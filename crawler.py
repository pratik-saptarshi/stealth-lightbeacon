"""
crawler.py — High-performance asynchronous recursive web crawler.
Performs domain-bounded link discovery, depth limits, and max-URL circuit-breaker guards.
"""

import asyncio
from urllib.parse import urlparse, urljoin
from typing import Dict, Set, List, Tuple, Optional, Any
import httpx
from modules.html_parser import HtmlParser

class Crawler:
    """
    Crawls pages asynchronously within the same domain up to a maximum depth and maximum URL count.
    """
    def __init__(
        self,
        start_url: str,
        max_depth: int = 1,
        max_urls: int = 10,
        allow_private: bool = False,
        rate_delay: float = 0.2,
        max_concurrent: int = 5
    ):
        self.start_url = start_url
        self.max_depth = max_depth
        self.max_urls = max_urls
        self.allow_private = allow_private
        self.rate_delay = rate_delay
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.broken_links: Dict[str, int] = {}
        
        parsed = urlparse(start_url)
        self.target_netloc = parsed.netloc
        self.target_scheme = parsed.scheme

    def extract_links(self, html: str, current_url: str) -> List[str]:
        """
        Extracts same-domain hyperlinks from the page HTML content and normalizes them.
        """
        parser = HtmlParser(html)
        links = []
        
        for anchor in parser.find_all("a", href=True):
            href = anchor.get("href", "").strip()
            
            # Skip anchors, query fragments, javascript calls
            if not href or href.startswith("#") or href.lower().startswith("javascript:"):
                continue
                
            # Convert relative URL to absolute URL
            absolute_url = urljoin(current_url, href)
            parsed_abs = urlparse(absolute_url)
            
            # Exclude non-http schemes (mailto, tel, etc.)
            if parsed_abs.scheme not in ["http", "https"]:
                continue
                
            # Enforce same-domain boundary constraint
            if parsed_abs.netloc == self.target_netloc:
                # Strip fragments to normalize URLs
                normalized_url = absolute_url.split("#")[0]
                links.append(normalized_url)
                
        return list(set(links))

    async def crawl(self, client: httpx.AsyncClient, renderer: Optional[Any] = None) -> Dict[str, str]:
        """
        Executes the recursive crawling loop asynchronously using a queue structure.
        Optionally uses PlaywrightRenderer to fetch and render JavaScript-heavy DOMs.
        Returns a dictionary mapping crawled URLs to their fetched HTML string content.
        """
        from utils.ssrf_guard import SSRFGuard, SSRFViolationError

        visited_content: Dict[str, str] = {}
        queue: asyncio.Queue[Tuple[str, int]] = asyncio.Queue()
        guard = SSRFGuard(allow_private=self.allow_private)
        
        # Enqueue start URL at depth 0
        await queue.put((self.start_url, 0))
        visited_urls: Set[str] = {self.start_url}
        
        while not queue.empty():
            # Check circuit breaker before pulling new work
            if len(visited_content) >= self.max_urls:
                break
                
            url, depth = await queue.get()
            
            # Rate limiting
            if self.rate_delay > 0:
                await asyncio.sleep(self.rate_delay)
                
            async with self.semaphore:
                try:
                    # 1. Pre-fetch SSRF Guard validation
                    await guard.validate(url)
                    
                    # 2. Fetch page HTML
                    if renderer:
                        if hasattr(renderer, "scrape"):
                            html = await renderer.scrape(url)
                        else:
                            html = await renderer.render(url)
                        final_url = url
                    else:
                        response = await client.get(url, follow_redirects=True)
                        if response.status_code != 200:
                            self.broken_links[url] = response.status_code
                            queue.task_done()
                            continue
                        html = response.text
                        final_url = str(response.url)
                    
                    # 3. Post-redirect SSRF Guard validation
                    await guard.validate(final_url)
                    
                    # 4. Double-check domain of final URL
                    parsed_final = urlparse(final_url)
                    if parsed_final.netloc != self.target_netloc:
                        queue.task_done()
                        continue
                        
                    # Save only final canonical URL to prevent duplicates on redirect
                    visited_content[final_url] = html
                    
                    # Check circuit breaker and depth limit before discovering child links
                    if len(visited_content) >= self.max_urls or depth >= self.max_depth:
                        queue.task_done()
                        continue
                        
                    # Discover links
                    discovered_links = self.extract_links(html, final_url)
                    for link in discovered_links:
                        if link not in visited_urls and len(visited_urls) < self.max_urls:
                            visited_urls.add(link)
                            await queue.put((link, depth + 1))
                except (SSRFViolationError, Exception):
                    pass  # Ignore SSRF violations or network errors on individual pages during crawl
                    
            queue.task_done()
            
        return visited_content
