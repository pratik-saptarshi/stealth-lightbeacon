# Stealth Lightbeacon — Architecture & Technical Workflows

This document details the architectural specifications, component boundaries, and non-blocking asynchronous data-flow patterns governing the **Stealth Lightbeacon** engine. It is kept in sync with the `v1.2.2` release train.

---

## 1. Core Architecture Overview

Stealth Lightbeacon is engineered as a highly decoupled, concurrent **asynchronous plugin framework** in Python. High concurrency is achieved using native `asyncio` loop schedules and non-blocking `httpx` async clients, avoiding thread overhead and locking bottlenecks.

```
                  ┌────────────────────────────────────────┐
                  │          Typer CLI Entry               │
                  │             (main.py)                  │
                  └──────────────────┬─────────────────────┘
                                     │
                                     ▼
                  ┌────────────────────────────────────────┐
                  │             SSRFGuard Check            │
                  │         (utils/ssrf_guard.py)          │
                  └──────────────────┬─────────────────────┘
                                     │ (Safe URLs)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │         Async recursive crawler        │
                  │             (crawler.py)               │
                  └──────────────────┬─────────────────────┘
                                     │
             ┌───────────────────────┴───────────────────────┐
             ▼ (Rendered/Stealth)                            ▼ (Default)
┌────────────────────────────────────────┐       ┌────────────────────────────────────────┐
│     Adversarial Scraping Factory       │       │         Direct httpx HTTP Client       │
│          (modules/scraping/)           │       │             (crawler.py)               │
┌────────────────────────────────────────┘       └────────────────────────────────────────┘
             │                                               │
             └───────────────────────┬───────────────────────┘
                                     │ (HTML Content)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │         Unified HTML Parser            │
                  │     (BeautifulSoup / Selectolax)       │
                  └──────────────────┬─────────────────────┘
                                     │ (Normalized DOM)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │      Independent Evaluator Modules     │
                  │      (modules/*.py subclasses)         │
                  └──────────────────┬─────────────────────┘
                                     │ (EvaluationResults)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │          Consolidation & Budget        │
                  │          (utils/budget_validator)      │
                  └──────────────────┬─────────────────────┘
                                     │ (Exit 2 if Breached)
                                     ▼
                  ┌────────────────────────────────────────┐
                  │            Report Generator            │
                  │   (report/generator.py + formats.py)   │
                  └────────────────────────────────────────┘
```

The report stage renders JSON, HTML, LLM Markdown, or GEO XML from one normalized payload so downstream consumers can choose the format they need without changing the audit pipeline.

---

## 2. Component Boundary Specifications

### 🛡️ 1. SSRFGuard Security Shield (`utils/ssrf_guard.py`)
- **Vulnerability Blocked:** Prevents **Server-Side Request Forgery (SSRF)** attacks by intercepting outgoing requests before TCP connection instantiation.
- **DNS Hostname Resolution:** Translates hostnames to IP addresses using system-level DNS resolver pools inside `asyncio` thread executors to prevent blocking the event loop.
- **Subnet Address Matching:** Matches resolved IPs against standard subnet lists defined by standard library `ipaddress` APIs, checking for:
  - Private Class A/B/C ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
  - Loopback ranges (`127.0.0.0/8`, `::1`)
  - Link-local ranges (`169.254.0.0/16`)
  - Unspecified and reserved subnets
- **Double Gate Checks:** Executed first at the CLI evaluation gate, and secondly inside the Crawler recursive queue loop (on discovered links and final post-redirect URLs) to prevent redirect SSRF bypasses.

### 🕷️ 2. High-Performance Spider Engine (`crawler.py`)
- **Queue Mechanics:** Employs a non-blocking `asyncio.Queue` executing a breadth-first search (BFS) recursive spider traversal.
- **Domain Concurrency Boundary:** Bounded strictly to the source domain netloc (same-domain boundary constraint).
- **Circuit Breaker Rules:** Halts immediately once the visited unique URL count hits `--max-urls` or traversal reaches `--crawl-depth`.
- **Throttling & Deduping:**
  - Employs an `asyncio.Semaphore` to cap concurrent sockets connections.
  - Implements configurable rate limits via non-blocking `asyncio.sleep()`.
  - Normalizes URLs (stripping query fragments and hashes) and retains only final redirected URLs to avoid duplicate fetches.

### 🎭 3. Pluggable Scraping strategies (`modules/scraping/`)
Auditing sophisticated properties requires evading standard anti-bot triggers. The **Scraping Strategy Pattern** isolates fetching workloads:
- **HttpEngine (Standard):** High-speed, low-footprint direct HTTP client using customized modern browser headers and HTTP/2 transport profiles.
- **ObscuraEngine (Fast-Path):** Spawns a compiled hermetic Rust static binary `./bin/obscura` via subprocesses to negotiate low-level TLS handshakes, spoofing standard client signatures.
- **ZendriverEngine (Heavy-Path):** Automated anti-detect Chromium controller powered by Playwright. Intercepts webdriver parameters, emulates system fonts/plugins, overrides WebGL GPU descriptors, and simulates human mouse gestures to defeat zero-day bot challenges.
- **StealthMcpLayer (Model Context Protocol):** Client wrapper encapsulating queries into standard MCP tool calls (Playwright integration stdio sessions) for autonomous agent orchestrators. It requires an explicitly pinned executable or versioned package via `SLB_MCP_COMMAND` / `SLB_MCP_ARGS`; the mutable runtime-download default is disabled.

### 🔌 4. Decoupled Diagnostic Plugins (`modules/`)
Evaluation domains are structured as independent diagnostic plugins executing concurrently:
- **`seo.py` (SEO compliance):** Canonical tags checks, autoescaped robots directives matching, and `application/ld+json` parsing. The evaluator now normalizes empty and `None`-like attribute values before string checks so malformed markup degrades into findings instead of exceptions.
- **`pagespeed.py` (PageSpeed & Performance):** Concurrent Google PSI API client. Integrates an asynchronous SQLite caching system mapping URL MD5 hashes to past response structures under **Write-Ahead Logging (WAL)** and **Normal Sync** mode to prevent write lock bottlenecks.
- **`accessibility.py` (WCAG 2.2 AA):** Checks WCAG rules including alt tag values, headings nesting hierarchy sequences, and missing form label links.
- **`aeo_geo.py` (Answer Engine Optimization Heuristics):** Analyzes speakable schemas, conversation Q&A outline lengths (Featured Snippets), E-E-A-T schemas authority records, and single keyword densities.
- **`ux.py` (UX Performance):** Assesses viewports, inline readability limits, tap target widths/heights, and menu nesting levels. It now normalizes missing `content`, `style`, `class`, and `id` attributes before scoring, which keeps malformed HTML from crashing UX audits. Scans DOM and body text for user privacy consent popups compliance (EU Compliance).
- **`drupal.py` (CMS & Security):** Footprints generator tokens and core path disclosures, checks security headers (HSTS, CSP, X-Frame-Options), and probes exposed default JSON:API routers (`/jsonapi/user/user`).

---

## 3. Data Integration & Reporting Flow

1. **Typer CLI Command:** Parses parameters, instantiates active evaluators, and triggers the non-blocking event loop.
2. **Consolidation Pipeline:** Collects results from concurrent evaluators, merges metadata maps, and aggregates diagnostic issue logs.
3. **Budget Compliance Check:** Feeds metrics into the `BudgetValidator` helper. If any Core Web Vitals or scores breach specified budget boundaries, throws exit code `2` to break build loops.
4. **Autoescaped Jinja2 Output:** Exports diagnostic tables into JSON and renders a responsive HTML dashboard securely, autoescaping page content to eliminate Stored XSS threats. The shared payload is canonical across rendering, persistence, and diffing, and it also supports LLM Markdown and GEO XML renderers for orchestration workflows.

---

## 4. CLI Operating Modes

The Typer entrypoint in `main.py` exposes a single `evaluate` command with several operating modes:

- `URL` argument: Required unless running `--watch` or `--search-semantic`.
- `--watch`: Starts the `WorkspaceWatcher` background loop for local directory sync workflows.
- `--search-semantic`: Queries the `OntologyStore` vector index for historical runs and findings.
- `--persist`: Enables DuckDB + LanceDB persistence for runs, pages, and findings.
- `--render`: Forces rendered DOM auditing through Playwright-backed scraping.
- `--engine`: Selects the scraping strategy: `http`, `fast`, `stealth`, or `mcp`.
- `--recon` and `--recon-auto`: Run advisory anti-bot reconnaissance before the crawl and optionally apply the recommended posture automatically.
- `--format`: Selects the output renderer, including `json`, `html`, `both`, `llm`, and `geo-xml`.
- `--crawl-depth` and `--max-urls`: Control recursive crawl breadth and circuit breaking.
- `--check-links` and `--check-api`: Enable outbound link checks and Drupal API discovery.
- `--budget`: Applies an external JSON performance budget after evaluation.

The CLI also exposes `--out`, `--http2`, and `--allow-private` for report routing, protocol tuning, and SSRF-boundary overrides.

---

## 5. Operational Support Services

The supporting utility layer keeps the orchestration surface stable:

- `utils/recon.py` performs advisory reconnaissance and selects a scraping posture.
- `utils/selector_resolver.py` and `modules/html_parser.py` repair selectors when small layout shifts break exact matches, scoped per parser instance so repaired DOM state never leaks between documents.
- `utils/crawl_diff.py` and `utils/ontology.py` compare canonical audit payloads and persisted runs to highlight regressions and improvements.
- `utils/ontology.py` buffers vector writes during the crawl and flushes them in batches to reduce hot-path persistence cost.
- `scripts/run_public_audit.sh` wraps the standard evaluate flow for a public audit profile and accepts `TARGET=...` style overrides.
- `SLB_MCP_COMMAND`, `SLB_MCP_ARGS`, `SLB_MCP_HANDSHAKE_TIMEOUT`, `SLB_MCP_TOOL_TIMEOUT`, and `SLB_MCP_SHUTDOWN_TIMEOUT` define the MCP runtime contract when `--engine mcp` is selected.
- `utils/agent_card.py` defines the stable agent-card manifest used by orchestration consumers.

---

## 6. Dependency and Validation Pipeline

The repository now validates pinned dependencies before test execution:

1. `requirements.txt` remains the source of truth for runtime pins.
2. `scripts/validate_dependencies.py` calls `piptools compile` against the live PyPI index to catch incompatible pins before merge.
3. `.github/workflows/ci.yml` installs dependencies with `--extra-index-url https://pypi.org/simple`, validates the lock state, then runs the test suite on Python 3.11.
4. `pre-commit run dependency-validation --all-files` mirrors the CI check locally so dependency drift is caught early.
5. The current release notes for `v1.2.2` live in `changelog.md` and the alias docs point to the same history.

The prioritized remediation roadmap and phase validation gates live in
[`docs/architecture-beads-plan.md`](docs/architecture-beads-plan.md).
