"""
browser_pool.py — Shared thread-safe BrowserPool singleton managing a persistent headless Chromium lifecycle.
"""

import asyncio
import logging
from typing import Optional

logger = logging.getLogger("browser_pool")

try:
    from playwright.async_api import async_playwright, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    async_playwright = None
    PLAYWRIGHT_AVAILABLE = False
    Browser = None


class BrowserPool:
    """
    Thread-safe Singleton BrowserPool managing headless Playwright Chromium and associated SSRF proxy instances.
    """
    _instance: Optional['BrowserPool'] = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(BrowserPool, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.browser: Optional[Browser] = None
        self.playwright = None
        self.proxy = None
        self.init_lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'BrowserPool':
        if not cls._instance:
            cls._instance = BrowserPool()
        return cls._instance

    async def get_browser(self) -> Browser:
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError(
                "Playwright is not installed. Rendered mode requires the 'playwright' package."
            )

        async with self.init_lock:
            if self.browser:
                return self.browser

            from utils.ssrf_guard import SSRFGuard
            from modules.renderer import SSRFLocalProxy

            guard = SSRFGuard(allow_private=False)
            self.proxy = SSRFLocalProxy(guard)
            await self.proxy.start()

            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    f"--proxy-server={self.proxy.get_proxy_url()}",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-infobars",
                    "--disable-setuid-sandbox",
                ]
            )
            return self.browser

    async def close(self) -> None:
        async with self.init_lock:
            if self.browser:
                try:
                    await self.browser.close()
                except Exception:
                    pass
                self.browser = None
            if self.playwright:
                try:
                    await self.playwright.stop()
                except Exception:
                    pass
                self.playwright = None
            if self.proxy:
                try:
                    await self.proxy.stop()
                except Exception:
                    pass
                self.proxy = None
