"""
renderer.py — Asynchronous HTML renderer using headless Playwright (Chromium).
Allows evaluation of modern JavaScript-heavy single page applications (SPAs).
"""

import logging
import inspect

logger = logging.getLogger("renderer")

# --- Try Playwright Imports ---
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

class SSRFLocalProxy:
    """
    Asynchronous secure local proxy that intercepts dynamic Playwright network traffic,
    validates outbound hosts against SSRF violations, and tunnels connections to DNS-pinned safe IPs.
    """
    def __init__(self, guard):
        self.guard = guard
        self.server = None
        self.port = None

    async def start(self) -> int:
        import asyncio
        self.server = await asyncio.start_server(
            self.handle_connection,
            '127.0.0.1',
            0
        )
        self.port = self.server.sockets[0].getsockname()[1]
        return self.port

    async def stop(self) -> None:
        if self.server:
            self.server.close()
            await self.server.wait_closed()

    def get_proxy_url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    async def handle_connection(self, reader, writer) -> None:
        import asyncio
        from urllib.parse import urlparse
        try:
            line = await reader.readline()
            if not line:
                writer.close()
                await writer.wait_closed()
                return

            parts = line.decode('utf-8', errors='ignore').split()
            if len(parts) < 2:
                writer.close()
                await writer.wait_closed()
                return

            method, target = parts[0], parts[1]

            if method.upper() == 'CONNECT':
                host_port = target.split(':')
                if len(host_port) == 2:
                    host, port_str = host_port[0], host_port[1]
                    port = int(port_str)
                else:
                    host = target
                    port = 443

                try:
                    await self.guard.validate(f"https://{host}:{port}")
                    pinned_ip = self.guard.get_pinned_address(host) or host
                    
                    server_reader, server_writer = await asyncio.open_connection(pinned_ip, port)
                    
                    writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    await writer.drain()

                    await asyncio.gather(
                        self.tunnel(reader, server_writer),
                        self.tunnel(server_reader, writer),
                        return_exceptions=True
                    )
                except Exception:
                    writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by SSRFGuard\r\n")
                    await writer.drain()
            else:
                parsed = urlparse(target)
                host = parsed.hostname
                port = parsed.port or (80 if parsed.scheme == 'http' else 443)
                if not host:
                    writer.close()
                    await writer.wait_closed()
                    return

                try:
                    await self.guard.validate(target)
                    pinned_ip = self.guard.get_pinned_address(host) or host
                    
                    server_reader, server_writer = await asyncio.open_connection(pinned_ip, port)
                    
                    path_query = parsed.path
                    if parsed.query:
                        path_query += "?" + parsed.query
                    if not path_query:
                        path_query = "/"
                        
                    new_line = f"{method} {path_query} {parts[2]}\r\n".encode('utf-8')
                    server_writer.write(new_line)
                    await server_writer.drain()

                    await asyncio.gather(
                        self.tunnel(reader, server_writer),
                        self.tunnel(server_reader, writer),
                        return_exceptions=True
                    )
                except Exception:
                    writer.write(b"HTTP/1.1 403 Forbidden\r\n\r\nBlocked by SSRFGuard\r\n")
                    await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass

    async def tunnel(self, reader, writer) -> None:
        try:
            while True:
                data = await reader.read(8192)
                if not data:
                    break
                writer.write(data)
                await writer.drain()
        except Exception:
            pass
        finally:
            try:
                writer.close()
            except Exception:
                pass


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
            
        from utils.browser_pool import BrowserPool
        pool = BrowserPool.get_instance()
        browser = await pool.get_browser()

        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 DrupalEvaluator/1.0"
        )
        try:
            page = await context.new_page()
            
            # Navigate and wait until network is completely idle
            await page.goto(url, wait_until="networkidle")
            
            # 2. Post-navigation redirect SSRF validation
            final_url = page.url
            if inspect.isawaitable(final_url):
                final_url = await final_url
            if not isinstance(final_url, str):
                final_url = url
            await guard.validate(final_url)
            
            # Return fully rendered DOM HTML
            html_content = await page.content()
            return html_content
        finally:
            await context.close()
