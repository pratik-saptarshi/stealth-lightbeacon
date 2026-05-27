#!/usr/bin/env python3
"""Validate release docs, BOM, and contract snapshot stay synchronized."""

from __future__ import annotations

import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.service_contract import CONTRACT_PATH, validate_service_contract_snapshot
from utils.update_bom import update_bom

BOM_PATH = ROOT / "bill-of-material.md"
REQUIREMENTS_PATH = ROOT / "requirements.txt"

ALIAS_STUBS = {
    ROOT / "README.md": "CLI-readme.md",
    ROOT / "readme.md": "CLI-readme.md",
    ROOT / "readme-CLI.md": "CLI-readme.md",
    ROOT / "chagelog.md": "changelog.md",
    ROOT / "bill-of-materials.md": "bill-of-material.md",
    ROOT / "archotecture.md": "docs/architecture.md",
}


def validate_alias_stubs(root: Path = ROOT) -> list[str]:
    errors: list[str] = []

    for path, canonical in ALIAS_STUBS.items():
        alias_path = root / path.name
        if not alias_path.exists():
            errors.append(f"missing alias stub: {alias_path.name}")
            continue

        text = alias_path.read_text(encoding="utf-8")
        if canonical not in text:
            errors.append(f"alias stub drift: {alias_path.name} -> {canonical}")

    readme = root / "README.md"
    lower_readme = root / "readme.md"
    if readme.exists() and lower_readme.exists():
        if readme.read_text(encoding="utf-8") != lower_readme.read_text(encoding="utf-8"):
            errors.append("README.md and readme.md content drift")

    return errors


def validate_bom_sync(
    bom_path: Path = BOM_PATH,
    requirements_path: Path = REQUIREMENTS_PATH,
) -> list[str]:
    errors: list[str] = []

    if not bom_path.exists():
        return [f"missing BOM file: {bom_path}"]
    if not requirements_path.exists():
        return [f"missing requirements file: {requirements_path}"]

    with tempfile.TemporaryDirectory(prefix="slb-bom-sync-") as tmpdir:
        temp_bom = Path(tmpdir) / bom_path.name
        temp_bom.write_text(bom_path.read_text(encoding="utf-8"), encoding="utf-8")
        if not update_bom(str(temp_bom), str(requirements_path)):
            errors.append("BOM regeneration failed")
            return errors

        if temp_bom.read_text(encoding="utf-8") != bom_path.read_text(encoding="utf-8"):
            errors.append("bill-of-material.md drift: regeneration differs from checked-in file")

    return errors


def validate_release_sync(root: Path = ROOT) -> list[str]:
    errors = []
    contract_path = root / CONTRACT_PATH
    if not contract_path.exists():
        errors.append(f"missing contract snapshot: {contract_path}")
    else:
        errors.extend(validate_service_contract_snapshot(contract_path))
    errors.extend(validate_alias_stubs(root))
    errors.extend(validate_bom_sync(root / BOM_PATH.name, root / REQUIREMENTS_PATH.name))
    return errors


def main() -> int:
    errors = validate_release_sync(ROOT)
    if errors:
        for error in errors:
            print(error)
        return 1
    print("release sync OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
