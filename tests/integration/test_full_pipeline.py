"""
test_full_pipeline.py — Integration tests verifying the entire evaluator pipeline.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from main import run_evaluation
from modules.base import EvaluationResult

@pytest.mark.asyncio
async def test_full_pipeline_single_url_success():
    """
    Integration test validating that run_evaluation correctly crawls a single URL
    and runs all active evaluators.
    """
    from modules.seo import SeoEvaluator
    from modules.accessibility import AccessibilityEvaluator
    
    active_evaluators = [
        SeoEvaluator(),
        AccessibilityEvaluator()
    ]
    
    mock_html = """<!DOCTYPE html>
    <html>
      <head>
        <title>Acme widgets for Drupal</title>
        <meta name="description" content="Discover the best high-quality Drupal widgets at Acme Widgets. Standard compliance, excellent durability, and modern engineering design.">
        <link rel="canonical" href="https://example.com/drupal-page">
        <meta name="robots" content="index, follow">
        <script type="application/ld+json">{"@context": "https://schema.org", "@type": "WebSite", "name": "Acme"}</script>
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
    
    with patch("httpx.AsyncClient.get", return_value=mock_resp), \
         patch("httpx.AsyncClient.head", return_value=mock_resp), \
         patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]):
         
        results = await run_evaluation(
            url="https://example.com/drupal-page",
            active_modules=active_evaluators,
            allow_private=False,
            crawl_depth=0
        )
        
    assert len(results) == 2
    domains = [r.domain for r in results]
    assert "Technical SEO" in domains
    assert "Accessibility (WCAG 2.2 AA)" in domains
    
    # Check that score was computed and issues are within range
    for r in results:
        assert isinstance(r, EvaluationResult)
        assert r.score >= 5.0
