"""
test_playwright_renderer.py — Unit tests for the Playwright Renderer.
"""

import pytest
from unittest.mock import AsyncMock, patch

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

from modules.renderer import PlaywrightRenderer

@pytest.mark.skipif(not PLAYWRIGHT_AVAILABLE, reason="Playwright is not installed in the environment.")
@pytest.mark.asyncio
async def test_playwright_renderer_success():
    """
    Verifies that PlaywrightRenderer successfully retrieves page HTML in rendered mode.
    """
    renderer = PlaywrightRenderer()
    
    # We mock playwright to avoid spawning actual headless browsers during tests
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    
    mock_browser.new_context.return_value = mock_context
    mock_context.new_page.return_value = mock_page
    mock_page.content.return_value = "<html><body><h1>Rendered by Playwright</h1></body></html>"
    
    with patch("utils.browser_pool.BrowserPool.get_instance") as mock_gp:
        mock_pool = AsyncMock()
        mock_pool.get_browser.return_value = mock_browser
        mock_gp.return_value = mock_pool
        
        html = await renderer.render("https://example.com/dynamic-js")
        
    assert "Rendered by Playwright" in html
    mock_page.goto.assert_called_with("https://example.com/dynamic-js", wait_until="networkidle")
