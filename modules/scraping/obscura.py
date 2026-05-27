"""
obscura.py — Fast-path scraping engine executing a compiled static Rust binary asset.
Falls back to high-performance client with customized TLS/HTTP fingerprints if binary is missing.
"""

import os
import asyncio
import logging
import httpx
from typing import Optional
from modules.scraping.base import ScrapingEngine
from utils.ssrf_guard import SSRFGuard

logger = logging.getLogger("obscura")

class ObscuraEngine(ScrapingEngine):
    """
    Fast-path engine executing a hermetic static Rust binary, falling back to TLS/HTTP fingerprint spoofing.
    """
    def __init__(self, binary_path: str = "bin/obscura", allow_private: bool = False):
        self.binary_path = binary_path
        self.allow_private = allow_private
        self.ssrf_guard = SSRFGuard(allow_private=allow_private)

    async def scrape(self, url: str) -> str:
        """
        Runs the static binary or handles the customized TLS spoofing fallback.
        """
        # Validate SSRF safety
        await self.ssrf_guard.validate(url)

        if os.path.exists(self.binary_path) and os.path.isfile(self.binary_path):
            try:
                logger.info(f"Executing fast-path static Rust binary: {self.binary_path} --dump html {url}")
                # Run the static Rust binary as a subprocess
                process = await asyncio.create_subprocess_exec(
                    self.binary_path,
                    "--dump", "html",
                    url,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    return stdout.decode("utf-8")
                else:
                    logger.warning(f"Obscura binary exited with error: {stderr.decode('utf-8')}")
            except Exception as e:
                logger.error(f"Failed to execute Obscura Rust binary: {str(e)}")

        # Fallback mode: specialized spoofed browser headers/concurrency rules
        logger.info("Executing Obscura specialized browser-spoofing client fallback...")
        spoofed_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Linux"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        
        async with httpx.AsyncClient(timeout=15, headers=spoofed_headers, follow_redirects=True, http2=False) as client:
            response = await client.get(url)
            # Post-redirect SSRF guard validation
            await self.ssrf_guard.validate(str(response.url))
            response.raise_for_status()
            return response.text
