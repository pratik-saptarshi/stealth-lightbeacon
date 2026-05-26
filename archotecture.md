This repo keeps the canonical architecture guide in [docs/architecture.md](docs/architecture.md).

## Current Notes

- `scripts/run_public_audit.sh` wraps the standard evaluate flow for a public audit profile, accepts `TARGET=...` style overrides, and hands the target straight through to the SSRF-guarded audit flow without external seed probing.
- `seo.py` and `ux.py` now normalize missing and `None`-like attribute values before string checks, which keeps malformed markup from crashing audits.
- `v1.2.3` keeps the architecture doc aligned with the current release train.
- [CLI ref](CLI-readme.md)
- [Changelog](changelog.md)
