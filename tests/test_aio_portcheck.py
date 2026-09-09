import asyncio

import httpx

import aioeapi.aio_portcheck as aio_portcheck
from aioeapi.aio_portcheck import port_check_url


def run(coro):
    return asyncio.run(coro)


class StubWriter:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_port_check_url_returns_true_for_open_port(monkeypatch):
    async def exercise():
        writer = StubWriter()

        async def open_connection(host, port):
            assert host == "switch.example.com"
            assert port == 443
            return None, writer

        monkeypatch.setattr(aio_portcheck.asyncio, "open_connection", open_connection)

        assert await port_check_url(httpx.URL("https://switch.example.com"))
        assert writer.closed

    run(exercise())


def test_port_check_url_returns_false_for_connection_error(monkeypatch):
    async def exercise():
        async def open_connection(host, port):
            raise OSError("connection refused")

        monkeypatch.setattr(aio_portcheck.asyncio, "open_connection", open_connection)

        assert not await port_check_url(
            httpx.URL("http://switch.example.com:8080"), timeout=1
        )

    run(exercise())
