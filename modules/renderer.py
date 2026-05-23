"""
renderer.py — Asynchronous HTML renderer using headless Playwright (Chromium).
Allows evaluation of modern JavaScript-heavy single page applications (SPAs).
"""

import logging

logger = logging.getLogger("renderer")

# --- Try Playwright Imports ---
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class PlaywrightRenderer:
    """
    Renders dynamic web pages using headless Playwright Chromium.
    """
    def __init__(self, timeout_ms: int = 30000):
        self.timeout_ms = timeout_ms

    async def render(self, url: str) -> str:
        """
        Launches a headless browser, navigates to the URL, waits for network idle,
        and returns the fully rendered DOM HTML content.
        Validates target URLs and final redirected destinations against SSRF violations.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Rendered mode requires the 'playwright' package.\n"
                "To install it, run: pip install playwright && playwright install"
            )
            
        from utils.ssrf_guard import SSRFGuard
        guard = SSRFGuard(allow_private=False)
        # 1. Pre-browser launch SSRF validation
        await guard.validate(url)
            
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 DrupalEvaluator/1.0"
                )
                page = await context.new_page()
                
                # Navigate and wait until network is completely idle
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                
                # 2. Post-navigation redirect SSRF validation
                await guard.validate(page.url)
                
                # Return fully rendered DOM HTML
                html_content = await page.content()
                return html_content
            finally:
                await browser.close()
