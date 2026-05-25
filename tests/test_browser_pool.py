"""
test_browser_pool.py — Unit tests for the BrowserPool singleton.
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from utils.browser_pool import BrowserPool


@pytest.mark.asyncio
async def test_browser_pool_singleton_identity():
    """
    Verifies that BrowserPool operates as a true thread-safe Singleton, returning
    the exact same instance identity across calls.
    """
    pool1 = BrowserPool.get_instance()
    pool2 = BrowserPool()
    assert pool1 is pool2


@pytest.mark.asyncio
async def test_browser_pool_lifecycle():
    """
    Verifies that get_browser creates a single browser instance and close cleanly tears it down.
    """
    pool = BrowserPool()
    
    mock_browser = AsyncMock()
    mock_playwright = AsyncMock()
    mock_playwright.chromium.launch.return_value = mock_browser
    
    with patch("utils.browser_pool.PLAYWRIGHT_AVAILABLE", True), \
         patch("utils.browser_pool.async_playwright") as mock_ap, \
         patch("modules.renderer.SSRFLocalProxy") as mock_proxy:
        
        mock_manager = AsyncMock()
        mock_manager.start = AsyncMock(return_value=mock_playwright)
        mock_ap.return_value = mock_manager
        mock_proxy_instance = AsyncMock()
        mock_proxy_instance.get_proxy_url = Mock(return_value="http://127.0.0.1:8080")
        mock_proxy.return_value = mock_proxy_instance
        
        # Invoke get_browser
        browser = await pool.get_browser()
        assert browser is mock_browser
        
        # Second call should immediately return the existing browser without relaunching
        browser2 = await pool.get_browser()
        assert browser2 is mock_browser
        mock_playwright.chromium.launch.assert_called_once()
        
        # Clean up
        await pool.close()
        assert pool.browser is None
        mock_browser.close.assert_called_once()
        mock_playwright.stop.assert_called_once()
        mock_proxy_instance.stop.assert_called_once()
