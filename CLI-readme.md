# CLI Readme

This repository exposes one primary command: `python main.py evaluate`.

The runtime identity and docs surface are aligned with the `v1.2.5` release train.

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

## Public Audit Wrapper

Use the wrapper script for the public audit flow with the repo defaults.

```bash
./scripts/run_public_audit.sh
TARGET=www.example.com ./scripts/run_public_audit.sh
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
- `SLB_MCP_COMMAND`: pinned MCP executable or package command for `--engine mcp`.
- `SLB_MCP_ARGS`: additional args for the pinned MCP command.
- `SLB_MCP_HANDSHAKE_TIMEOUT`: timeout in seconds for the MCP handshake.
- `SLB_MCP_TOOL_TIMEOUT`: timeout in seconds for MCP tool calls and I/O drains.
- `SLB_MCP_SHUTDOWN_TIMEOUT`: timeout in seconds for MCP process shutdown.

When `--engine mcp` is selected, startup diagnostics print the resolved command,
arguments, and timeout budgets so the pinned runtime is observable at launch.

Recipe templates are checked in under `ci-recipes/` for GitHub Actions, GitLab CI, and Bitbucket Pipelines, and they rely on those variables as the CI contract.

`--engine mcp` requires a pinned executable or versioned package. The mutable
`npx -y @modelcontextprotocol/server-playwright` download path is disabled.

## Exit Codes

- `0`: successful evaluation and report generation.
- `1`: validation, fetch, SSRF, or configuration failure.
- `2`: performance budget violation when `--budget` is supplied.

## Output Artifacts

| `--format` | Primary artifact | Notes |
|---|---|---|
| `json` | `reports/report.json` | Canonical machine-readable payload. |
| `html` | `reports/report.html` | Rich interactive report. |
| `llm` | `reports/report.md` | Markdown summary for agents and LLMs. |
| `geo-xml` | `reports/report.xml` | GEO-style XML output. |
| `both` | `reports/report.json` + `reports/report.html` | Default dual-output mode. |

CI recipes archive both `reports/report.json` and `reports/report.html` when
the dual-output mode is used.

## Release Notes

- The `v1.2.5` release publishes the canonical HTTP service, contract validator, and end-to-end smoke coverage alongside the CLI.
- The canonical release history lives in `changelog.md`.

## Shared Axioms

Use [shared-axioms.md](shared-axioms.md) as the cross-repo boundary contract
for the backend, desktop, and browser-addon repos. It records which repo owns
which semantics and which validation gate must protect each boundary.

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
