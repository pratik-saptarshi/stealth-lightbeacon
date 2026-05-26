from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from modules.base import EvaluationResult
from services.audit_service import run_evaluation
from services.errors import AuditServiceError


@pytest.mark.asyncio
async def test_audit_service_runs_single_url_success():
    from modules.accessibility import AccessibilityEvaluator
    from modules.seo import SeoEvaluator

    active_evaluators = [SeoEvaluator(), AccessibilityEvaluator()]

    mock_html = """<!DOCTYPE html>
    <html>
      <head>
        <title>Acme widgets for Drupal</title>
        <meta name="description" content="Discover the best high-quality Drupal widgets at Acme Widgets.">
      </head>
      <body>
        <h1>Acme Drupal Page</h1>
        <img src="logo.png" alt="Acme Logo">
      </body>
    </html>"""

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = mock_html
    mock_resp.url = "https://example.com/drupal-page"

    with (
        patch("httpx.AsyncClient.get", return_value=mock_resp),
        patch("httpx.AsyncClient.head", return_value=mock_resp),
        patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]),
    ):
        results = await run_evaluation(
            url="https://example.com/drupal-page",
            active_modules=active_evaluators,
            allow_private=False,
            crawl_depth=0,
        )

    assert len(results) == 2
    assert all(isinstance(result, EvaluationResult) for result in results)


@pytest.mark.asyncio
async def test_audit_service_wraps_fetch_failures_and_closes_browser_pool():
    browser_pool = MagicMock()
    browser_pool.close = AsyncMock()

    with (
        patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]),
        patch("httpx.AsyncClient.get", side_effect=RuntimeError("boom")),
        patch("utils.browser_pool.BrowserPool.get_instance", return_value=browser_pool),
    ):
        with pytest.raises(AuditServiceError) as exc:
            await run_evaluation(
                url="https://example.com/drupal-page",
                active_modules=[],
                allow_private=False,
                crawl_depth=0,
            )

    assert exc.value.title == "Error: Failed to fetch target URL: https://example.com/drupal-page"
    browser_pool.close.assert_awaited_once()
