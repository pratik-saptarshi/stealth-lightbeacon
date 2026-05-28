"""
test_service_orchestration_pipeline.py — Integration test covering persistence,
crawl consolidation, broken-link injection, and final report publication.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from main import run_evaluation
from modules.drupal import DrupalEvaluator
from modules.seo import SeoEvaluator


class _FakeStore:
    def __init__(self):
        self.pages = []
        self.findings = []
        self.finished = None

    async def record_page(self, run_id, page_url, html_content):
        self.pages.append((run_id, page_url, html_content))

    async def record_finding(self, **kwargs):
        self.findings.append(kwargs)

    async def finish_run(self, run_id, report_payload, crawled_pages_count, domain_count):
        self.finished = {
            "run_id": run_id,
            "report_payload": report_payload,
            "crawled_pages_count": crawled_pages_count,
            "domain_count": domain_count,
        }


@pytest.mark.asyncio
async def test_integration_pipeline_persists_and_finishes_run():
    html = """<!DOCTYPE html>
<html>
  <head>
    <title>Acme widgets for Drupal</title>
    <meta name="description" content="Discover the best high-quality Drupal widgets at Acme Widgets. Standard compliance, excellent durability, and modern engineering design.">
    <link rel="canonical" href="https://example.com/drupal-page">
    <meta rel="robots" content="index, follow">
    <meta property="og:title" content="Acme widgets for Drupal">
    <script type="application/ld+json">{"@context": "https://schema.org", "@type": "WebSite", "name": "Acme"}</script>
  </head>
  <body>
    <h1>Acme Drupal Page</h1>
    <a href="https://example.com/broken-link">Broken Outbound Link</a>
  </body>
</html>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = html
    mock_resp.url = "https://example.com/drupal-page"
    mock_resp.headers = {
        "Set-Cookie": "session_id=123; HttpOnly; Secure; SameSite=Lax",
        "X-Frame-Options": "SAMEORIGIN",
        "Content-Security-Policy": "default-src 'self'",
        "Strict-Transport-Security": "max-age=31536000",
        "X-Content-Type-Options": "nosniff",
    }

    async def mock_get(url, *args, **kwargs):
        if "broken-link" in url:
            broken = MagicMock()
            broken.status_code = 404
            broken.text = "Not Found"
            broken.url = url
            return broken
        if "jsonapi/user/user" in url:
            api = MagicMock()
            api.status_code = 200
            api.text = '{"data": [{"type": "user--user", "attributes": {"name": "admin"}}]}'
            api.url = url
            return api
        return mock_resp

    async def mock_head(url, *args, **kwargs):
        return mock_resp

    async def fake_crawl(self, client, renderer=None):
        self.broken_links = {"https://example.com/broken-link": 404}
        return {
            "https://example.com/drupal-page": html,
            "https://example.com/secondary": html.replace("drupal-page", "secondary"),
        }

    fake_store = _FakeStore()
    client = MagicMock()
    client.get = AsyncMock(side_effect=mock_get)
    client.head = AsyncMock(side_effect=mock_head)
    client.aclose = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=client), \
         patch("crawler.Crawler.crawl", new=fake_crawl), \
         patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]), \
         patch("utils.browser_pool.BrowserPool.get_instance") as get_pool:
        pool = MagicMock()
        pool.close = AsyncMock(return_value=None)
        get_pool.return_value = pool

        results = await run_evaluation(
            url="https://example.com/drupal-page",
            active_modules=[SeoEvaluator(), DrupalEvaluator()],
            allow_private=False,
            crawl_depth=1,
            max_urls=10,
            check_links=True,
            check_api=True,
            store=fake_store,
            run_id="run-1",
        )

    domains = {result.domain: result for result in results}
    assert "Technical SEO" in domains
    assert "Drupal & Security Headers" in domains
    assert fake_store.pages
    assert fake_store.findings
    assert fake_store.finished is not None
    assert fake_store.finished["run_id"] == "run-1"
    assert fake_store.finished["crawled_pages_count"] == 2
    assert fake_store.finished["domain_count"] == 2
    assert any(issue.id == "R-SEO-BROKEN-LINK" for issue in domains["Technical SEO"].issues)
    assert any(issue.id == "R-DRUP-API-EXPOSED" for issue in domains["Drupal & Security Headers"].issues)
