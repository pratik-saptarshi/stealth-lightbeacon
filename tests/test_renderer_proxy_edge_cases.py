from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import modules.renderer as renderer_module
from modules.renderer import SSRFLocalProxy


class _Reader:
    def __init__(self, line: bytes):
        self._line = line

    async def readline(self):
        line, self._line = self._line, b""
        return line

    async def read(self, _size):
        return b""


class _Writer:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    def close(self):
        self.closed = True

    async def wait_closed(self):
        return None


@pytest.mark.asyncio
async def test_ssrf_local_proxy_connect_tunnel_branch(monkeypatch):
    guard = type(
        "Guard",
        (),
        {
            "validate": AsyncMock(return_value=None),
            "get_pinned_address": lambda self, host: "93.184.216.34",
        },
    )()
    proxy = SSRFLocalProxy(guard)
    reader = _Reader(b"CONNECT example.com:443 HTTP/1.1\r\n")
    writer = _Writer()
    server_reader = _Reader(b"")
    server_writer = _Writer()

    monkeypatch.setattr(asyncio, "open_connection", AsyncMock(return_value=(server_reader, server_writer)))
    monkeypatch.setattr(SSRFLocalProxy, "tunnel", AsyncMock(return_value=None))

    await proxy.handle_connection(reader, writer)

    assert writer.closed is True
    assert any(b"200 Connection Established" in chunk for chunk in writer.writes)
    guard.validate.assert_awaited_once()


@pytest.mark.asyncio
async def test_ssrf_local_proxy_http_branch_rewrites_request_line(monkeypatch):
    guard = type(
        "Guard",
        (),
        {
            "validate": AsyncMock(return_value=None),
            "get_pinned_address": lambda self, host: "93.184.216.34",
        },
    )()
    proxy = SSRFLocalProxy(guard)
    reader = _Reader(b"GET http://example.com/path?q=1 HTTP/1.1\r\n")
    writer = _Writer()
    server_reader = _Reader(b"")
    server_writer = _Writer()

    monkeypatch.setattr(asyncio, "open_connection", AsyncMock(return_value=(server_reader, server_writer)))
    monkeypatch.setattr(SSRFLocalProxy, "tunnel", AsyncMock(return_value=None))

    await proxy.handle_connection(reader, writer)

    assert writer.closed is True
    assert server_writer.writes[0] == b"GET /path?q=1 HTTP/1.1\r\n"
    guard.validate.assert_awaited_once()
