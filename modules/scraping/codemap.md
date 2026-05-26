# modules/scraping/

## Responsibility
Pluggable HTML acquisition layer for the crawler and renderer stack. It
provides fast, stealth, and protocol-driven scrapers that all return raw HTML
strings.

## Design / patterns

- `ScrapingEngine` is the abstract strategy contract; `ScrapingFactory` picks
  an implementation from CLI/config input.
- Every engine validates targets with `SSRFGuard` before fetch and again after
  redirects/final navigation.
- Engines stay async and do not parse HTML; parsing is deferred to `modules/*`
  evaluators.
- `StealthMcpLayer` wraps a JSON-RPC subprocess and falls back to
  `ObscuraEngine` on protocol failure.
- `ZendriverEngine` and `ObscuraEngine` both use browser-like fingerprints or
  spoofed headers when they are not using their primary path.

## Data & control flow

- `ScrapingFactory.get_engine()` normalizes `engine_type` and maps `fast`,
  `stealth`, and `mcp` to their respective engines; everything else falls back
  to `ObscuraEngine`.
- `ObscuraEngine.scrape()` tries `bin/obscura --dump html <url>` first, then
  switches to `httpx.AsyncClient` with spoofed headers and HTTP/2.
- `ZendriverEngine.scrape()` launches headless Chromium, injects anti-fingerprint
  scripts, waits for network idle, validates the final URL, and returns
  `page.content()`.
- `StealthMcpLayer.scrape()` starts the configured MCP process, performs the
  initialize/navigate/evaluate/close sequence, and returns the DOM HTML.

## Integration points

- Exported through `modules/scraping/__init__.py` for direct imports.
- Consumed by `main.py` through `ScrapingFactory` when crawl/render mode needs
  a pluggable scraper.
- Configured by `config` values for MCP command, args, and timeout budgets.
- Shares SSRF policy code with the renderer and evaluator modules via
  `utils.ssrf_guard`.
