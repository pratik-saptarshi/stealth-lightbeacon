"""Real Playwright E2E smoke test against a local fixture page."""

from __future__ import annotations

from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread

import pytest

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - environment dependent
    sync_playwright = None
    PlaywrightError = Exception


def _write_fixture(root: Path) -> None:
    (root / "index.html").write_text(
        """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Stealth Lightbeacon E2E Fixture</title>
  </head>
  <body>
    <main>
      <h1 id="hero-title">Smoke Fixture Ready</h1>
      <p data-testid="status">local-fixture-ok</p>
    </main>
  </body>
</html>
""",
        encoding="utf-8",
    )


@contextmanager
def _serve_fixture_site() -> str:
    with TemporaryDirectory(prefix="slb-e2e-fixture-") as tmpdir:
        root = Path(tmpdir)
        _write_fixture(root)
        handler = partial(SimpleHTTPRequestHandler, directory=str(root))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        host, port = server.server_address
        try:
            yield f"http://{host}:{port}/index.html"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


@pytest.mark.e2e
@pytest.mark.skipif(sync_playwright is None, reason="Playwright is not installed.")
def test_playwright_local_fixture_smoke() -> None:
    with _serve_fixture_site() as fixture_url:
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(fixture_url, wait_until="domcontentloaded")
                assert page.locator("#hero-title").inner_text() == "Smoke Fixture Ready"
                assert page.locator('[data-testid="status"]').inner_text() == "local-fixture-ok"
                browser.close()
        except PlaywrightError as exc:  # pragma: no cover - environment dependent
            pytest.skip(f"Playwright/browser unavailable in this environment: {exc}")
