"""
conftest.py — Pytest configuration and shared mock fixtures.
"""

import pytest
import asyncio
from typing import Generator

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Creates an instance of the default event loop for the test session.
    """
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_html_valid() -> str:
    """
    Returns a valid mock HTML page with canonical tags, metadata, structured JSON-LD,
    correct headings, accessible image descriptions, and ARIA components.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Acme Widgets | High Quality Drupal Widgets</title>
  <meta name="description" content="Discover the best high-quality Drupal widgets at Acme Widgets. Standard compliance, excellent durability, and modern engineering design.">
  <link rel="canonical" href="https://example.com/acme-widgets">
  <meta name="robots" content="index, follow">
  <meta property="og:title" content="Acme Widgets | Drupal Widgets">
  <meta property="og:description" content="Discover the best high-quality Drupal widgets at Acme Widgets.">
  <meta property="og:type" content="website">
  
  <script type="application/ld+json">
  {
    "@context": "https://schema.org",
    "@type": "WebSite",
    "name": "Acme Widgets",
    "url": "https://example.com"
  }
  </script>
</head>
<body>
  <h1>Acme Widgets and Accessories</h1>
  <p>Welcome to Acme Widgets, the leading supplier of Drupal modules and accessories.</p>
  
  <h2>Our Best Sellers</h2>
  <img src="images/widget1.jpg" alt="Acme Blue Widget model A-100" width="300" height="200" loading="lazy">
  
  <h3>Customer FAQ</h3>
  <div class="faq-item">
    <h4>What is the return policy?</h4>
    <p>We offer a 30-day money-back guarantee on all our widgets and custom modules.</p>
  </div>
</body>
</html>
"""

@pytest.fixture
def mock_html_invalid() -> str:
    """
    Returns an invalid HTML page containing standard SEO, accessibility, and hierarchy issues
    (missing canonical, multiple h1 tags, missing image alt tag, incorrect metadata, empty head).
    """
    return """<!DOCTYPE html>
<html>
<head>
  <!-- Missing charset and viewport -->
  <title>Stale Page</title>
  <!-- Missing description -->
  <!-- Missing canonical -->
  <meta name="robots" content="noindex, nofollow">
</head>
<body>
  <h1>First Main Heading</h1>
  <h1>Second Main Heading (Error: multiple H1s)</h1>
  
  <h4>Out of order heading level (Error: jumps from H1 to H4)</h4>
  
  <p>This is a poorly designed page with major accessibility and SEO issues.</p>
  
  <!-- Accessibility error: missing alt attribute -->
  <img src="images/bad.jpg">
  
  <!-- Accessibility error: empty interactive element -->
  <a href="/click" role="button"></a>
</body>
</html>
"""
