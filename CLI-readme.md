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
python main.py evaluate "https://example.com" --format llm --out reports/
python main.py evaluate "https://example.com" --format geo-xml --out reports/
python main.py evaluate "https://example.com" --recon --recon-auto
python main.py evaluate "https://example.com" --check-links --check-api
python main.py evaluate "https://example.com" --audits security,performance --fail-on-critical
python main.py evaluate --watch
python main.py evaluate --search-semantic "broken link audit"
```

## Options

| Flag | Default | Description |
|---|---|---|
| `URL` | required | Target site to evaluate unless `--watch` or `--search-semantic` is used. |
| `--out`, `-o` | `reports/` | Output directory for generated report artifacts. |
| `--format`, `-f` | `both` | Report format: `json`, `html`, `both`, `llm`, or `geo-xml`. |
| `--audits` | unset | Comma-separated evaluator subset such as `security,performance`. |
| `--fail-on-critical` | `false` | Exit with code 1 when any critical finding is present. |
| `--allow-private` | `false` | Permit scans of private or loopback IPs. |
| `--crawl-depth`, `-d` | `0` | Crawl depth for recursive discovery. |
| `--max-urls`, `-n` | `10` | Maximum number of URLs to crawl. |
| `--render` | `false` | Use Playwright-backed rendered auditing. |
| `--recon` | `false` | Run advisory reconnaissance before crawling. |
| `--recon-auto` | `false` | Apply the recon-recommended scraper posture automatically. |
| `--http2` | `false` | Enable HTTP/2 for outgoing requests. |
| `--engine` | `http` | Scraping engine: `http`, `fast`, `stealth`, or `mcp`. |
| `--check-links` | `false` | Scan outbound and same-domain links for broken targets. |
| `--check-api` | `false` | Probe common Drupal REST and JSON:API routes. |
| `--persist` | `false` | Store runs and findings in DuckDB and LanceDB. |
| `--budget` | unset | JSON performance budget file for post-audit thresholds. |
| `--watch` | `false` | Start the workspace watcher loop instead of evaluating a URL. |
| `--search-semantic` | unset | Search historical audit data using semantic similarity. |

## Environment Variables

The CLI also reads these environment variables for CI workflows:

- `SLB_TARGET_URL`: default target URL when no positional URL is supplied.
- `SLB_AUTH_TOKEN`: bearer token for authenticated CI runs.
- `SLB_AUDITS`: comma-separated evaluator subset used by CI recipes.
- `SLB_FAIL_ON_CRITICAL`: fail the job when any critical finding is present.
- `SLB_MCP_COMMAND`: required executable for `--engine mcp`.
- `SLB_MCP_ARGS`: optional argument list for MCP command invocation.
- `SLB_MCP_HANDSHAKE_TIMEOUT`: optional MCP timeout (seconds) for handshake/tool responses.

Recipe templates are checked in under `ci-recipes/` for GitHub Actions, GitLab CI, and Bitbucket Pipelines, and they rely on those variables as the CI contract.

## Output

- JSON reports are written to `reports/report.json` unless `--out` overrides the directory.
- HTML reports are written to `reports/report.html` unless `--out` overrides the directory.
- LLM-ready Markdown reports are written to `reports/report.md` unless `--out` overrides the directory.
- GEO XML reports are written to `reports/report.xml` unless `--out` overrides the directory.
- Console output includes a domain score table and a detailed issue log.

## Setup Notes

Install dependencies with the live index so the pinned set resolves the same way CI does:

```bash
pip install -r requirements.txt --extra-index-url https://pypi.org/simple
python -m pip install pip-tools
pre-commit run dependency-validation --all-files
```
