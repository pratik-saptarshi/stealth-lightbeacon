# ci-recipes/github-actions/

## Responsibility
Manual GitHub Actions audit workflow. It exposes a `workflow_dispatch` entry
point so operators can supply a required target URL and optional evaluator
subset, then run the audit on `ubuntu-latest`.

## Design
Single `audit` job with checkout, Python 3.11 setup, dependency install, CLI
execution, and artifact upload. The workflow maps dispatcher inputs directly
into env vars and keeps the pipeline intentionally flat.

## Data & control flow

`inputs.target_url` and `inputs.audits` become `SLB_TARGET_URL` and
`SLB_AUDITS`; `secrets.SLB_AUTH_TOKEN` becomes `SLB_AUTH_TOKEN`. The job sets
`SLB_FAIL_ON_CRITICAL=1`, runs `python main.py evaluate --format both --out
reports`, and uploads `reports/report.json` as `stealth-lightbeacon-report`.

## Integration points

GitHub Actions dispatcher inputs, repository secrets, `actions/checkout`,
`actions/setup-python`, `actions/upload-artifact`, and the CLI in `main.py`.
