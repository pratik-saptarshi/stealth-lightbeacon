# CLI Readme

This repository exposes one primary command: `python main.py evaluate`.

## Quick Start

```bash
python main.py evaluate "https://example.com"
```

Common examples:

```bash
python main.py evaluate "https://example.com" --crawl-depth 2 --max-urls 10
python main.py evaluate "https://example.com" --render --engine stealth
python main.py evaluate "https://example.com" --format html --out reports/
python main.py evaluate "https://example.com" --check-links --check-api
python main.py evaluate --watch
python main.py evaluate --search-semantic "broken link audit"
```

## Options

| Flag | Default | Description |
|---|---|---|
| `URL` | required | Target site to evaluate unless `--watch` or `--search-semantic` is used. |
| `--out`, `-o` | `reports/` | Output directory for JSON and HTML reports. |
| `--format`, `-f` | `both` | Report format: `json`, `html`, or `both`. |
| `--allow-private` | `false` | Permit scans of private or loopback IPs. |
| `--crawl-depth`, `-d` | `0` | Crawl depth for recursive discovery. |
| `--max-urls`, `-n` | `10` | Maximum number of URLs to crawl. |
| `--render` | `false` | Use Playwright-backed rendered auditing. |
| `--http2` | `false` | Enable HTTP/2 for outgoing requests. |
| `--engine` | `http` | Scraping engine: `http`, `fast`, `stealth`, or `mcp`. |
| `--budget` | unset | JSON budget file for performance threshold enforcement. |
| `--check-links` | `false` | Scan outbound and same-domain links for broken targets. |
| `--check-api` | `false` | Probe common Drupal REST and JSON:API routes. |
| `--persist` | `false` | Store runs and findings in DuckDB and LanceDB. |
| `--watch` | `false` | Start the workspace watcher loop instead of evaluating a URL. |
| `--search-semantic` | unset | Search historical audit data using semantic similarity. |

## Output

- JSON reports are written to `reports/report.json` unless `--out` overrides the directory.
- HTML reports are written to `reports/report.html` unless `--out` overrides the directory.
- Console output includes a domain score table and a detailed issue log.

## Setup Notes

Install dependencies with the live index so the pinned set resolves the same way CI does:

```bash
pip install -r requirements.txt --extra-index-url https://pypi.org/simple
python -m pip install pip-tools
pre-commit run dependency-validation --all-files
```
