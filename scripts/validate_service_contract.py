"""Validate the checked-in service contract snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.service_contract import CONTRACT_PATH, validate_service_contract_snapshot


def main() -> int:
    errors = validate_service_contract_snapshot(CONTRACT_PATH)
    if errors:
        for error in errors:
            print(error)
        return 1
    print(f"service contract OK: {CONTRACT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
