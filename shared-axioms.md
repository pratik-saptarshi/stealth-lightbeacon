# Shared Axioms

These three repositories are one system split into separate boundaries:

- Backend: canonical audit engine, generated contract, and report semantics.
- Desktop Tauri: trusted transport, local companion lifecycle, operator UX,
  and release packaging.
- Browser addon: local-first browser runtime, DOM extraction, and popup/
  side-panel UX.

## Non-Negotiables

1. Producer owns semantics, consumers pin and validate.
2. Boundaries are tested where they actually cross.
3. Local-first and least-privilege defaults stay in place unless explicit
   opt-in changes them.
4. Release docs, version metadata, and validation gates must match the shipped
   artifact.
5. Smallest coherent change wins; if a contract changes, update producer and
   consumer docs together.

## Role Matrix

| Concern | Backend | Desktop | Browser addon |
| --- | --- | --- | --- |
| API semantics | Source of truth for evaluation state, artifacts, and OpenAPI | Pinned consumer | Pinned consumer |
| Runtime transport | CLI and async engine | Tauri IPC and Rust transport | Background and service-worker transport |
| User-facing UI | Report artifacts and CLI output | React operator shell | Popup and side-panel UI |
| Release gate | Docs and artifacts stay aligned | Contract sync plus Tauri build | Unit, integration, UI-load, and browser smoke |
| Optional backend coupling | N/A | Local and remote policy | Opt-in backend bridge |
| Canonical port | `127.0.0.1:8000` loopback default, overridable for remote/cloud | UI defaults should preserve `8000` for local mode | Endpoint+port composition should target the same `8000` service default |
| Transport rules | HTTP for the service, stdin for adapter embedding | Local, standalone, and remote deployment modes | Loopback-first HTTP, remote HTTPS, stdin adapter fallback |

## Working Rule

When the docs disagree, trust the producer for semantics, the desktop for
packaging and transport, and the browser addon for browser UX.
