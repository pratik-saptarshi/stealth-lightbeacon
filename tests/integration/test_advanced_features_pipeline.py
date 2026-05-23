"""
test_advanced_features_pipeline.py — Integration tests verifying advanced features (Broken Links, JSON:API, Cookie Security).
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import run_evaluation
from modules.base import EvaluationResult

@pytest.mark.asyncio
async def test_integration_pipeline_advanced_features():
    """
    E2E integration test validating broken link checks and API endpoint scans inside run_evaluation.
    """
    from modules.seo import SeoEvaluator
    from modules.drupal import DrupalEvaluator
    
    active_evaluators = [
        SeoEvaluator(),
        DrupalEvaluator()
    ]
    
    mock_html = """<!DOCTYPE html>
    <html>
      <head>
        <title>Acme widgets for Drupal</title>
        <link rel="canonical" href="https://example.com/drupal-page">
      </head>
      <body>
        <h1>Acme Drupal Page</h1>
        <a href="https://example.com/broken-link">Broken Outbound Link</a>
      </body>
    </html>"""
    
    # Define client responses mock dictionary
    async def mock_get(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.url = url
        if "broken-link" in url:
            mock_resp.status_code = 404
            mock_resp.text = "Not Found"
        elif "jsonapi/user/user" in url:
            mock_resp.status_code = 200
            mock_resp.text = '{"data": [{"type": "user--user", "attributes": {"name": "admin"}}]}'
        else:
            mock_resp.status_code = 200
            mock_resp.text = mock_html
            # Add secure Set-Cookie to check security headers
            mock_resp.headers = {
                "Set-Cookie": "session_id=123; HttpOnly; Secure; SameSite=Lax",
                "X-Frame-Options": "SAMEORIGIN",
                "Content-Security-Policy": "default-src 'self'",
                "Strict-Transport-Security": "max-age=31536000",
                "X-Content-Type-Options": "nosniff"
            }
        return mock_resp

    async def mock_head(url, *args, **kwargs):
        mock_resp = MagicMock()
        mock_resp.url = url
        mock_resp.status_code = 200
        mock_resp.headers = {
            "X-Frame-Options": "SAMEORIGIN",
            "Content-Security-Policy": "default-src 'self'",
            "Strict-Transport-Security": "max-age=31536000",
            "X-Content-Type-Options": "nosniff"
        }
        return mock_resp

    client = MagicMock()
    client.get = AsyncMock(side_effect=mock_get)
    client.head = AsyncMock(side_effect=mock_head)
    
    with patch("httpx.AsyncClient", return_value=client), \
         patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]):
         
        results = await run_evaluation(
            url="https://example.com/drupal-page",
            active_modules=active_evaluators,
            allow_private=False,
            crawl_depth=1,
            check_links=True,
            check_api=True
        )
        
    domains = {r.domain: r for r in results}
    assert "Technical SEO" in domains
    assert "Drupal & Security Headers" in domains
    
    seo_result = domains["Technical SEO"]
    drupal_result = domains["Drupal & Security Headers"]
    
    # Assert broken link issue was successfully injected into SEO
    seo_issue_ids = [issue.id for issue in seo_result.issues]
    assert "R-SEO-BROKEN-LINK" in seo_issue_ids
    
    # Assert API exposure issue was successfully injected into Drupal
    drupal_issue_ids = [issue.id for issue in drupal_result.issues]
    assert "R-DRUP-API-EXPOSED" in drupal_issue_ids
