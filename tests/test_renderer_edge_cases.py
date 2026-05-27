from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

import modules.renderer as renderer_module
from modules.renderer import PlaywrightRenderer


@pytest.mark.asyncio
async def test_playwright_renderer_raises_without_playwright(monkeypatch):
    monkeypatch.setattr(renderer_module, "PLAYWRIGHT_AVAILABLE", False)

    with pytest.raises(RuntimeError, match="Playwright is not installed"):
        await PlaywrightRenderer().render("https://example.com")


@pytest.mark.asyncio
async def test_playwright_renderer_uses_browser_pool_and_validates_final_url(monkeypatch):
    events: list[str] = []

    class _Guard:
        def __init__(self):
            self.validate = AsyncMock(side_effect=lambda url: events.append(f"validate:{url}"))

    class _Page:
        def __init__(self):
            self.url = asyncio.sleep(0, result="https://example.com/final")

        async def goto(self, url, wait_until):
            events.append(f"goto:{url}:{wait_until}")

        async def content(self):
            return "<html><body>rendered</body></html>"

    class _Context:
        async def new_page(self):
            events.append("new_page")
            return _Page()

        async def close(self):
            events.append("context_close")

    class _Browser:
        async def new_context(self, **kwargs):
            events.append(f"context:{kwargs['viewport']['width']}x{kwargs['viewport']['height']}")
            return _Context()

    class _Pool:
        async def get_browser(self):
            events.append("get_browser")
            return _Browser()

    monkeypatch.setattr(renderer_module, "PLAYWRIGHT_AVAILABLE", True)
    monkeypatch.setattr("utils.ssrf_guard.SSRFGuard", lambda allow_private=False: _Guard())
    monkeypatch.setattr("utils.browser_pool.BrowserPool.get_instance", lambda: _Pool())

    html = await PlaywrightRenderer(timeout_ms=1234).render("https://example.com")

    assert html == "<html><body>rendered</body></html>"
    assert "get_browser" in events
    assert "goto:https://example.com:networkidle" in events
    assert "validate:https://example.com" in events
    assert "validate:https://example.com/final" in events
    assert "context_close" in events
