import asyncio

import pytest

from aioeapi.config_session import SessionConfig


def run(coro):
    return asyncio.run(coro)


class FakeDevice:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    async def cli(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.responses:
            response = self.responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response
        return None


def test_status_all_requests_configuration_session_details():
    async def exercise():
        response = {"sessions": {}}
        device = FakeDevice([response])
        session = SessionConfig(device, "candidate")

        assert await session.status_all() is response
        assert device.calls == [(("show configuration sessions detail",), {})]

    run(exercise())


def test_status_returns_named_session_or_none():
    async def exercise():
        status = {"state": "pending"}
        device = FakeDevice(
            [
                {"sessions": {"candidate": status}},
                {"sessions": {"other": {"state": "pending"}}},
            ]
        )
        session = SessionConfig(device, "candidate")

        assert await session.status() is status
        assert await session.status() is None

    run(exercise())


def test_push_sends_config_session_commands_from_string():
    async def exercise():
        device = FakeDevice()
        session = SessionConfig(device, "candidate")

        await session.push("interface Ethernet1\n\n description uplink\n!\n")

        assert device.calls == [
            (
                (),
                {
                    "commands": [
                        "configure session candidate",
                        "interface Ethernet1",
                        " description uplink",
                        "!",
                    ]
                },
            )
        ]

    run(exercise())


def test_push_can_replace_existing_config():
    async def exercise():
        device = FakeDevice()
        session = SessionConfig(device, "candidate")

        await session.push(["hostname leaf1"], replace=True)

        assert device.calls == [
            (
                (),
                {
                    "commands": [
                        "configure session candidate",
                        "rollback clean-config",
                        "hostname leaf1",
                    ]
                },
            )
        ]

    run(exercise())


@pytest.mark.parametrize(
    ("method", "args", "expected"),
    [
        ("commit", (), "configure session candidate commit"),
        ("commit", ("00:05:00",), "configure session candidate commit timer 00:05:00"),
        ("abort", (), "configure session candidate abort"),
        ("write", (), "write"),
    ],
)
def test_session_commands(method, args, expected):
    async def exercise():
        device = FakeDevice()
        session = SessionConfig(device, "candidate")

        await getattr(session, method)(*args)

        assert device.calls == [((expected,), {})]

    run(exercise())


def test_diff_requests_text_output():
    async def exercise():
        device = FakeDevice(["diff text"])
        session = SessionConfig(device, "candidate")

        assert await session.diff() == "diff text"
        assert device.calls == [
            (("show session-config named candidate diffs",), {"ofmt": "text"})
        ]

    run(exercise())


def test_load_scp_file_raises_when_device_reports_error():
    async def exercise():
        device = FakeDevice([[{}, {"messages": ["Invalid input detected"]}]])
        session = SessionConfig(device, "candidate")

        with pytest.raises(RuntimeError, match="Invalid input detected"):
            await session.load_scp_file("flash:startup.cfg")

    run(exercise())


def test_load_scp_file_can_replace_existing_config():
    async def exercise():
        device = FakeDevice([[{}, {}, {"messages": ["Copy completed successfully"]}]])
        session = SessionConfig(device, "candidate")

        await session.load_scp_file("flash:startup.cfg", replace=True)

        assert device.calls == [
            (
                (),
                {
                    "commands": [
                        "configure session candidate",
                        "rollback clean-config",
                        "copy flash:startup.cfg session-config",
                    ]
                },
            )
        ]

    run(exercise())
