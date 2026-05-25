# Changelog

## v1.1.9

### Documentation

- Documented the `llm` and `geo-xml` report formats, including their artifact paths.
- Documented the CI env contract for `SLB_TARGET_URL`, `SLB_AUTH_TOKEN`, `SLB_AUDITS`, and `SLB_FAIL_ON_CRITICAL`.
- Expanded the README and architecture guide to cover recon, selector repair, crawl diffs, and the agent-card manifest.

### Runtime and Contracts

- Bumped the runtime user-agent and report metadata to `1.1.9` so release output stays aligned with the new tag.
- Added advisory reconnaissance (`--recon`, `--recon-auto`) and the supporting agent-orchestration contract surfaces.

## v1.1.8

### Documentation

- Refreshed the main README with a docs index, live dependency validation guidance, and the current CI/test flow.
- Added a dedicated CLI reference for command usage, flags, examples, and output artifacts.
- Expanded the architecture guide to cover CLI operating modes and the dependency validation pipeline.
- Added this changelog so future releases have a single home for human-readable history.

### Runtime and Quality

- Bumped the runtime user-agent version string to `1.1.8` so release metadata stays aligned with the published tag.
- Hardened the accessibility evaluator against empty `alt` values returned as `None` by the parser.
- Added coverage-focused accessibility tests that push the accessibility module above the 80% target.

## v1.1.7

- Synchronized the bill of materials with the pinned dependency set.
- Added live dependency validation using `pip-tools` so incompatible pins are caught before merge.
- Updated CI to install dependencies from PyPI explicitly and validate the resolver state before tests.
