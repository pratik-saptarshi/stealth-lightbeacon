# Stealth Lightbeacon BEADS Architecture Plan

This document turns the current repo state into a tracked, phase-based
architecture plan.

Source inputs:
- Current repository state
- Current architecture guide and repository state
- Current architecture doc: `docs/architecture.md`

## BEADS Legend

Use BEADS as the tracking shorthand for each phase:
- `B` = Blocker or gap being addressed
- `E` = Evidence from code/review
- `A` = Actions to take
- `D` = Dependencies and risks
- `S` = Success criteria and validation

## Current Feature Gaps

Priority order is based on blast radius, correctness risk, and how much each
gap affects downstream consumers.

| Priority | Gap | Why it matters | Primary files |
|---|---|---|---|
| P0 | Canonical audit payload is split across multiple shapes | Report rendering, persistence, and diffing can drift from each other and produce incompatible contracts | `main.py`, `report/formats.py`, `utils/ontology.py`, `utils/crawl_diff.py` |
| P0 | Selector repair is shared across documents | A repaired selector can resolve against the wrong DOM and corrupt results across pages | `modules/html_parser.py`, `utils/selector_resolver.py` |
| P0 | MCP scraping depends on live runtime fetches | Audit runs can change behavior or fail because of registry state, not target state | `modules/scraping/stealth_mcp.py`, `modules/scraping/factory.py` |
| P1 | Crawl persistence work runs inline on the hot path | Large audits will spend avoidable time in storage and embedding work | `main.py`, `utils/ontology.py` |
| P1 | Documentation and CI recipes need contract alignment | The public story must match the current schema, env contract, and release flow | `README.md`, `CLI-readme.md`, `docs/architecture.md`, `changelog.md`, `ci-recipes/*` |

## Phase Plan

### Phase 0 - Normalize the Audit Contract

`B`
- Contract drift: `targetUrl` vs `target_url`, inline persistence payloads,
  and fallback-driven diffing.

`E`
- `main.py` serializes a separate `report_dict` for storage.
- `report/formats.py` and `utils/ontology.py` already expose compatibility
  shims, which is a sign the internal schema is not canonical.

`A`
- Introduce one canonical audit payload type and make all renderers,
  persistence, and diffing consume it.
- Keep compatibility shims only at the boundaries.
- Add contract tests that prove `json`, `html`, `llm`, and `geo-xml` all
  derive from the same payload.

`D`
- Preserve current filenames and user-facing report shape.
- Do not break the existing CLI.

`S`
- Targeted tests for report formatting and diffing pass.
- Full test suite passes.
- One payload shape is used internally end to end.

Validation gate:
- `pytest -q -o addopts="" tests/test_report_formats.py tests/test_crawl_diff.py tests/test_ontology.py`
- `pytest -q -o addopts="" tests -q`

### Phase 1 - Scope Selector Repair to One Document

`B`
- Selector repair cache is currently shared across parser instances.

`E`
- `modules/html_parser.py` keeps parser-scoped selector repair state.
- The resolver should not return live nodes from a different DOM.

`A`
- Make selector repair parser-scoped or document-scoped.
- Cache repaired selector metadata or strategy, not live DOM nodes.
- Invalidate or rebind repair state on each new document.
- Add a regression test that resolves the same selector against two pages and
  verifies the second page does not reuse the first page's node.

`D`
- Preserve exact-selector behavior.
- Prefer false negatives over false positives when confidence is low.

`S`
- The same missing selector on two different documents resolves locally.
- No cross-document DOM leakage is possible.
- Existing parser fixtures continue to pass.

Validation gate:
- `pytest -q -o addopts="" tests/test_selector_resolver.py tests/test_html_parser_adapter.py`
- `pytest -q -o addopts="" tests -q`

### Phase 2 - Pin and Bound MCP Scraping

`B`
- `StealthMcpLayer` defaults to a live `npx` package fetch and has no bounded
  handshake/runtime guard.

`E`
- `modules/scraping/stealth_mcp.py` must reject mutable runtime download defaults.
- The process is spawned with bounded handshake/tool/shutdown timeouts only when explicitly pinned.

`A`
- Require an explicit command path or pinned executable/version for MCP mode.
- Make runtime fetches opt-in, not the default.
- Add handshake and subprocess timeout protection.
- Surface the selected executable and version in config and diagnostics.

`D`
- Preserve non-MCP engines as the default fallback.
- Do not bundle third-party bypass tooling.

`S`
- MCP mode fails fast when the dependency is missing or unpinned.
- Timeouts are deterministic.
- The engine choice is visible in run metadata.

Validation gate:
- `pytest -q -o addopts="" tests/test_recon_mode.py tests/test_crawler.py`
- `pytest -q -o addopts="" tests -q`

### Phase 3 - Move Persistence Off the Crawl Hot Path

`B`
- Inline semantic-store writes will become the first throughput bottleneck.

`E`
- `main.py` currently serializes persistence work inside the run loop.
- `utils/ontology.py` computes vectors and inserts them immediately.

`A`
- Batch or queue vector writes.
- Keep the small-job synchronous path.
- If necessary, add bounded crawl concurrency so persistence no longer blocks
  page acquisition.

`D`
- Preserve correctness and ordering of persisted runs.
- Do not lose page/finding records if batching fails midway.

`S`
- Performance budget tests remain green.
- Larger audits show lower end-to-end latency for the same page count.
- Persistence remains consistent under partial failures.

Validation gate:
- `pytest -q -o addopts="" tests/test_performance_budget.py`
- `pytest -q -o addopts="" tests -q`

### Phase 4 - Reconcile Docs, CI, and Release Contracts

`B`
- Public docs and CI recipes must match the canonical runtime contract.

`E`
- Current docs already describe the expanded architecture, but the plan must
  stay synchronized with code and CI.
- Existing CI templates and release notes depend on stable env-driven inputs.

`A`
- Update `README.md`, `CLI-readme.md`, `docs/architecture.md`, and
  `changelog.md` to reflect the canonical payload, selector scope fix, and MCP
  pinning behavior.
- Keep CI recipes aligned with the env contract and artifact paths.
- Add a release note entry that calls out the architecture hardening and the
  validation results.

`D`
- Preserve backward compatibility in the CLI and report filenames.
- Keep release text consistent with the current versioning strategy.

`S`
- Docs match the actual code paths.
- CI recipes remain copy-paste ready.
- Release notes mention the verified validation gates and known limitations.

Validation gate:
- `pytest -q -o addopts="" tests -q`
- `python -m coverage run -m pytest -q -o addopts="" tests -q`
- `python -m coverage report --show-missing --fail-under=64`
- GitHub Actions `main` workflow green on the repository actions page.

## Prioritized Fix Plan

Implement in this order:
1. Canonical audit payload normalization.
2. Selector repair scoping and cache invalidation.
3. MCP dependency pinning plus bounded handshake/runtime control.
4. Persistence batching or queued indexing.
5. Docs, CI recipes, and release-note reconciliation.

Rationale:
- The first three are correctness and reliability issues that can corrupt
  audit output or make runs non-deterministic.
- The persistence issue is a scale and latency problem.
- The docs/CI work is necessary, but it should follow the contract fixes so
  the public story matches the actual architecture.

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
