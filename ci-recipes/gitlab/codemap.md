# ci-recipes/gitlab/

## Responsibility
GitLab CI recipe for the audit job. It defines a single pipeline stage that
runs the Stealth Lightbeacon evaluator inside a Python 3.11 container.

## Design
Straight-line CI: one `audit` job, repo dependency install, CLI execution, and
artifact retention. GitLab variables are passed through unchanged so the job
can stay generic across branches and runners.

## Data & control flow

`SLB_TARGET_URL`, `SLB_AUTH_TOKEN`, and `SLB_AUDITS` are bound at the job
level, `SLB_FAIL_ON_CRITICAL=1` is enforced, and `python main.py evaluate
--format both --out reports` writes the audit outputs. `reports/report.json`
and `reports/report.html` are archived and kept for one week.

## Integration points

GitLab CI variables, the `python:3.11` image, stage/artifact handling, and the
CLI/reporting code in `main.py`.
