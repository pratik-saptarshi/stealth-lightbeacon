import asyncio
from unittest.mock import AsyncMock

import pytest

import modules.scraping.factory as factory
import modules.scraping.obscura as obscura
import modules.scraping.zendriver as zendriver


class _FakeResponse:
    def __init__(self, text="<html>fallback</html>", url="https://example.com"):
        self.text = text
        self.url = url

    def raise_for_status(self):
        return None


class _FakeAsyncClient:
    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        return self.response


class _FakeProcess:
    def __init__(self, returncode=0, stdout=b"<html>binary</html>", stderr=b""):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self):
        return self._stdout, self._stderr


class _FakePage:
    def __init__(self):
        self.url = "https://example.com/final"

    async def goto(self, *args, **kwargs):
        return None

    async def content(self):
        return "<html>rendered</html>"


class _FakeContext:
    def __init__(self):
        self.page = _FakePage()

    async def add_init_script(self, *args, **kwargs):
        return None

    async def new_page(self):
        return self.page

    async def close(self):
        return None


class _FakeBrowser:
    def __init__(self):
        self.context = _FakeContext()

    async def new_context(self, *args, **kwargs):
        return self.context

    async def close(self):
        return None


class _FakePlaywright:
    def __init__(self):
        self.browser = _FakeBrowser()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    @property
    def chromium(self):
        return self

    async def launch(self, *args, **kwargs):
        return self.browser


def test_factory_selects_expected_engine(monkeypatch):
    calls = []

    class _FakeObscura:
        def __init__(self, binary_path, allow_private=False):
            calls.append(("obscura", binary_path, allow_private))

    class _FakeZendriver:
        def __init__(self, allow_private=False):
            calls.append(("zendriver", allow_private))

    class _FakeMcp:
        def __init__(self, **kwargs):
            calls.append(("mcp", kwargs))

    monkeypatch.setattr(factory, "ObscuraEngine", _FakeObscura)
    monkeypatch.setattr(factory, "ZendriverEngine", _FakeZendriver)
    monkeypatch.setattr(factory, "StealthMcpLayer", _FakeMcp)
    monkeypatch.setattr(factory.config, "MCP_COMMAND", "/opt/mcp")
    monkeypatch.setattr(factory.config, "MCP_COMMAND_ARGS", ["--stdio"])
    monkeypatch.setattr(factory.config, "MCP_ARGS", ["--legacy"])
    monkeypatch.setattr(factory.config, "MCP_HANDSHAKE_TIMEOUT", 1.5)
    monkeypatch.setattr(factory.config, "MCP_TOOL_TIMEOUT", 2.5)
    monkeypatch.setattr(factory.config, "MCP_SHUTDOWN_TIMEOUT", 3.5)

    factory.ScrapingFactory.get_engine("fast", allow_private=True)
    factory.ScrapingFactory.get_engine("stealth")
    factory.ScrapingFactory.get_engine("mcp")
    factory.ScrapingFactory.get_engine("http")

    assert calls[0] == ("obscura", "bin/obscura", True)
    assert calls[1] == ("zendriver", False)
    assert calls[2][0] == "mcp"
    assert calls[2][1]["mcp_command"] == "/opt/mcp"
    assert calls[2][1]["mcp_args"] == ["--stdio"]
    assert calls[3] == ("obscura", "bin/obscura_absent", False)


@pytest.mark.asyncio
async def test_obscura_binary_and_fallback_paths(monkeypatch):
    guard = obscura.SSRFGuard()
    guard.validate = AsyncMock(return_value=None)

    monkeypatch.setattr(obscura.os.path, "exists", lambda path: True)
    monkeypatch.setattr(obscura.os.path, "isfile", lambda path: True)
    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess()

    monkeypatch.setattr(obscura.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    engine = obscura.ObscuraEngine(binary_path="/opt/obscura")
    engine.ssrf_guard = guard
    binary_html = await engine.scrape("https://example.com/binary")

    assert binary_html == "<html>binary</html>"

    monkeypatch.setattr(obscura.os.path, "exists", lambda path: False)
    monkeypatch.setattr(
        obscura.httpx,
        "AsyncClient",
        lambda *args, **kwargs: _FakeAsyncClient(_FakeResponse()),
    )

    fallback_html = await engine.scrape("https://example.com/fallback")

    assert fallback_html == "<html>fallback</html>"


@pytest.mark.asyncio
async def test_zendriver_happy_path_and_missing_playwright(monkeypatch):
    monkeypatch.setattr(zendriver, "PLAYWRIGHT_AVAILABLE", False)
    with pytest.raises(RuntimeError, match="Playwright is not installed"):
        await zendriver.ZendriverEngine().scrape("https://example.com")

    monkeypatch.setattr(zendriver, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr(zendriver, "async_playwright", lambda: _FakePlaywright(), raising=False)

    engine = zendriver.ZendriverEngine()
    engine.ssrf_guard.validate = AsyncMock(return_value=None)

    html = await engine.scrape("https://example.com")

    assert html == "<html>rendered</html>"
