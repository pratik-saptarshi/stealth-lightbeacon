# Client Service Architecture

This repo is the backend producer. The two frontend consumers are the browser
addon and the Tauri desktop shell. They should converge on one service
contract, one canonical local port, and one set of connection rules.

## Client Comparison

| Client | Stack | Primary job | Transport shape | Default target |
| --- | --- | --- | --- | --- |
| Browser addon | TypeScript background worker, popup UI, content script | Lightweight DOM-first scan and optional backend bridge | `http` or `stdin` adapter mode | Loopback backend on `127.0.0.1:8000` when backend coupling is enabled |
| Desktop Tauri | React TypeScript UI with Rust transport | Operator shell, lifecycle polling, artifacts, recon, and release packaging | Tauri IPC to Rust, then HTTP to backend | Loopback backend on `127.0.0.1:8000` for local mode; HTTPS for remote mode |
| Python backend | Typer CLI today, HTTP service target | Canonical audit engine, result producer, and contract owner | HTTP service plus stdin-compatible adapter boundary | `http://127.0.0.1:8000` locally, HTTPS in cloud |

## Canonical Contract

The backend contract should keep these paths stable:

- `GET /health`
- `GET /capabilities`
- `POST /evaluations`
- `GET /evaluations/{evaluation_id}`
- `GET /evaluations/{evaluation_id}/result`
- `GET /evaluations/{evaluation_id}/artifacts`
- `POST /recon`

The backend contract snapshot lives at
[`contracts/backend-api.openapi.json`](../contracts/backend-api.openapi.json).

## Connection Rules

- `127.0.0.1:8000` is the canonical loopback default.
- Remote deployments must use HTTPS.
- Browser addon HTTP access stays loopback-first and should refuse unsafe
  private-network targets.
- Desktop local mode may auto-start a companion on loopback; standalone mode is
  an embedded runtime, not a remote API.
- `stdin` is an adapter transport, not a service deployment model.

## Alignment Rules

- Backend owns schema names, response shapes, and compatibility semantics.
- Desktop owns trusted transport, retry, and local/remote/standalone policy.
- Browser addon owns DOM extraction, scan UI, and opt-in backend coupling.
- If a client needs a shortcut route, define it as a compatibility facade over
  the canonical evaluation lifecycle rather than inventing a second backend
  model.
