"""
test_broken_links.py — Failing unit tests for the Crawler's Broken Link Checker.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from crawler import Crawler

@pytest.mark.asyncio
async def test_crawler_detects_broken_links():
    """
    Crawler must perform requests to discover outbound links and capture non-200 responses.
    """
    # Instantiate crawler with crawl_depth 1
    crawler = Crawler("https://example.com", max_depth=1, max_urls=3)
    
    # Mock good response and broken response
    mock_good = MagicMock()
    mock_good.status_code = 200
    mock_good.text = '<a href="https://example.com/broken">Broken Link</a><a href="https://example.com/ok">Ok Link</a>'
    mock_good.url = "https://example.com"
    
    mock_ok = MagicMock()
    mock_ok.status_code = 200
    mock_ok.text = "All good here"
    mock_ok.url = "https://example.com/ok"
    
    mock_broken = MagicMock()
    # 404 response
    mock_broken.status_code = 404
    mock_broken.text = "Page not found"
    mock_broken.url = "https://example.com/broken"

    # Define mock get selector
    async def mock_get(url, *args, **kwargs):
        if "/ok" in url:
            return mock_ok
        elif "/broken" in url:
            return mock_broken
        else:
            return mock_good
            
    client = MagicMock()
    client.get = AsyncMock(side_effect=mock_get)
    
    with patch("utils.ssrf_guard.resolve_ips", return_value=["93.184.216.34"]):
        # Execute crawl
        visited = await crawler.crawl(client)
        
    # Crawler must record the broken link in a crawler attribute or map
    assert "https://example.com/broken" in crawler.broken_links
    assert crawler.broken_links["https://example.com/broken"] == 404
    
    # The valid page should be in visited_content
    assert "https://example.com/ok" in visited
    # The broken page should NOT be added to visited_content (since it's a 404)
    assert "https://example.com/broken" not in visited
