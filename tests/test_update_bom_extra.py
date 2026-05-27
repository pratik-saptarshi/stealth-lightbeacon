from __future__ import annotations

from utils.update_bom import parse_requirements, update_bom


def test_update_bom_descriptions_fallback_and_missing_file(tmp_path):
    reqs = tmp_path / "requirements.txt"
    bom = tmp_path / "bom.md"
    reqs.write_text("unknownpkg==1.2.3\nJinja2==3.1.2\nunknownpkg==1.2.4\n", encoding="utf-8")
    bom.write_text("<!-- LIBRARIES_START -->\n<!-- LIBRARIES_END -->\n", encoding="utf-8")

    libraries = parse_requirements(str(reqs))
    assert libraries == [("unknownpkg", "==1.2.4"), ("Jinja2", "==3.1.2")]

    assert update_bom(str(bom), str(reqs)) is True
    text = bom.read_text(encoding="utf-8")
    assert "Dynamic software dependency" in text
    assert "Autoescaped layout templating engine" in text

    assert update_bom(str(tmp_path / "missing.md"), str(reqs)) is False
