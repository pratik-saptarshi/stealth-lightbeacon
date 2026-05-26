# utils/

## Responsibility
Support the audit engine with shared infrastructure for vectorization, storage,
diffing, browser lifecycle, SSRF protection, selector repair, recon, budgets,
workspace watching, and BOM maintenance.

## Design / patterns

- Small single-purpose modules with minimal shared state.
- Backend fallbacks are built in where possible:
  - `OntologyStore` uses DuckDB + LanceDB when available, otherwise in-memory mocks.
  - `BrowserPool` is a singleton guarded by an `asyncio.Lock`.
  - `SSRFGuard` pins safe host resolutions before HTTP connection setup.
- Heuristic helpers favor lightweight runtime decisions:
  - `ReconAdvisor` maps anti-bot signals to a scraping posture.
  - `SelectorResolver` retries exact lookup first, then fuzzy repair.
  - `WorkspaceWatcher` polls and debounces filesystem changes.
- Utility functions stay deterministic where possible, especially the JS-compatible
  `make_vector()` hashing path.

## Data & control flow

- `utils/vector.py` turns text into normalized hashed vectors used by semantic
  storage and search.
- `utils/ontology.py` persists runs/pages/findings in DuckDB tables, buffers vector
  rows, flushes them to LanceDB or the fallback store, and exposes `get_run_report()`,
  `diff_runs()`, `search()`, and `health()`.
- `utils/crawl_diff.py` normalizes two report payloads and returns score deltas,
  added/removed domains, regressions, improvements, and issue-id churn; the async
  wrapper can load reports from `OntologyStore` or raw SQL rows.
- `utils/ssrf_guard.py` resolves hosts, blocks private/loopback/reserved targets,
  and plugs a pinned network backend into `httpx/httpcore`.
- `utils/browser_pool.py` starts SSRF-protected Playwright Chromium once and reuses
  it for later calls until `close()`.
- `utils/recon.py` issues a probe request with `httpx`, scans headers/body for
  anti-bot markers, and returns a recommended engine/posture.
- `utils/selector_resolver.py` caches resolved selectors, tries exact parser lookups,
  and falls back to a scored candidate match.
- `utils/budget_validator.py` inspects the `PageSpeed & Performance` evaluation
  result for LCP, CLS, INP, TTFB, and score thresholds.
- `utils/update_bom.py` parses `requirements.txt` and rewrites the BOM block between
  comment anchors.
- `utils/agent_card.py` returns a static orchestration manifest for the CLI entrypoint
  and supported audit/output metadata.
- `utils/watcher.py` scans the workspace tree, tracks mtimes for `.py`, `.toml`, and
  `.md` files, and triggers a sync after debounce.

## Integration points

- `modules.base` provides `EvaluationResult` for budget validation and ontology
  reporting.
- `report.formats` supplies the canonical report normalizer used by diffing and
  persistence.
- `modules.renderer.SSRFLocalProxy`, `httpx`, `httpcore`, and `playwright` are used
  by the SSRF/browser stack.
- `duckdb` and `lancedb` are optional persistence/search backends.
- `config` supplies request timeouts and headers for recon.
- `bill-of-material.md` and `requirements.txt` are the BOM update targets.
