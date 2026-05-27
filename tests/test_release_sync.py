from pathlib import Path

from scripts.validate_release_sync import (
    validate_alias_stubs,
    validate_bom_sync,
    validate_release_sync,
)


def test_release_sync_checks_pass_on_checked_in_artifacts():
    assert validate_release_sync() == []


def test_alias_stubs_reference_canonical_docs(tmp_path):
    root = tmp_path
    (root / "README.md").write_text(
        "# README Alias\n\nCanonical project overview: [CLI-readme.md](CLI-readme.md).\n",
        encoding="utf-8",
    )
    (root / "readme.md").write_text(
        "# README Alias\n\nCanonical project overview: [CLI-readme.md](CLI-readme.md).\n",
        encoding="utf-8",
    )
    (root / "readme-CLI.md").write_text(
        "# CLI Readme Alias\n\nCanonical CLI reference: [CLI-readme.md](CLI-readme.md).\n",
        encoding="utf-8",
    )
    (root / "chagelog.md").write_text(
        "This repo keeps the canonical release history in [changelog.md](changelog.md).\n",
        encoding="utf-8",
    )
    (root / "bill-of-materials.md").write_text(
        "Canonical BOM: [bill-of-material.md](bill-of-material.md).\n",
        encoding="utf-8",
    )
    (root / "archotecture.md").write_text(
        "Canonical architecture guide: [docs/architecture.md](docs/architecture.md).\n",
        encoding="utf-8",
    )

    assert validate_alias_stubs(root) == []


def test_bom_sync_detects_drift(tmp_path):
    bom = tmp_path / "bill-of-material.md"
    reqs = tmp_path / "requirements.txt"
    bom.write_text(
        "<!-- LIBRARIES_START -->\n* **requests** (`==0.0.1`): stale\n<!-- LIBRARIES_END -->\n",
        encoding="utf-8",
    )
    reqs.write_text("requests==2.33.0\n", encoding="utf-8")

    errors = validate_bom_sync(bom, reqs)

    assert errors == ["bill-of-material.md drift: regeneration differs from checked-in file"]
