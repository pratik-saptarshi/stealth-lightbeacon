This repo keeps the canonical architecture guide in [docs/architecture.md](docs/architecture.md).

## Current Notes

- `scripts/run_public_audit.sh` wraps the standard evaluate flow for a public audit profile and accepts `TARGET=...` style overrides.
- `seo.py` and `ux.py` now normalize missing and `None`-like attribute values before string checks, which keeps malformed markup from crashing audits.
- `v1.2.2` keeps the architecture doc aligned with the current release train.
- [CLI ref](CLI-readme.md)
- [Changelog](changelog.md)
