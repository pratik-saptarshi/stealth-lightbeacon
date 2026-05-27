from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import crawler as crawler_mod
from crawler import Crawler


class _FakeGuard:
    async def validate(self, url):
        return None


@pytest.mark.asyncio
async def test_crawler_renderer_and_redirect_paths(monkeypatch):
    monkeypatch.setattr(crawler_mod.asyncio, "sleep", AsyncMock())
    monkeypatch.setattr("utils.ssrf_guard.SSRFGuard", lambda allow_private=False: _FakeGuard())

    renderer = MagicMock()
    renderer.scrape = AsyncMock(
        return_value="<html><body><a href='/child'>Child</a></body></html>"
    )
    crawler = Crawler("https://example.com", max_depth=1, max_urls=2, rate_delay=0)
    visited = await crawler.crawl(MagicMock(), renderer=renderer)

    assert "https://example.com" in visited
    assert "https://example.com/child" in visited or len(visited) == 1

    client = MagicMock()
    response = MagicMock()
    response.status_code = 200
    response.text = "<html><body><a href='/child'>Child</a></body></html>"
    response.url = "https://other.com/final"
    client.get = AsyncMock(return_value=response)

    redirected = await crawler.crawl(client)
    assert redirected == {}


@pytest.mark.asyncio
async def test_crawler_extracts_and_skips_bad_links():
    crawler = Crawler("https://example.com", max_depth=1)
    html = """
    <html>
      <body>
        <a href="/page#frag">Fragment</a>
        <a href="#skip">Skip</a>
        <a href="javascript:void(0)">JS</a>
        <a href="mailto:test@example.com">Mail</a>
        <a href="https://example.com/page">Absolute</a>
        <a href="https://other.example/page">Other</a>
      </body>
    </html>
    """

    links = crawler.extract_links(html, "https://example.com")

    assert links == ["https://example.com/page"]
