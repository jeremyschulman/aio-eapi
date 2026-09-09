import asyncio

import httpx
import pytest

from aioeapi import Device, EapiCommandError, SessionConfig


def run(coro):
    return asyncio.run(coro)


def json_transport(body, status_code=200):
    def handler(request):
        return httpx.Response(status_code, json=body, request=request)

    return httpx.MockTransport(handler)


def test_device_initializes_eapi_defaults():
    dev = Device(
        host="switch.example.com",
        username="admin",
        password="secret",
        proto="http",
    )

    try:
        assert str(dev.base_url) == "http://switch.example.com"
        assert dev.port == 80
        assert dev.headers["Content-Type"] == "application/json-rpc"
        assert isinstance(dev.auth, httpx.BasicAuth)
    finally:
        run(dev.aclose())


def test_device_uses_explicit_port_and_base_url():
    dev = Device(
        host="switch.example.com",
        port=8443,
        base_url="https://override.example.net:9443",
    )

    try:
        assert str(dev.base_url) == "https://override.example.net:9443"
        assert dev.port == 8443
    finally:
        run(dev.aclose())


def test_jsoncrpc_command_builds_run_cmds_payload():
    dev = Device(host="switch.example.com")

    try:
        payload = dev.jsoncrpc_command(
            commands=["show version"],
            ofmt=None,
            version="latest",
            req_id="abc-123",
            autoComplete=True,
            expandAliases=False,
        )
    finally:
        run(dev.aclose())

    assert payload == {
        "jsonrpc": "2.0",
        "method": "runCmds",
        "params": {
            "version": "latest",
            "cmds": ["show version"],
            "format": "json",
            "autoComplete": True,
            "expandAliases": False,
        },
        "id": "abc-123",
    }


def test_cli_requires_command_or_commands():
    async def exercise():
        dev = Device(host="switch.example.com")
        try:
            with pytest.raises(RuntimeError, match="Required 'command' or 'commands'"):
                await dev.cli()
        finally:
            await dev.aclose()

    run(exercise())


def test_cli_returns_single_command_result():
    async def exercise():
        dev = Device(
            host="switch.example.com",
            transport=json_transport({"result": [{"hostname": "leaf1"}]}),
        )
        try:
            assert await dev.cli("show hostname") == {"hostname": "leaf1"}
        finally:
            await dev.aclose()

    run(exercise())


def test_cli_returns_multiple_command_results():
    async def exercise():
        dev = Device(
            host="switch.example.com",
            transport=json_transport(
                {"result": [{"hostname": "leaf1"}, {"version": "4.32.0F"}]}
            ),
        )
        try:
            assert await dev.cli(commands=["show hostname", "show version"]) == [
                {"hostname": "leaf1"},
                {"version": "4.32.0F"},
            ]
        finally:
            await dev.aclose()

    run(exercise())


def test_jsonrpc_exec_returns_text_outputs():
    async def exercise():
        dev = Device(
            host="switch.example.com",
            transport=json_transport({"result": [{"output": "diff output\n"}]}),
        )
        try:
            payload = dev.jsoncrpc_command(
                commands=["show session-config named test diffs"],
                ofmt="text",
                version="latest",
            )
            assert await dev.jsonrpc_exec(payload) == ["diff output\n"]
        finally:
            await dev.aclose()

    run(exercise())


def test_jsonrpc_exec_raises_command_error_with_context():
    async def exercise():
        dev = Device(
            host="switch.example.com",
            transport=json_transport(
                {
                    "error": {
                        "message": "CLI command 2 of 3 failed",
                        "data": [
                            {"hostname": "leaf1"},
                            {"errors": ["Invalid input"]},
                        ],
                    }
                }
            ),
        )
        payload = dev.jsoncrpc_command(
            commands=["show hostname", "show bad", "show version"],
            ofmt="json",
            version="latest",
        )

        try:
            with pytest.raises(EapiCommandError) as exc_info:
                await dev.jsonrpc_exec(payload)
        finally:
            await dev.aclose()

        exc = exc_info.value
        assert str(exc) == "CLI command 2 of 3 failed"
        assert exc.failed == "show bad"
        assert exc.errors == ["Invalid input"]
        assert exc.passed == [{"hostname": "leaf1"}]
        assert exc.not_exec == ["show version"]

    run(exercise())


def test_cli_can_suppress_command_error():
    class ErrorDevice(Device):
        async def jsonrpc_exec(self, jsonrpc):
            raise EapiCommandError(
                failed="show bad",
                errors=["Invalid input"],
                errmsg="bad command",
                passed=[],
                not_exec=[],
            )

    async def exercise():
        dev = ErrorDevice(host="switch.example.com")
        try:
            assert await dev.cli("show bad", suppress_error=True) is None
        finally:
            await dev.aclose()

    run(exercise())


def test_config_session_factory_binds_device():
    dev = Device(host="switch.example.com")

    try:
        session = dev.config_session("candidate")
        assert isinstance(session, SessionConfig)
        assert session.name == "candidate"
        assert session.device is dev
    finally:
        run(dev.aclose())
