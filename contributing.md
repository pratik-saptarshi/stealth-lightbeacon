# Contributing

This repository keeps the release surface intentionally small and versioned.
Contributions should preserve the canonical docs, alias shims, and validation
gates that keep the audit flow and release train aligned.

## Workflow

- Make the smallest change that fixes the issue.
- Update the relevant codemap or phase tracker when architecture or release
  surfaces change.
- Keep alias files lightweight and point them at the canonical docs.
- Regenerate `bill-of-material.md` with `python3 utils/update_bom.py` whenever
  `requirements.txt` changes.
- Run the focused tests for the touched subsystem, then the broader unit and
  integration slices before publishing.

## Required Checks

- `python -m py_compile` or equivalent syntax validation for touched Python
  files.
- `pytest` for the affected unit and integration tests.
- `git diff --check` before commit.
- `python3 utils/update_bom.py` for dependency or release metadata changes.

## Release Hygiene

- Keep `README.md`, `readme.md`, `CLI-readme.md`, `readme-CLI.md`,
  `architecture.md`, `docs/architecture.md`, `changelog.md`, and
  `bill-of-material.md` synchronized.
- Do not publish a release until the docs, CI recipes, tests, and BOM all agree
  on the same release train.
- Treat `SECURITY.md` as the canonical security policy and `security-policy.md`
  as the compatibility alias.
