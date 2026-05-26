This repo keeps the canonical release history in [changelog.md](changelog.md).

## Unreleased

- Added `scripts/run_public_audit.sh` as a convenience wrapper for a public audit profile. It defaults to `https://www.example.com` and accepts `TARGET=...` style overrides.
- Documented the env-style invocation so operators can run `TARGET=www.example.com ./scripts/run_public_audit.sh` without editing the script.
- Hardened SEO and UX attribute handling so empty and `None`-like `href`, `content`, `style`, `class`, and `id` values no longer crash evaluation. Malformed markup now turns into normal findings instead of exceptions.

## Recent Releases

- v1.2.2: docs refresh, runtime identity alignment, and release sanity checks.
- v1.2.1: resilience, persistence batching, and release-validated external audit run coverage.
- [CLI ref](CLI-readme.md)
- [Architecture Guide](docs/architecture.md)
