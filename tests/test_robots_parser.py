"""
test_robots_parser.py — Unit tests for the SeoEvaluator robots.txt parsing logic using urllib.robotparser.
"""

import pytest
from unittest.mock import AsyncMock, patch
import httpx
from modules.seo import SeoEvaluator
from modules.base import EvaluationResult

@pytest.mark.asyncio
async def test_robots_global_block():
    """
    Verifies that a global disallow directive (Disallow: /) in robots.txt is flagged as a critical issue.
    """
    evaluator = SeoEvaluator()
    mock_html = "<html><head><title>Test Page</title><meta name='description' content='A valid page description for testing purposes of the parser.'><link rel='canonical' href='https://example.com/'><script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"WebSite\", \"name\": \"Test\"}</script></head><body><h1>Header</h1></body></html>"
    
    robots_content = "User-agent: *\nDisallow: /"
    
    with patch.object(SeoEvaluator, "_fetch_robots_txt", return_value=robots_content):
        result = await evaluator.evaluate(mock_html, "https://example.com/")
        
    issue_ids = [issue.id for issue in result.issues]
    assert "R-SEO-ROBOTS-BLOCK" in issue_ids
    assert result.score < 5.0

@pytest.mark.asyncio
async def test_robots_path_block():
    """
    Verifies that a path-level disallow directive (e.g., Disallow: /admin/) blocking the specific audited URL is flagged.
    """
    evaluator = SeoEvaluator()
    mock_html = "<html><head><title>Admin Panel</title><meta name='description' content='A valid page description for testing purposes of the parser.'><link rel='canonical' href='https://example.com/admin/settings'><script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"WebSite\", \"name\": \"Test\"}</script></head><body><h1>Header</h1></body></html>"
    
    # Block /admin/ but allow the home page
    robots_content = "User-agent: *\nDisallow: /admin/\nSitemap: https://example.com/sitemap.xml"
    
    with patch.object(SeoEvaluator, "_fetch_robots_txt", return_value=robots_content):
        # Audit a URL under /admin/
        result = await evaluator.evaluate(mock_html, "https://example.com/admin/settings")
        
    issue_ids = [issue.id for issue in result.issues]
    # Should flag path block but not global block
    assert "R-SEO-ROBOTS-PATH-BLOCK" in issue_ids
    assert "R-SEO-ROBOTS-BLOCK" not in issue_ids

@pytest.mark.asyncio
async def test_robots_sitemap_directive():
    """
    Verifies that sitemap directive presence or absence in robots.txt is flagged correctly.
    """
    evaluator = SeoEvaluator()
    mock_html = "<html><head><title>Test Page</title><meta name='description' content='A valid page description for testing purposes of the parser.'><link rel='canonical' href='https://example.com/'><script type='application/ld+json'>{\"@context\": \"https://schema.org\", \"@type\": \"WebSite\", \"name\": \"Test\"}</script></head><body><h1>Header</h1></body></html>"
    
    # 1. Sitemap present
    robots_with_sitemap = "User-agent: *\nDisallow: /private/\nSitemap: https://example.com/sitemap.xml"
    with patch.object(SeoEvaluator, "_fetch_robots_txt", return_value=robots_with_sitemap):
        result_ok = await evaluator.evaluate(mock_html, "https://example.com/")
        
    issue_ids_ok = [issue.id for issue in result_ok.issues]
    assert "R-SEO-ROBOTS-SITEMAP" not in issue_ids_ok
    
    # 2. Sitemap missing
    robots_no_sitemap = "User-agent: *\nDisallow: /private/"
    with patch.object(SeoEvaluator, "_fetch_robots_txt", return_value=robots_no_sitemap):
        result_bad = await evaluator.evaluate(mock_html, "https://example.com/")
        
    issue_ids_bad = [issue.id for issue in result_bad.issues]
    assert "R-SEO-ROBOTS-SITEMAP" in issue_ids_bad
