# Changelog

## Unreleased

### Wrapper and Hardening

- Added `scripts/run_public_audit.sh` as a convenience wrapper for a public audit profile. It defaults to `https://www.example.com` and accepts `TARGET=...` style overrides.
- Documented the env-style invocation so operators can run `TARGET=www.example.com ./scripts/run_public_audit.sh` without editing the script.
- Hardened SEO and UX attribute handling so empty and `None`-like `href`, `content`, `style`, `class`, and `id` values no longer crash evaluation. Malformed markup now turns into normal findings instead of exceptions.
- Removed preflight seed probing from the public audit wrapper so the target is handed straight to the SSRF-guarded audit flow.
- Stripped internal review artifacts and local-path references from the public docs surface.

## v1.2.2

### Release and Documentation

- Published the `v1.2.2` release train and aligned the runtime identity string so client headers stay in sync with the tagged version.
- Refreshed the main docs surface (`README`, `CLI-readme`, `docs/architecture`, `chagelog`, and `archotecture`) to keep the release story consistent for humans and automation.
- Kept the changelog family current so the canonical history and typo-alias entry points point at the same release notes.

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

- Expanded docs references (`README`, `CLI-readme`, `docs/architecture`) and kept `chagelog` alignment.
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
