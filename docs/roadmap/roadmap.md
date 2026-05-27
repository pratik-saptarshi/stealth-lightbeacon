# Offline Evaluation Roadmap

## Purpose

This roadmap turns the current repo state into a durable planning artifact for
the offline-evaluation service boundary. It decomposes the work into
capabilities, epics, features, user stories, and tasks, and it keeps the test
strategy tied to the same structure.

## Source Validation

`docs/offline-eval-roadmap.md` is not present in the current working tree, so
this roadmap is reconstructed from the authoritative docs that do exist:

- `docs/architecture.md`
- `docs/architecture-beads-plan.md`
- `shared-axioms.md`
- `docs/client-service-architecture.md`

If the missing source file reappears, merge any delta into this document and
retire the old path under `docs/roadmap/`.

## Completion Snapshot

| Item | Status | Notes |
| --- | --- | --- |
| Roadmap artifact | Complete | Canonical hub created at `docs/roadmap/roadmap.md`. |
| Source validation | Partial | Original `docs/offline-eval-roadmap.md` is absent locally. |
| Service contract snapshot | Complete | OpenAPI snapshot now pinned in `contracts/backend-api.openapi.json`. |
| Service implementation | Complete | HTTP service layer, lifecycle routes, and smoke coverage are in place. |
| Client alignment | Open | Desktop and browser clients still need service-driven convergence. |
| Test strategy | Complete | Unit and integration strategy are defined and backed by passing tests. |

## Capability Map

| Capability ID | Beads ID | Capability | Outcome | Status |
| --- | --- | --- | --- | --- |
| CAP-1 | `stealth-lightbeacon-fw9` | Service contract and transport unification | One backend service contract with loopback and remote deployment modes. | Complete |
| CAP-2 | `stealth-lightbeacon-m0q` | Evaluation lifecycle and artifact delivery | Create, poll, result, artifacts, and recon routes share one state model. | Complete |
| CAP-3 | `stealth-lightbeacon-ds8` | Client alignment | Desktop Tauri and browser addon consume the same backend semantics. | Open |
| CAP-4 | `stealth-lightbeacon-epr` | Validation and release hardening | Tests, drift checks, and docs stay aligned with the shipped contract. | Open |

## Feature Decomposition

### CAP-1: Service Contract and Transport Unification

| Epic ID | Epic | Feature | User Story | Tasks | Status |
| --- | --- | --- | --- | --- | --- |
| EP-1.1 | HTTP service extraction | Health and capabilities endpoints | As an operator, I can probe service health and supported modes before sending work. | Extract a service app factory, add `/health`, add `/capabilities`, expose compatibility payloads, return structured errors. | Complete |
| EP-1.2 | Transport policy | Local, remote, and adapter modes | As an operator, I can target loopback, HTTPS, or stdin without changing the contract. | Normalize config, enforce `127.0.0.1:8000` loopback defaults, keep stdin adapter-only, reject unsafe remote targets. | Complete |
| EP-1.3 | Auth and compatibility | Error and capability negotiation | As a client, I get explicit 401/409 failures when the backend requires auth or a version gate fails. | Add auth middleware, version negotiation, and typed error responses. | Complete |

### CAP-2: Evaluation Lifecycle and Artifact Delivery

| Epic ID | Epic | Feature | User Story | Tasks | Status |
| --- | --- | --- | --- | --- | --- |
| EP-2.1 | Evaluation submission | `POST /evaluations` | As a client, I can submit a new evaluation and receive a stable evaluation ID. | Define request validation, create job records, return 202 payloads, persist accepted timestamps. | Complete |
| EP-2.2 | Progress polling | `GET /evaluations/{evaluation_id}` | As a client, I can poll status until the evaluation is terminal. | Add job state storage, stage/progress reporting, terminal state flags, not-found handling. | Complete |
| EP-2.3 | Terminal output | `GET /evaluations/{evaluation_id}/result` | As a client, I can fetch the final normalized result once the job is complete. | Serialize the canonical result DTO, map internal findings to the response shape, preserve summary and severity counts. | Complete |
| EP-2.4 | Artifact retrieval | `GET /evaluations/{evaluation_id}/artifacts` | As a client, I can fetch report descriptors and download URLs for terminal outputs. | Store artifact metadata, generate media types and URLs, keep local and remote paths stable. | Complete |
| EP-2.5 | Recon advisory | `POST /recon` | As a client, I can request recon guidance before launching the main evaluation. | Promote recon to a first-class route, preserve advisory semantics, return posture, confidence, signals, and evidence. | Complete |

### CAP-3: Client Alignment

| Epic ID | Epic | Feature | User Story | Tasks | Status |
| --- | --- | --- | --- | --- | --- |
| EP-3.1 | Desktop alignment | Tauri adapter parity | As a desktop operator, I can keep local, standalone, and remote modes consistent with the service contract. | Keep the Rust adapter aligned to the OpenAPI snapshot, preserve mode-specific config, and map service errors cleanly into UI state. | Open |
| EP-3.2 | Browser addon alignment | Optional backend bridge | As an addon user, I can opt into backend-backed scans without losing local-first behavior. | Align backend bridge requests, keep loopback-first host policy, preserve stdin adapter semantics, and sync shared contract types. | Open |
| EP-3.3 | Shared schema ownership | One canonical schema source | As a maintainer, I can update a single contract and fan out compatible client changes. | Keep contract snapshots, generated types, and runtime checks synchronized. | Open |

### CAP-4: Validation and Release Hardening

| Epic ID | Epic | Feature | User Story | Tasks | Status |
| --- | --- | --- | --- | --- | --- |
| EP-4.1 | Unit coverage | Contract and boundary tests | As a maintainer, I can trust the service contract to reject invalid shapes before runtime. | Add schema tests, endpoint validation tests, auth/compatibility tests, and config normalization tests. | Open |
| EP-4.2 | Integration coverage | End-to-end lifecycle smoke | As a maintainer, I can verify submission-to-artifact flows against a running service. | Add lifecycle tests for create/poll/result/artifacts/recon, plus failure-path coverage for 400/401/404/409 responses. | Open |
| EP-4.3 | Drift guards | Docs and snapshot sync | As a maintainer, I can catch contract drift before release. | Snapshot the OpenAPI file, compare client types to contract schemas, and keep docs in sync with the shipped behavior. | Open |

## Explicit Beads Child Issues

| Issue ID | Beads ID | Parent | Type | BEADS | Description | Status | Validation Gate |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RDM-1 | `stealth-lightbeacon-fw9.1` | CAP-1 / EP-1.1 | Feature | B: no HTTP service layer; E: CLI-only backend; A: extract app factory and routes; D: config and auth policy; S: health/capabilities pass contract tests | Create the service entrypoint and base route surface. | Complete | Unit tests for route validation and contract snapshot. |
| RDM-2 | `stealth-lightbeacon-fw9.2` | CAP-1 / EP-1.2 | Feature | B: transport split across clients; E: desktop/addon already model local and remote modes; A: normalize port and transport policy; D: loopback and HTTPS restrictions; S: config maps to one canonical endpoint model | Define local/remote/adapter transport behavior. | Complete | Unit tests for config normalization and host policy. |
| RDM-3 | `stealth-lightbeacon-fw9.3` | CAP-1 / EP-1.3 | Feature | B: auth/version semantics are undefined in the service boundary; E: desktop and addon expect explicit auth and compatibility failures; A: add auth middleware and typed compatibility errors; D: remote access and version drift; S: health/capabilities return 401/409 behavior cleanly | Add auth and compatibility negotiation. | Complete | Unit tests for auth-required and incompatible-client responses. |
| RDM-4 | `stealth-lightbeacon-m0q.1` | CAP-2 / EP-2.1 | Feature | B: no evaluation job API; E: desktop and addon expect submit/poll lifecycle; A: add accepted job store; D: async state persistence; S: 202 response with stable evaluation ID | Implement evaluation submission. | Complete | Integration test for submit response and job record creation. |
| RDM-5 | `stealth-lightbeacon-m0q.2` | CAP-2 / EP-2.2 | Feature | B: no polling state model; E: clients expect terminal status; A: persist stage/progress/status transitions; D: timeout and retry handling; S: status route returns terminal flags and message | Implement evaluation polling. | Complete | Integration test for pending, running, terminal, and missing IDs. |
| RDM-6 | `stealth-lightbeacon-m0q.3` | CAP-2 / EP-2.3 | Feature | B: result retrieval is not served by backend; E: desktop renderer expects terminal payload; A: serialize canonical result DTO; D: normalize summary/findings counts; S: result route matches client schema | Implement terminal result delivery. | Complete | Unit tests for result serialization and schema compatibility. |
| RDM-7 | `stealth-lightbeacon-m0q.4` | CAP-2 / EP-2.4 | Feature | B: artifact descriptors are missing; E: clients expect report links; A: store artifact metadata and URLs; D: local vs remote download locations; S: artifact route returns stable descriptors | Implement artifact delivery. | Complete | Integration test for artifact list and URL shape. |
| RDM-8 | `stealth-lightbeacon-m0q.5` | CAP-2 / EP-2.5 | Feature | B: recon exists only as helper logic; E: roadmap and clients need a route; A: expose recon as a first-class endpoint; D: advisory-only semantics; S: recon response returns posture, confidence, evidence | Promote recon to service API. | Complete | Unit tests for recon response shape and advisory semantics. |
| RDM-9 | `stealth-lightbeacon-ds8.1` | CAP-3 / EP-3.1 | Epic | B: desktop uses Tauri IPC to a service contract; E: existing adapter already models health/capabilities/evaluation/result/artifacts; A: align Rust proxy with contract; D: local/standalone/remote behavior; S: adapter passes all contract assertions | Keep desktop client aligned. | Open | Desktop contract sync tests and smoke checks. |
| RDM-10 | `stealth-lightbeacon-ds8.2` | CAP-3 / EP-3.2 | Epic | B: addon backend bridge has its own config and host policy; E: optional backend coupling already exists; A: align request/response contracts; D: loopback-first policy; S: addon uses same service schema | Keep browser addon aligned. | Open | Addon bridge contract tests and host-policy tests. |
| RDM-11 | `stealth-lightbeacon-ds8.3` | CAP-3 / EP-3.3 | Epic | B: contract drift can diverge client schemas; E: one canonical contract should feed all clients; A: keep contract snapshots, generated types, and runtime checks synchronized; D: manual drift; S: shared schema source remains authoritative | Keep shared schema ownership aligned. | Open | Schema-generation and contract-sync tests. |
| RDM-12 | `stealth-lightbeacon-epr.1` | CAP-4 / EP-4.1 | Epic | B: contract drift can regress runtime behavior; E: one pinned OpenAPI snapshot already exists; A: add schema and boundary unit tests; D: snapshot update process; S: contract validation stays green | Build unit test coverage for service seams. | Complete | `pytest` contract and boundary suite. |
| RDM-13 | `stealth-lightbeacon-epr.2` | CAP-4 / EP-4.2 | Epic | B: service lifecycle has no end-to-end guard; E: clients require submit-to-artifact flow; A: add lifecycle smoke tests; D: async timing and state transitions; S: flow succeeds against a running service | Build integration test coverage for service lifecycle. | Complete | Running-service smoke suite. |
| RDM-14 | `stealth-lightbeacon-epr.3` | CAP-4 / EP-4.3 | Epic | B: docs and code can drift; E: roadmap and snapshots now need a release gate; A: add snapshot/diff checks; D: release train changes; S: docs and contract remain synchronized | Build drift and release checks. | Open | Snapshot diff and docs-sync gate. |

## Unit Test Strategy

Focus unit tests on stable boundaries and schema enforcement.

| Area | What to test | Expected outcome |
| --- | --- | --- |
| Contract schema | OpenAPI snapshot structure, required route presence, required schema fields | Contract changes fail fast before runtime. |
| Config normalization | Port handling, URL composition, local vs remote defaults, adapter-only mode | Invalid or ambiguous config is rejected early. |
| Host policy | Loopback, private network, HTTPS, allowlist behavior | Unsafe endpoints are blocked consistently. |
| Auth and signatures | Basic auth, request signatures, error mapping | Remote auth failures are explicit and deterministic. |
| Result normalization | Result payload, severity counts, findings, timestamps | Consumer-facing shapes remain stable. |
| Recon output | Advisory posture, confidence, signals, evidence | Recon stays non-destructive and typed. |

## Integration Test Strategy

Exercise the service as clients will consume it.

| Scenario | Inputs | Assertions |
| --- | --- | --- |
| Loopback local service | `http://127.0.0.1:8000` | Health and capabilities respond, create/poll/result/artifacts routes work. |
| Remote HTTPS service | HTTPS base URL with auth | Auth is required when configured and version gates return 401/409 as expected. |
| Create-to-result lifecycle | Submit evaluation, poll until terminal | Evaluation ID remains stable and terminal payload matches the normalized schema. |
| Artifact retrieval | Terminal evaluation with report outputs | Artifact descriptors include name, kind, media type, and download URL. |
| Recon request | Target URL passed to `/recon` | Recon returns posture, confidence, evidence, and auto-select policy. |
| Negative paths | Invalid payloads, unknown IDs, incompatible client | 400/404/409 failures return structured API errors. |

## Completion Tracking

| Track Item | Status | Next Check |
| --- | --- | --- |
| Roadmap artifact | Complete | Keep this file as the canonical plan hub. |
| Capability decomposition | Complete | Keep issue rows synchronized with implementation work and parent IDs. |
| Service implementation | Complete | Add HTTP service layer and route handlers. |
| Contract sync | Complete | Regenerate or validate OpenAPI snapshot from backend behavior. |
| Client alignment | Open | Keep desktop and addon in lockstep with the service contract. |
| Unit strategy | Complete | Turn the table above into concrete tests. |
| Integration strategy | Complete | Add lifecycle smoke coverage once the service exists. |
| Beads tracker | Complete | Capability epics and child issues now exist in the local Beads database. |
