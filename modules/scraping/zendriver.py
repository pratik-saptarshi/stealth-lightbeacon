"""
zendriver.py — Advanced heavy-path anti-detect scraping engine utilizing Playwright Chromium.
Emulates human interactions and overrides standard bot detection fingerprints.
"""

import logging
from modules.scraping.base import ScrapingEngine
from utils.ssrf_guard import SSRFGuard

# --- Try Playwright Imports ---
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

logger = logging.getLogger("zendriver")

class ZendriverEngine(ScrapingEngine):
    """
    Heavy-path anti-detect Chromium scraper that bypasses advanced zero-day fingerprint rules.
    """
    def __init__(self, timeout_ms: int = 30000, allow_private: bool = False):
        self.timeout_ms = timeout_ms
        self.allow_private = allow_private
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)

    async def scrape(self, url: str) -> str:
        """
        Launches Playwright Chromium with anti-fingerprint overrides and scraping actions.
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Zendriver engine requires the 'playwright' package.\n"
                "To install it, run: pip install playwright && playwright install"
            )

        # 1. Pre-fetch SSRF validation
        await self.ssrf_guard.validate(url)

        async with async_playwright() as p:
            # Emulate full screen, system fonts, and bypass WebDriver identification
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--no-sandbox",
                    "--window-size=1920,1080"
                ]
            )
            try:
                context = await browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    accept_downloads=False,
                    color_scheme="dark",
                    device_scale_factor=1,
                    has_touch=False,
                    is_mobile=False,
                    locale="en-US",
                    timezone_id="America/New_York"
                )
                
                # Bypassing webdriver detection scripts
                await context.add_init_script("""
                    // Override webdriver flag
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });

                    // Emulate standard plugins list length
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [1, 2, 3, 4, 5]
                    });

                    // Emulate standard chrome runtime interface
                    window.chrome = {
                        runtime: {}
                    };

                    // WebGL Fingerprint Spoofing
                    const getParameter = WebGLRenderingContext.prototype.getParameter;
                    WebGLRenderingContext.prototype.getParameter = function(parameter) {
                        // UNMASKED_VENDOR_WEBGL
                        if (parameter === 37445) {
                            return 'Intel Open Source Technology Center';
                        }
                        // UNMASKED_RENDERER_WEBGL
                        if (parameter === 37446) {
                            return 'Mesa DRI Intel(R) HD Graphics 520 (Skylake GT2)';
                        }
                        return getParameter.apply(this, arguments);
                    };
                """)

                page = await context.new_page()
                
                # Navigate and wait for content
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
                
                # 2. Post-navigation redirect SSRF validation
                await self.ssrf_guard.validate(page.url)

                # Fetch fully evaluated dynamic DOM content
                html_content = await page.content()
                return html_content
            finally:
                await browser.close()
