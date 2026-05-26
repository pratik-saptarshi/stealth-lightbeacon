# report/

## Responsibility
Normalize audit results into a stable payload and render them into consumer-facing
report formats. `report/formats.py` is the canonical payload layer; `report/generator.py`
builds the HTML dashboard.

## Design / patterns

- Payload-first design: `target_url`, `average_score`, `total_issues`, and `domains`
  are normalized before any rendering.
- Compatibility shim: the normalizer accepts legacy keys such as `targetUrl`,
  `averageScore`, `totalIssues`, and `domain`.
- Pure render helpers: JSON, LLM markdown, and GEO XML are format transforms over
  the same normalized payload.
- Embedded HTML template: `ReportGenerator` keeps a Jinja2 template string in code
  and renders with autoescape enabled.

## Data & control flow

- `modules.base.EvaluationResult` / `Issue` objects are converted into dicts by
  `build_report_payload()`.
- `normalize_report_payload()` coerces mixed input into the shared schema and
  derives summary fields when they are missing.
- `render_report_format()` dispatches by lowercased format name:
  - `json` -> `json.dumps(...)`
  - `llm` -> markdown summary
  - `geo-xml` -> XML tree serialization
- `ReportGenerator.generate_report(url, results, output_dir)` computes the average
  score and issue count, builds Jinja2 context, renders `report.html`, and writes it
  to disk. It currently does not emit a JSON file despite the docstring.

## Integration points

- `modules.base` supplies `EvaluationResult` and `Issue`.
- `utils.crawl_diff` and `utils.ontology` consume the normalized payload shape.
- `jinja2` handles HTML rendering; `xml.etree.ElementTree` handles GEO XML output.
- `os` and `json` are used for filesystem output and serialization.
