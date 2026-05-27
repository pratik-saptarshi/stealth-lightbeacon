from __future__ import annotations

import logging
import re

import pytest

import modules.html_parser as html_parser


class _DummyNode:
    def __init__(self, name: str, attrs: dict | None = None):
        self.name = name
        self.attrs = attrs or {}


def test_helper_filters_and_backend_switching(monkeypatch, caplog):
    node = _DummyNode("button", {"id": "cta", "class": ["primary", "wide"], "property": "launch"})

    assert html_parser._matches_filter(node, ["button", "a"], attrs={"id": "cta"})
    assert html_parser._matches_filter(node, re.compile(r"^but"), class_="primary", property_="launch")
    assert not html_parser._matches_filter(node, "input")
    assert html_parser._selector_for_query(None) == "*"
    assert html_parser._selector_for_query(["a", "button"]) == "a, button"
    assert html_parser._selector_for_query(re.compile("x")) == "*"
    assert html_parser._selector_for_query("section") == "section"

    monkeypatch.setattr(html_parser, "SELECTOLAX_AVAILABLE", False)
    caplog.set_level(logging.WARNING)
    html_parser.force_backend("selectolax")
    assert html_parser.BACKEND == "bs4"
    assert "Selectolax is not installed" in caplog.text

    html_parser.force_backend("bs4")
    assert html_parser.BACKEND == "bs4"

    with pytest.raises(ValueError, match="Unknown backend"):
        html_parser.force_backend("bogus")


def test_bs4_backend_wrappers_cover_node_apis():
    html_parser.force_backend("bs4")
    parser = html_parser.HtmlParser(
        """
        <html>
          <body>
            <div id="outer">
              <article class="card wide" data-role="feature">
                <p id="lead">Hello <span>World</span></p>
                <a href="/next" class="cta">Next</a>
              </article>
            </div>
          </body>
        </html>
        """
    )

    paragraph = parser.find("p", attrs={"id": "lead"})
    link = parser.find("a", attrs={"href": "/next"})

    assert paragraph is not None
    assert paragraph.name == "p"
    assert paragraph.text == "Hello World"
    assert paragraph.get_text() == "Hello World"
    assert paragraph.string is None
    assert "id" in paragraph
    assert paragraph.get("missing", "fallback") == "fallback"
    assert paragraph["id"] == "lead"
    assert "lead" in str(paragraph)
    assert [parent.name for parent in paragraph.parents][:2] == ["article", "div"]
    assert paragraph.find_parent("article").attrs["data-role"] == "feature"
    assert paragraph.find_next("a").get("href") == "/next"
    assert len(paragraph.find_all("span")) == 1

    assert link is not None
    assert link.find_parent("div").attrs["id"] == "outer"
    assert len(parser(["article", "a"])) == 2

    link.decompose()
    assert parser.find("a") is None
    assert "Next" not in parser.get_text()
