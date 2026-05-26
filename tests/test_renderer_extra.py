import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import modules.renderer as renderer
from modules.renderer import PlaywrightRenderer, SSRFLocalProxy


class _FakeReader:
    def __init__(self, line=None, chunks=None):
        self.lines = list(line or [])
        self.chunks = list(chunks or [])

    async def readline(self):
        return self.lines.pop(0) if self.lines else b""

    async def read(self, _size):
        return self.chunks.pop(0) if self.chunks else b""


class _FakeWriter:
    def __init__(self):
        self.writes = []
        self.close_called = False
        self.wait_closed_called = False

    def write(self, data):
        self.writes.append(data)

    async def drain(self):
        return None

    def close(self):
        self.close_called = True

    async def wait_closed(self):
        self.wait_closed_called = True


class _FakeServer:
    def __init__(self, port=8123):
        sock = MagicMock()
        sock.getsockname.return_value = ("127.0.0.1", port)
        self.sockets = [sock]
        self.close_called = False
        self.wait_closed_called = False

    def close(self):
        self.close_called = True

    async def wait_closed(self):
        self.wait_closed_called = True


@pytest.mark.asyncio
async def test_ssrf_local_proxy_start_stop_and_proxy_url(monkeypatch):
    server = _FakeServer(port=8123)

    async def fake_start_server(*args, **kwargs):
        return server

    monkeypatch.setattr(asyncio, "start_server", fake_start_server)

    proxy = SSRFLocalProxy(guard=MagicMock())
    port = await proxy.start()

    assert port == 8123
    assert proxy.get_proxy_url() == "http://127.0.0.1:8123"

    await proxy.stop()
    assert server.close_called is True
    assert server.wait_closed_called is True


@pytest.mark.asyncio
async def test_ssrf_local_proxy_handles_connect_and_http_requests(monkeypatch):
    guard = MagicMock()
    guard.validate = AsyncMock()
    guard.get_pinned_address.return_value = "93.184.216.34"
    proxy = SSRFLocalProxy(guard=guard)

    server_reader = _FakeReader()
    server_writer = _FakeWriter()

    async def fake_open_connection(host, port):
        assert host == "93.184.216.34"
        assert port in {80, 443}
        return server_reader, server_writer

    monkeypatch.setattr(asyncio, "open_connection", fake_open_connection)
    monkeypatch.setattr(SSRFLocalProxy, "tunnel", AsyncMock(return_value=None))

    connect_reader = _FakeReader([b"CONNECT example.com:443 HTTP/1.1\r\n"])
    connect_writer = _FakeWriter()
    await proxy.handle_connection(connect_reader, connect_writer)

    guard.validate.assert_awaited_once_with("https://example.com:443")
    assert any(b"200 Connection Established" in chunk for chunk in connect_writer.writes)

    guard.validate.reset_mock()
    http_reader = _FakeReader([b"GET https://example.com/path?q=1 HTTP/1.1\r\n"])
    http_writer = _FakeWriter()
    await proxy.handle_connection(http_reader, http_writer)

    guard.validate.assert_awaited_once_with("https://example.com/path?q=1")
    assert server_writer.writes[0] == b"GET /path?q=1 HTTP/1.1\r\n"
    assert http_writer.close_called is True


@pytest.mark.asyncio
async def test_ssrf_local_proxy_handles_invalid_and_blocked_requests():
    guard = MagicMock()
    guard.validate = AsyncMock(side_effect=ValueError("blocked"))
    guard.get_pinned_address.return_value = "93.184.216.34"
    proxy = SSRFLocalProxy(guard=guard)

    connect_reader = _FakeReader([b"CONNECT example.com:443 HTTP/1.1\r\n"])
    connect_writer = _FakeWriter()
    await proxy.handle_connection(connect_reader, connect_writer)
    assert connect_writer.writes[0].startswith(b"HTTP/1.1 403 Forbidden")

    malformed_reader = _FakeReader([b"GET / HTTP/1.1\r\n"])
    malformed_writer = _FakeWriter()
    await proxy.handle_connection(malformed_reader, malformed_writer)
    assert malformed_writer.close_called is True


@pytest.mark.asyncio
async def test_ssrf_local_proxy_tunnel_writes_until_eof():
    proxy = SSRFLocalProxy(guard=MagicMock())
    reader = _FakeReader(chunks=[b"chunk-1", b"chunk-2", b""])
    writer = _FakeWriter()

    await proxy.tunnel(reader, writer)

    assert writer.writes == [b"chunk-1", b"chunk-2"]
    assert writer.close_called is True


@pytest.mark.asyncio
async def test_playwright_renderer_requires_playwright(monkeypatch):
    monkeypatch.setattr(renderer, "PLAYWRIGHT_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="Playwright is not installed"):
        await PlaywrightRenderer().render("https://example.com")


@pytest.mark.asyncio
async def test_playwright_renderer_renders_and_revalidates_final_url(monkeypatch):
    monkeypatch.setattr(renderer, "PLAYWRIGHT_AVAILABLE", True)

    guard = MagicMock()
    guard.validate = AsyncMock()
    browser = AsyncMock()
    context = AsyncMock()
    page = AsyncMock()

    async def awaited_final_url():
        return 123

    page.url = awaited_final_url()
    page.content = AsyncMock(return_value="<html><body>rendered</body></html>")
    page.goto = AsyncMock()
    context.new_page = AsyncMock(return_value=page)
    context.close = AsyncMock()
    browser.new_context = AsyncMock(return_value=context)

    fake_pool = MagicMock()
    fake_pool.get_browser = AsyncMock(return_value=browser)

    with patch("utils.ssrf_guard.SSRFGuard", return_value=guard), patch(
        "utils.browser_pool.BrowserPool.get_instance", return_value=fake_pool
    ):
        html = await PlaywrightRenderer().render("https://example.com/rendered")

    assert html == "<html><body>rendered</body></html>"
    assert guard.validate.await_args_list[0].args == ("https://example.com/rendered",)
    assert guard.validate.await_args_list[1].args == ("https://example.com/rendered",)
    browser.new_context.assert_awaited_once()
    page.goto.assert_awaited_once_with("https://example.com/rendered", wait_until="networkidle")
    context.close.assert_awaited_once()
