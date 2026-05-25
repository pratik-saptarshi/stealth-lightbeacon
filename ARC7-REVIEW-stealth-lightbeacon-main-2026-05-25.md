# Architectural Review Report — stealth-lightbeacon codebase architecture

**Subject:** stealth-lightbeacon codebase architecture
**Date:** 2026-05-25
**Mode:** Codebase Review
**Panel:** Context Master (Gemini 3 Pro) · The Architect (Claude Sonnet 4.6) · Security Sentinel (OpenAI o4) · Product Visionary (GPT-5.2) · Creative Strategist (GPT-5.3-Codex) · The Optimizer (GPT-5.3-Codex) · The Naysayer (Claude Sonnet 4.6)

---

## Final Recommendation: Request Changes

The codebase has a solid modular shape: the CLI orchestration is reasonably thin, evaluators are separated by concern, and the new contract tests cover the added formats and helpers. The architecture is directionally sound for a production CLI.

The main risks are architectural rather than feature-level: the audit payload is split across multiple incompatible schemas, selector repair is globally cached across documents, the MCP scraping path fetches an unpinned runtime dependency, and the write path still serializes a lot of work inline. Those concerns will create drift, stale results, and non-deterministic behavior as the system grows or as more callers depend on the contracts.

Focused validation run: 22 targeted tests passed under the project venv after disabling the repo’s coverage addopts in this environment.

---

## Findings Summary

| Severity | Count |
|----------|-------|
| Critical | 0 |
| Major    | 3 |
| Minor    | 1 |
| Info     | 0 |

---

## Critical Issues (Must Address)

None.

---

## Major Issues (Should Address)

### ARC7-1: Normalize the audit contract before it fragments further
- **Severity:** Major
- **Source:** The Architect, Product Visionary, The Naysayer
- **Files:** [`main.py`](/Users/neo/projects/stealth-lightbeacon/main.py#L277), [`report/formats.py`](/Users/neo/projects/stealth-lightbeacon/report/formats.py#L34), [`utils/ontology.py`](/Users/neo/projects/stealth-lightbeacon/utils/ontology.py#L314), [`utils/crawl_diff.py`](/Users/neo/projects/stealth-lightbeacon/utils/crawl_diff.py#L17)
- **Description:** The same audit result is represented with multiple schemas: `build_report_payload()` emits `target_url` and per-domain `name`, while persistence and diffing still consume `targetUrl` and accept both `domain` and `name` as fallbacks. `main.py` also serializes yet another inline `report_dict` shape for storage. The code already contains compatibility fallbacks, which is a strong signal that the contract has started to fragment. That makes future renderers, canary runs, and historical diffs harder to trust because consumers must keep guessing which shape they are receiving.
- **Recommendation:** Define one canonical audit payload object or dataclass and use it everywhere: CLI output, HTML/Markdown/XML rendering, persistence, and diffing. Keep compatibility shims only at the boundary layer, then remove the internal fallbacks once the new schema is the only internal representation.

### ARC7-2: Scope selector repair to a single document
- **Severity:** Major
- **Source:** The Naysayer, The Architect
- **Files:** [`modules/html_parser.py`](/Users/neo/projects/stealth-lightbeacon/modules/html_parser.py#L25), [`modules/html_parser.py`](/Users/neo/projects/stealth-lightbeacon/modules/html_parser.py#L421), [`utils/selector_resolver.py`](/Users/neo/projects/stealth-lightbeacon/utils/selector_resolver.py#L18)
- **Description:** `SelectorResolver` is instantiated once at module import time and caches a resolved node object by selector signature only. That cache is shared by all `HtmlParser` instances. A quick repro shows the failure mode: resolving the same missing selector against a second page can return the node from the first page. This is a correctness bug, not just a heuristic miss, because the repair path can hand back stale DOM from a different document.
- **Recommendation:** Make the resolver cache parser-scoped or document-scoped. Cache selector metadata or repaired selector strings, not live node objects, and invalidate on each new document. If you want cross-document reuse, cache only the repair strategy, then re-resolve against the current parser before returning a node.

### ARC7-3: Pin the MCP scraping dependency instead of fetching it live
- **Severity:** Major
- **Source:** Security Sentinel, The Architect
- **Files:** [`modules/scraping/stealth_mcp.py`](/Users/neo/projects/stealth-lightbeacon/modules/scraping/stealth_mcp.py#L19), [`modules/scraping/factory.py`](/Users/neo/projects/stealth-lightbeacon/modules/scraping/factory.py#L12)
- **Description:** The MCP scraper defaults to `npx -y @modelcontextprotocol/server-playwright`, which fetches a mutable package at runtime. That creates a supply-chain and determinism gap: a production audit run can change behavior because the registry changed, and the command can fail for reasons unrelated to the target site. This is especially risky because the factory exposes it as a normal engine choice rather than as an explicitly managed external dependency.
- **Recommendation:** Require an explicit version pin or a preinstalled/local command path for MCP mode. Surface the executable path and version in config, fail fast when the dependency is missing, and keep runtime downloads out of the default execution path.

---

## Minor Suggestions (Nice to Have)

### ARC7-4: Batch the semantic-index writes or move them off the crawl hot path
- **Severity:** Minor
- **Source:** The Optimizer
- **Files:** [`main.py`](/Users/neo/projects/stealth-lightbeacon/main.py#L194), [`utils/ontology.py`](/Users/neo/projects/stealth-lightbeacon/utils/ontology.py#L244), [`utils/ontology.py`](/Users/neo/projects/stealth-lightbeacon/utils/ontology.py#L288)
- **Description:** The current crawl loop is page-serial, and each page/finding immediately computes a vector and inserts it into the semantic store. That is a reasonable default for small audits, but it means larger crawls scale linearly with page count and pay the embedding/storage cost inline on the critical path. The architecture already parallelizes evaluators per page, so persistence is likely to become the next bottleneck.
- **Recommendation:** If larger crawls are a real target, profile the persistence path and consider bounded page concurrency plus batched or queued vector insertion. Keep the current synchronous path for small jobs, but move the heavier indexing work off the crawl loop when throughput matters.

---

## Informational Notes

None.

---

## What Was Done Well

- The CLI orchestration is still reasonably thin and mostly delegates to focused modules rather than growing into a monolith.
- The new report surfaces are additive and backward-compatible at the user-facing boundary.
- The evaluator and persistence split is clear enough that future refactors can isolate schema and storage changes without rewriting the whole pipeline.
- The test suite already covers the new contract areas, which gives the architecture a useful safety net.

---

## Blind Voting Results (If Applicable)

None needed. The review had no high-stakes architecture split that required a forced vote.

---

## Panel Breakdown

### The Architect (Claude Sonnet 4.6)
- **Recommendation:** Request Changes
- **Summary:** The module boundaries are sensible, but the core audit contract is already fragmenting across renderers, persistence, and diffs. The cleanest next step is to make the payload canonical before more consumers depend on it.
- **Findings:** Major 1, Minor 0, Info 0

### Security Sentinel (OpenAI o4)
- **Recommendation:** Request Changes
- **Summary:** The MCP scraper path introduces a runtime dependency fetch that should not be part of a production audit default. The current design is workable, but it needs deterministic dependency control.
- **Findings:** Major 1, Minor 0, Info 0

### Product Visionary (GPT-5.2)
- **Recommendation:** Approve with Conditions
- **Summary:** The feature set is useful and additive, especially the new formats and CI contracts. The main product risk is that the data contract will become hard to document and harder to consume if schema drift continues.
- **Findings:** Major 1, Minor 0, Info 0

### Creative Strategist (GPT-5.3-Codex)
- **Recommendation:** Approve with Conditions
- **Summary:** The current decomposition is a good base for simplification, but the selector-repair and report-payload paths are carrying too much hidden state. Simplifying those seams will pay off quickly.
- **Findings:** Major 1, Minor 0, Info 0

### The Optimizer (GPT-5.3-Codex)
- **Recommendation:** Approve with Conditions
- **Summary:** Throughput is likely acceptable for small jobs, but the sequential crawl loop plus inline persistence will become the next scaling limiter. That is worth addressing before audits get much larger.
- **Findings:** Major 0, Minor 1, Info 0

### The Naysayer (Claude Sonnet 4.6)
- **Recommendation:** Request Changes
- **Summary:** The selector cache leak is the kind of issue that passes tests and still corrupts real audits. The architecture needs stronger state boundaries before it can be considered reliable.
- **Findings:** Major 1, Minor 0, Info 0

---

## Dissenting Opinions

No hard dissent. The only disagreement was about urgency: the product and optimizer lenses were more comfortable with "Approve with Conditions," while the architect, security, and naysayer lenses pushed the review to "Request Changes" because the contract drift and cross-document selector cache are structural, not cosmetic.

---

## Model Assignments (Recommended for Implementation)

| Task | Assigned Model | Rationale |
|---|---|---|
| Canonical audit payload schema | Claude Sonnet 4.6 | Best fit for unifying contracts across modules without overfitting the implementation. |
| MCP dependency pinning and execution model | OpenAI o4 | Strong fit for supply-chain and operational-risk hardening. |
| Selector cache scoping and invalidation | GPT-5.3-Codex | Good at precise refactors in parser-adjacent code. |
| Crawl throughput tuning and persistence batching | GPT-5.3-Codex | Best placed to optimize the hot path without changing behavior. |

---

## Action Items

- [ ] Introduce one canonical audit payload and use it across report generation, persistence, and diffing.
- [ ] Scope selector repair to a single parser/document and stop caching live nodes globally.
- [ ] Pin or externalize the MCP runtime dependency before treating it as a normal engine option.
- [ ] Profile the crawl/persistence hot path and decide whether batching or bounded concurrency is warranted.

---

*Generated by ARC-7 Panel · 2026-05-25*
