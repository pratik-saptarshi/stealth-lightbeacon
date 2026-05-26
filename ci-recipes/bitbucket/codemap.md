# ci-recipes/bitbucket/

## Responsibility
Bitbucket Pipelines recipe for running the audit in the repository's default
pipeline. It uses the Bitbucket environment to supply the target URL, audits,
and auth token.

## Design
One `Audit` step running in the `python:3.11` image. The script is explicit:
export env vars, install dependencies, run the CLI, and keep the recipe free of
custom orchestration or branching logic.

## Data & control flow

Pipeline variables feed `SLB_TARGET_URL`, `SLB_AUTH_TOKEN`, and `SLB_AUDITS`;
the step forces `SLB_FAIL_ON_CRITICAL=1`, executes `python main.py evaluate
--format both --out reports`, and archives `reports/report.json`.

## Integration points

Bitbucket Pipelines environment variables, the container image, artifact
collection, and the `evaluate` CLI in `main.py`.
