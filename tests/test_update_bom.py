from pathlib import Path

from utils.update_bom import parse_requirements, update_bom


def test_parse_requirements_skips_comments_and_blank_lines(tmp_path):
    reqs = tmp_path / "requirements.txt"
    reqs.write_text(
        "# comment\n\nrequests==2.33.0\nfoo>=1.2\nbar\n",
        encoding="utf-8",
    )

    libraries = parse_requirements(str(reqs))

    assert libraries == [
        ("requests", "==2.33.0"),
        ("foo", ">=1.2"),
        ("bar", ""),
    ]


def test_update_bom_writes_dependency_block(tmp_path):
    bom = tmp_path / "bom.md"
    reqs = tmp_path / "requirements.txt"
    bom.write_text(
        "<!-- LIBRARIES_START -->\nold\n<!-- LIBRARIES_END -->\n",
        encoding="utf-8",
    )
    reqs.write_text("requests==2.33.0\ncustompkg==1.0.0\n", encoding="utf-8")

    assert update_bom(str(bom), str(reqs)) is True

    text = bom.read_text(encoding="utf-8")
    assert "* **requests** (`==2.33.0`): Fallback synchronous HTTP client." in text
    assert "* **custompkg** (`==1.0.0`): Dynamic software dependency." in text


def test_update_bom_reports_missing_requirements_file(tmp_path):
    bom = tmp_path / "bom.md"
    bom.write_text("<!-- LIBRARIES_START -->\n<!-- LIBRARIES_END -->\n", encoding="utf-8")

    assert update_bom(str(bom), str(tmp_path / "missing.txt")) is False


def test_update_bom_reports_missing_anchors(tmp_path):
    bom = tmp_path / "bom.md"
    reqs = tmp_path / "requirements.txt"
    bom.write_text("no anchors here\n", encoding="utf-8")
    reqs.write_text("requests==2.33.0\n", encoding="utf-8")

    assert update_bom(str(bom), str(reqs)) is False
