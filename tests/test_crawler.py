"""
test_crawler.py — Unit tests for the async recursive crawler.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from crawler import Crawler

@pytest.mark.asyncio
async def test_crawler_extracts_links():
    """
    Verifies that Crawler correctly extracts and normalizes relative/absolute links.
    """
    crawler = Crawler("https://example.com", max_depth=1)
    
    html = """
    <html>
      <body>
        <a href="/about-us">About</a>
        <a href="https://example.com/contact">Contact</a>
        <a href="https://otherdomain.com/blog">External</a>
        <a href="#anchor">Anchor</a>
      </body>
    </html>
    """
    
    links = crawler.extract_links(html, "https://example.com")
    
    # Normalization should turn relative to absolute, ignore external and anchors
    assert "https://example.com/about-us" in links
    assert "https://example.com/contact" in links
    assert "https://otherdomain.com/blog" not in links
    assert "https://example.com#anchor" not in links

@pytest.mark.asyncio
async def test_crawler_max_depth_boundary():
    """
    Verifies that the crawler does not traverse deeper than the specified max_depth.
    """
    # max_depth = 0 should only crawl the entry URL
    crawler = Crawler("https://example.com", max_depth=0, max_urls=10)
    
    # Mock network fetching
    mock_responses = {
        "https://example.com": "<html><body><a href='/page1'>Page 1</a></body></html>",
        "https://example.com/page1": "<html><body><a href='/page2'>Page 2</a></body></html>"
    }
    
    async def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_responses.get(url, "")
        mock_resp.url = url
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        import httpx
        async with httpx.AsyncClient() as client:
            crawled = await crawler.crawl(client)
            
    assert len(crawled) == 1
    assert "https://example.com" in crawled
    assert "https://example.com/page1" not in crawled

@pytest.mark.asyncio
async def test_crawler_max_urls_circuit_breaker():
    """
    Verifies that the crawler halts crawl recursion when the max_urls limit is breached.
    """
    crawler = Crawler("https://example.com", max_depth=3, max_urls=3)
    
    # Supply multiple pages
    mock_responses = {
        "https://example.com": "<html><body><a href='/p1'>p1</a><a href='/p2'>p2</a></body></html>",
        "https://example.com/p1": "<html><body><a href='/p3'>p3</a><a href='/p4'>p4</a></body></html>",
        "https://example.com/p2": "<html><body></body></html>",
        "https://example.com/p3": "<html><body></body></html>"
    }
    
    async def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = mock_responses.get(url, "")
        mock_resp.url = url
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        import httpx
        async with httpx.AsyncClient() as client:
            crawled = await crawler.crawl(client)
            
    # Max URLs is 3, so we should never crawl more than 3 URLs
    assert len(crawled) <= 3


@pytest.mark.asyncio
async def test_crawler_records_broken_links():
    crawler = Crawler("https://example.com", max_depth=1, max_urls=10, rate_delay=0)

    async def mock_get(url, **kwargs):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_resp.text = "Not Found"
        mock_resp.url = url
        return mock_resp

    with patch("httpx.AsyncClient.get", side_effect=mock_get):
        import httpx

        async with httpx.AsyncClient() as client:
            crawled = await crawler.crawl(client)

    assert crawled == {}
    assert crawler.broken_links["https://example.com"] == 404
