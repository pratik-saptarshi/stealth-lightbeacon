# Changelog

## v1.2.7

### Public Release and Documentation Alignment

- Published the public release surface as a conventional-commit-driven cut and aligned the runtime identity, service contract, and rendered report metadata to the new train.
- Refreshed the CLI readme, architecture guide, and release docs so the public-facing release story points at the same tagged version everywhere.
- Reconciled the compatibility defaults and smoke-test version pin so local service checks exercise the same release label that ships in reports.

### Validation and Sanity

- Ran the repo-wide test suite, release-sync checks, dependency validation, BOM regeneration, and OpenAPI export validation before publishing the release tag.
- Confirmed the release artifacts remain synchronized with the checked-in contract snapshot and generated documentation.

## v1.2.6

### Mainline Consolidation and Validation

- Merged the remaining feature branch tips into `main` and collapsed the parallel worktree lineage into a single consolidated branch.
- Preserved the queue-based service persistence path, the canonical service contract helpers, and the merged release docs while reconciling stale branch-specific overlaps.
- Added focused coverage and integration tests for SEO edge cases, service evaluation storage, helper helpers, and orchestration flows.

### Validation and Sanity

- Ran the merge-sensitive regression tests, the repo-wide coverage gate, and the service-facing integration slices after consolidation.
- Prepared the branch for CI-equivalent validation and release publication from the cleaned `main` line.

## v1.2.5

### Service Release and Contract Publication

- Published the canonical HTTP service surface for local and remote clients, including health, capabilities, compatibility, evaluation lifecycle, artifacts, and recon routes.
- Added the documented release branch `release/service-unified` with the service core, evaluation lifecycle, and contract validation series committed separately for auditability.
- Added the smoke test that boots the service, exercises the core routes end to end, and verifies a local audit completes successfully.
- Harmonized the canonical contract snapshot, drift validator, CLI defaults, and runtime identity strings around the `127.0.0.1:8000` local loopback target.
- Serialized DuckDB access inside the shared ontology store so threaded HTTP polling and background evaluation writes stay consistent in the subprocess service path.

### Validation and Sanity

- Ran the targeted config, contract, alignment, and smoke tests on the release branch.
- Verified the service boots, accepts evaluation requests, and returns terminal results and artifacts for a local target.

## v1.2.4

### Backlog, Release, and Coverage Hardening

- Validated the remaining BEADS backlog and merged the phase-wise implementation plan into an execution tracker.
- Added startup MCP diagnostics that expose the resolved command, arguments, and timeout budgets when `--engine mcp` is selected.
- Hardened the MCP runtime contract with pinned-command validation and fallback behavior coverage.
- Aligned the GitHub Actions, Bitbucket, and GitLab audit recipes so the dual-output contract archives both `report.json` and `report.html`.
- Added focused regression coverage for the low-surface helper paths and raised repo-wide coverage above the 80% target.
- Kept the canonical docs, alias shims, and BOM metadata synchronized for release publication.

### Validation and Sanity

- Ran the unit, integration, and full-suite coverage checks before publish.
- Confirmed the repository passes the 80% coverage target with the current release shape.

## Unreleased

- _No unreleased changes yet._

## v1.2.2

### Release and Documentation

- Published the `v1.2.2` release train and aligned the runtime identity string so client headers stay in sync with the tagged version.
- Refreshed the main docs surface (`README`, `CLI-readme`, `docs/architecture`, and the compatibility alias files) to keep the release story consistent for humans and automation.
- Kept the changelog family current so the canonical history and compatibility aliases point at the same release notes.

### Validation and Sanity

- Ran the repository test suite and coverage checks before publish so the release path stays validation-first.
- Performed a latest-commit security sanity pass and found no obvious secret material in the current release diff.

## v1.2.1

### Reliability and Orchestration

- Shifted persistence writes to batched task groups in `main.run_evaluation` so crawl/evaluation runs no longer block on every storage write.
- Added a release-grade persistence flow for canonical report payloads (`target_url`) with `targetUrl` compatibility fallback for legacy consumers.
- Kept `target_url`-driven report contracts across JSON/HTML/LLM/Geo-XML renderers and ontology finish writes.

### Coverage and Contracts

- Confirmed external audit execution path on public target sites and documented page-crawl coverage in operational notes.
- Added/reinforced CLI environment input validation and failure guidance for malformed/missing URLs.
- Expanded selector-resolver and MCP tests to reduce regressions around resilience and bounded posture.

## v1.1.10

### Contracts and Reliability

- Enforced a single canonical report payload (`target_url`, `average_score`, `total_issues`, `domains`) for JSON/HTML/LLM/Geo-XML output paths.
- Added parser-scoped selector resolver state to avoid cross-document selector leak regressions.
- Made MCP engine initialization deterministic by requiring explicit `SLB_MCP_COMMAND` configuration and bounded subprocess/tool-call handshakes.
- Added explicit MCP-related CLI/MCP env contract (`SLB_MCP_COMMAND`, `SLB_MCP_ARGS`, `SLB_MCP_HANDSHAKE_TIMEOUT`) in docs and runtime.

### Quality and Operations

- Expanded docs references (`README`, `CLI-readme`, `docs/architecture`) and kept the compatibility aliases aligned.
- Added regression coverage for parser-scoped selector reuse and MCP command configuration behavior.
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
