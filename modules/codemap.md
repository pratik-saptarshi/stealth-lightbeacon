# modules/

## Responsibility
Shared evaluation layer for the CLI: contracts, DOM adapters, cache/render
helpers, and domain evaluators for SEO, accessibility, performance, UX,
Drupal/security, and AEO/GEO.

## Design / patterns

- `BaseEvaluator` defines the async `evaluate()` contract; each evaluator
  returns frozen `EvaluationResult`/`Issue` dataclasses.
- `HtmlParser` wraps BeautifulSoup/Selectolax behind one search API and uses
  selector repair when direct lookups miss.
- `AsyncCache` isolates PSI persistence in SQLite with executor-based async
  reads/writes.
- `PlaywrightRenderer` and `SSRFLocalProxy` handle dynamic rendering with
  SSRF-aware network interception.
- Evaluators are signal-based: they score independent checks, collect issues,
  and attach lightweight metadata for reporting.

## Data & control flow

- `main.py` selects evaluators, fetches or renders HTML, then runs
  `evaluate()` coroutines concurrently with a shared `httpx.AsyncClient`.
- Static evaluators inspect the DOM only; networked evaluators fetch headers,
  robots.txt, PSI JSON, or Drupal JSON:API and validate outbound requests with
  `utils.ssrf_guard`.
- `PagespeedEvaluator` reads cache first, retries PSI on miss, then stores the
  raw PSI payload back into SQLite.
- Results flow back as `EvaluationResult` objects; `main.py` rewrites issue
  locations with the page path before report generation.

## Integration points

- Imported by `main.py`, `crawler.py`, `report/formats.py`, and
  `report/generator.py`.
- Depends on `config` for thresholds, PSI endpoints, severity labels, and
  output paths.
- Depends on `utils.selector_resolver` for parser fallback logic and
  `utils.ssrf_guard` for outbound validation.
- Covered by evaluator-specific unit and integration tests in `tests/`.
