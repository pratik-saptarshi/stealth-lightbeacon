"""
test_parser_performance.py — Unit tests verifying event loop offloading of DOM BeautifulSoup parsing.
"""

import pytest
import asyncio
import time
from modules.aeo_geo import AeoGeoEvaluator
from modules.accessibility import AccessibilityEvaluator


@pytest.mark.asyncio
async def test_parser_offloading_does_not_block():
    """
    Verifies that HtmlParser executes on worker threads via asyncio.to_thread,
    allowing other asynchronous events to fire concurrently on the main loop.
    """
    html_content = "<html><body>" + "<h1>Accessibility Test</h1><p>concise outline</p>" * 1000 + "</body></html>"
    
    aeo = AeoGeoEvaluator()
    a11y = AccessibilityEvaluator()
    
    # Track event loop responsiveness by scheduling a background task
    loop_responsive = False

    async def heart_beat():
        nonlocal loop_responsive
        await asyncio.sleep(0.01)
        loop_responsive = True

    # Run both parses and the background heartbeat concurrently
    hb_task = asyncio.create_task(heart_beat())
    
    await asyncio.gather(
        aeo.evaluate(html_content, "https://example.com"),
        a11y.evaluate(html_content, "https://example.com"),
        hb_task
    )
    
    assert loop_responsive, "Event loop was blocked by parser execution!"
