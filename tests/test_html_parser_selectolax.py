from __future__ import annotations

import importlib
import sys
import types


def _install_fake_selectolax(monkeypatch):
    class _FakeNode:
        def __init__(self, tag, attrs=None, text="", html=None):
            self.tag = tag
            self.attributes = attrs or {}
            self._text = text
            self.html = html or f"<{tag}>{text}</{tag}>"
            self.parent = None
            self.child = None
            self.next = None
            self._children = []
            self._decomposed = False

        def append(self, node):
            if self._children:
                self._children[-1].next = node
            self._children.append(node)
            node.parent = self
            self.child = self._children[0]
            return node

        def text(self, deep=True):
            if self._decomposed:
                return ""
            if not deep:
                return self._text
            return self._text + "".join(child.text(deep=True) for child in self._children)

        def decompose(self):
            self._decomposed = True

        def strip(self):
            self._decomposed = True

        def _matches(self, selector):
            if selector in {"*", ""}:
                return self.tag not in {"-text", "-comment"}
            tag = selector
            element_id = None
            classes = []
            if "#" in tag:
                tag, remainder = tag.split("#", 1)
                if "." in remainder:
                    element_id, class_blob = remainder.split(".", 1)
                    classes = class_blob.split(".")
                else:
                    element_id = remainder
            elif "." in tag:
                tag, class_blob = tag.split(".", 1)
                classes = class_blob.split(".")
            if tag and self.tag != tag:
                return False
            attrs = self.attributes
            if element_id and attrs.get("id") != element_id:
                return False
            if classes:
                actual = attrs.get("class", "")
                actual_list = actual if isinstance(actual, list) else str(actual).split()
                if not all(item in actual_list for item in classes):
                    return False
            return True

        def css(self, selector):
            matches = []
            for part in [item.strip() for item in selector.split(",") if item.strip()]:
                matches.extend(self._css_single(part))
            return matches

        def _css_single(self, selector):
            matches = []

            def visit(node):
                if node._decomposed:
                    return
                if node._matches(selector):
                    matches.append(node)
                for child in node._children:
                    visit(child)

            visit(self)
            return matches

    class _FakeParser:
        def __init__(self, html):
            self.root = _FakeNode("-root")
            html_node = self.root.append(_FakeNode("html"))
            body = html_node.append(_FakeNode("body"))
            main = body.append(_FakeNode("main", attrs={"id": "main", "class": "hero wrap"}))
            p = main.append(_FakeNode("p", text="Alpha", html="<p id='lead' class='copy'>Alpha</p>", attrs={"id": "lead", "class": "copy"}))
            p.append(_FakeNode("-text", text="Alpha"))
            link = main.append(_FakeNode("a", attrs={"href": "/next", "class": "cta"}))
            link.append(_FakeNode("-text", text="Next"))
            footer = body.append(_FakeNode("footer", attrs={"data-role": "site-footer"}, text="Footer"))
            footer.append(_FakeNode("-text", text="Footer"))
            self._html = html

        def css(self, selector):
            return self.root.css(selector)

    parser_mod = types.ModuleType("selectolax.parser")
    parser_mod.HTMLParser = _FakeParser
    parser_mod.Node = _FakeNode
    selectolax_pkg = types.ModuleType("selectolax")
    selectolax_pkg.parser = parser_mod

    monkeypatch.setitem(sys.modules, "selectolax", selectolax_pkg)
    monkeypatch.setitem(sys.modules, "selectolax.parser", parser_mod)
    sys.modules.pop("modules.html_parser", None)
    return importlib.import_module("modules.html_parser")


def test_selectolax_backend_node_wrapper_paths(monkeypatch):
    html_parser = _install_fake_selectolax(monkeypatch)
    html_parser.force_backend("selectolax")

    parser = html_parser.HtmlParser("<html></html>")
    node = parser.find("p", attrs={"id": "lead"})
    link = parser.find("a", attrs={"href": "/next"})

    assert node is not None
    assert node.name == "p"
    assert node.string == "Alpha"
    assert "id" in node
    assert "class" in node.attrs
    assert str(node).startswith("<p")
    assert [parent.name for parent in node.parents] == ["main", "body", "html"]

    assert link is not None
    assert link.find_parent("main").attrs["id"] == "main"
    assert node.find_next("a").get("href") == "/next"
    assert parser.find_all(["a", "footer"])[1].name == "footer"
    assert parser.get_text().strip().startswith("Alpha")

    link.decompose()
    assert parser.find("a") is None


def test_selectolax_force_backend_rejects_unknown(monkeypatch):
    html_parser = _install_fake_selectolax(monkeypatch)

    try:
        html_parser.force_backend("bogus")
    except ValueError as exc:
        assert "Unknown backend" in str(exc)
