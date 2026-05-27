# Stealth Lightbeacon BEADS Architecture Plan

This document turns the current repo state into a tracked, phase-based
architecture plan.

Source inputs:
- Current repository state
- Current architecture guide and repository state
- Current architecture doc: `docs/architecture.md`
- Cross-repo execution mirror: `docs/roadmap/roadmap.md`

## BEADS Legend

Use BEADS as the tracking shorthand for each phase:
- `B` = Blocker or gap being addressed
- `E` = Evidence from code/review
- `A` = Actions to take
- `D` = Dependencies and risks
- `S` = Success criteria and validation

## Backlog Validation

The current repo state validates the first three architecture phases.

| Phase | Status | Evidence | Remaining work |
|---|---|---|---|
| Phase 0 | Complete | Canonical payload tests pass and the report renderers normalize one payload shape. | None in this tracker. |
| Phase 1 | Complete | Selector repair is scoped per parser/document and covered by regression tests. | None in this tracker. |
| Phase 2 | Complete | MCP mode rejects mutable runtime downloads and now exposes the resolved runtime contract. | None in this tracker. |
| Phase 3 | Open | Persistence still performs row-level writes during evaluation, and the failure/backpressure path is not fully hardened. | Queue/batch persistence off the crawl hot path and cover failure isolation. |
| Phase 4 | Open | Docs and CI recipes are aligned, but the release/BOM drift guard and low-coverage seams still need dedicated tests. | Add drift checks and raise coverage on the weak branches. |

## Execution Map Mirror

The service-contract roadmap now uses the same Beads IDs in both the docs and
the local tracker. Mirror those IDs here so the architecture plan and tracker
stay aligned.

| Capability | Beads ID | Child IDs | Status |
|---|---|---|---|
| CAP-1 Service contract and transport unification | `stealth-lightbeacon-fw9` | `stealth-lightbeacon-fw9.1`, `stealth-lightbeacon-fw9.2`, `stealth-lightbeacon-fw9.3` | Complete |
| CAP-2 Evaluation lifecycle and artifact delivery | `stealth-lightbeacon-m0q` | `stealth-lightbeacon-m0q.1`, `stealth-lightbeacon-m0q.2`, `stealth-lightbeacon-m0q.3`, `stealth-lightbeacon-m0q.4`, `stealth-lightbeacon-m0q.5` | Complete |
| CAP-3 Client alignment | `stealth-lightbeacon-ds8` | `stealth-lightbeacon-ds8.1`, `stealth-lightbeacon-ds8.2`, `stealth-lightbeacon-ds8.3` | Open |
| CAP-4 Validation and release hardening | `stealth-lightbeacon-epr` | `stealth-lightbeacon-epr.1`, `stealth-lightbeacon-epr.2`, `stealth-lightbeacon-epr.3` | Open |

The canonical decomposition and task details live in
[`docs/roadmap/roadmap.md`](docs/roadmap/roadmap.md).

## Feature Map

| Feature | Scope | Phase | Implementation focus | Validation focus |
|---|---|---|---|---|
| Persistence off hot path | Batched ontology writes, bounded flushes, failure isolation | Phase 3 | Queue write work, preserve run finalization, keep small-job sync path | `tests/test_ontology.py`, `tests/integration/test_full_pipeline.py`, coverage on `utils/ontology.py` |
| Release contract sync | Docs, CI recipes, BOM, alias shims | Phase 4 | Keep canonical docs aligned, regenerate BOM, archive both artifacts | `tests/test_cli_contract.py`, `tests/test_report_formats.py`, `tests/test_ci_recipes.py`, `python3 utils/update_bom.py` |
| Coverage closure | Low-coverage helper branches | Phase 4 | Add focused tests for renderer, BOM updater, pagespeed, watcher, ontology | Full coverage run with `--fail-under=80` |

## Issue Tracker

| Issue ID | Phase | BEADS | Problem | Planned Change | Validation / Test Gate | Status |
|---|---|---|---|---|---|---|
| P3-1 | Phase 3 | B/E/A/D/S | Persistence still writes page/finding/run records inline during evaluation, so large audits can spend avoidable time in storage and vector work. | Move ontology ingestion to a bounded queue/worker path, keep a small-job synchronous fast path, and preserve ordered finalization of the run report. | `pytest -q -o addopts="" tests/test_ontology.py tests/test_performance_budget.py tests/integration/test_full_pipeline.py`; `pytest -q -o addopts="" tests --ignore=tests/integration`; `pytest -q -o addopts="" tests/integration`; full-suite coverage run with `--fail-under=64`. | Open |
| P3-2 | Phase 3 | B/E/A/D/S | Queue flush and storage-failure handling are not yet explicitly exercised for partial failure, retry, or backpressure behavior. | Add regression tests and guardrails for vector-store flush failures, bounded queue pressure, and partial persistence rollback/fallback semantics. | New unit coverage for `utils/ontology.py` failure branches; `pytest -q -o addopts="" tests/test_ontology.py`; full-suite run with coverage report. | Open |
| P4-1 | Phase 4 | B/E/A/D/S | Release metadata must stay synchronized with the docs surface, CI recipes, alias shims, and the generated BOM. | Keep canonical docs and all alias shims aligned, treat `utils/update_bom.py` as the source of truth for `bill-of-material.md`, and keep CI recipes archiving both report artifacts. | `pytest -q -o addopts="" tests/test_cli_contract.py tests/test_report_formats.py tests/test_ci_recipes.py`; `python3 utils/update_bom.py`; `git diff --check`; full-suite coverage run. | Open |
| P4-2 | Phase 4 | B/E/A/D/S | Coverage is still thin on the BOM updater and several fallback/error branches in renderer, watcher, persistence, and scraping helpers. | Add focused unit tests for the low-coverage seams and keep the repository above the 80% coverage target. | `pytest -q -o addopts="" tests/test_report_formats.py tests/test_pagespeed.py tests/test_ontology.py tests/test_watcher.py tests/test_mcp_scraper.py tests/test_stealth_mcp.py`; new `tests/test_update_bom.py`; `pytest -q -o addopts="" --cov=modules --cov=crawler --cov=utils --cov-report=term-missing tests`; `pytest -q -o addopts="" --cov=modules --cov=crawler --cov=utils --cov-fail-under=80 tests`; confirm total coverage remains above 80%. | Open |

## Prioritized Fix Plan

Implement in this order:
1. Decouple persistence ingestion from the crawl/evaluation hot path.
2. Add persistence failure and backpressure coverage.
3. Add release/BOM drift checks and keep CI artifacts aligned.
4. Fill the low-coverage seams that back the release contract.
5. Raise the repo-wide unit and integration coverage to at least 80%.

Rationale:
- Persistence is the remaining correctness/performance issue that affects large audits.
- Release/BOM drift is a release-management issue, but it should be guarded by tests rather than manual edits.
- Coverage hardening should target the seams that actually remain thin instead of inflating the test suite arbitrarily.

## Phase Batches

### Phase 3 Batch - Persistence Stability

Implementation tasks:
- Add a bounded ingestion queue in `utils/ontology.py` for page/finding vectors.
- Preserve the synchronous path for small runs by flushing immediately under the current threshold.
- Add explicit failure isolation for vector-store flush errors so run completion still writes the report payload.
- Keep run completion ordering deterministic: record pages/findings first, then finalize the run report and flush buffered vectors.
- Add regression coverage for partial flush failures, finalization under fallback stores, and diff/report retrieval after queued writes.

Validation gates:
- `pytest -q -o addopts="" tests/test_ontology.py`
- `pytest -q -o addopts="" tests/integration/test_full_pipeline.py`
- `pytest -q -o addopts="" tests/test_performance_budget.py`
- `pytest -q -o addopts="" tests --ignore=tests/integration`

### Phase 4 Batch - Release Contract and Coverage Closure

Implementation tasks:
- Keep canonical docs and alias shims synchronized in `README.md`, `CLI-readme.md`, `docs/architecture.md`, and `changelog.md`.
- Treat `utils/update_bom.py` as the source of truth for `bill-of-material.md`.
- Keep CI recipes archiving both `reports/report.json` and `reports/report.html`.
- Add focused tests for `modules/renderer.py`, `utils/update_bom.py`, `utils/ontology.py`, `modules/pagespeed.py`, and `utils/watcher.py` to close the thin branches from the latest coverage run.
- Keep the test suite above the 80% coverage target on `modules`, `crawler`, and `utils`.

Validation gates:
- `pytest -q -o addopts="" tests/test_cli_contract.py tests/test_report_formats.py tests/test_ci_recipes.py`
- `pytest -q -o addopts="" tests/test_pagespeed.py tests/test_ontology.py tests/test_watcher.py`
- `pytest -q -o addopts="" tests/test_playwright_renderer.py tests/test_browser_pool.py`
- `python3 utils/update_bom.py`
- `pytest -q -o addopts="" --cov=modules --cov=crawler --cov=utils --cov-report=term-missing tests`
- `pytest -q -o addopts="" --cov=modules --cov=crawler --cov=utils --cov-fail-under=80 tests`

## Testing Coverage Snapshot

- Unit slice: 90 passed, 1 skipped.
- Integration slice: 2 passed.
- Full suite: 92 passed, 1 skipped.
- Total coverage: last validated at 80.55% on 2026-05-26.
- Coverage floor: 64% met.
- Coverage target: 80% met.
- Lowest-coverage files in the latest run: `modules/aeo_geo.py` 67%, `modules/drupal.py` 68%, `modules/scraping/stealth_mcp.py` 78%, `modules/pagespeed.py` 79%, `modules/html_parser.py` 80%.
- Coverage target for this execution plan: 80% on the repo-wide `modules`, `crawler`, and `utils` coverage run.

## Architecture Checklist Coverage

This plan explicitly covers the agent-native architecture checklist from
`ce-agent-native-architecture`.

| Checklist item | Coverage |
|---|---|
| Parity | CLI outputs, persisted records, and diffing all use the same canonical payload |
| Granularity | Fixes are isolated to small seams: payload, selector repair, MCP mode, persistence, docs |
| Composability | New renderers continue to derive from one shared payload |
| Emergent capability | Recon and selector repair stay advisory and do not block the audit flow |
| Dynamic vs static | MCP mode should not fetch mutable runtime dependencies by default |
| CRUD completeness | Persistence remains readable, writable, and diffable through the same contract |
| Primitives not workflows | Keep helper-level refactors; do not collapse the pipeline into one monolith |
| API as validator | Validate env and runtime inputs at the boundary, not deep inside the flow |
| Shared workspace | Same repo files remain the source of truth for docs, tests, and run artifacts |
| Completion signals | No heuristic completion changes are needed for this repo scope |
| Context limits | Canonical payload reduces schema sprawl and keeps downstream context bounded |
| Agent/UI integration | Report and persisted state stay aligned so consumers do not see silent drift |
| Mobile | Not applicable to this repo scope |

## Tracking Notes

- If any phase fails its validation gate, stop and fix the phase before moving
  on.
- If a phase is implemented partially, keep the BEADS table updated with the
  remaining gap and the exact validation that failed.
- If GitHub Actions disagrees with local tests, treat CI as the source of truth
  and re-check the repo state that Actions is actually building.
