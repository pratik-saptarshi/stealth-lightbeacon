# ci-recipes/

## Responsibility
CI recipe examples for running Stealth Lightbeacon audits in external
providers. Each recipe provisions Python 3.11, installs repo requirements,
invokes `python main.py evaluate --format both --out reports`, and preserves
the generated audit report artifact.

## Design
Provider-specific, single-job pipelines with minimal orchestration. Runtime
behavior is controlled through environment variables and CI secrets rather
than custom wrapper scripts. The recipes standardize on `SLB_FAIL_ON_CRITICAL=1`
so CI can fail when the evaluator emits critical findings.

## Data & control flow

CI injects the target URL, optional audit subset, and auth token into
`SLB_TARGET_URL`, `SLB_AUDITS`, and `SLB_AUTH_TOKEN`. The `evaluate` command
reads those settings, runs the crawler/evaluators, writes JSON and HTML output
under `reports/`, and can exit non-zero on critical issues. The recipes
archive `reports/report.json`.

## Integration points

`main.py` CLI entry point, repo `requirements.txt`, the report output path in
`config`, and each provider's artifact/secret mechanism.
