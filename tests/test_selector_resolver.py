from modules.html_parser import HtmlParser
from utils.selector_resolver import SelectorResolver


def test_selector_resolver_repairs_small_layout_shift():
    html = """
    <html>
      <body>
        <main>
          <h1 class="page-title">Hero Title</h1>
        </main>
      </body>
    </html>
    """

    parser = HtmlParser(html)
    resolver = SelectorResolver()

    resolved = resolver.resolve(parser, "h1#main-title", text_hint="Hero Title")

    selector_name, selector_attrs = resolver._split_selector(resolved.selector, None)
    reparsed = parser.find(selector_name, attrs=selector_attrs)

    assert resolved.selector == "h1.page-title"
    assert resolved.confidence >= resolver.min_confidence
    assert resolved.repaired is True
    assert reparsed is not None
    assert reparsed.name == "h1"
    assert reparsed.get_text().strip() == "Hero Title"


def test_html_parser_uses_selector_repair_for_exact_miss():
    html = """
    <html>
      <body>
        <section>
          <h2 data-role="headline">Section Heading</h2>
        </section>
      </body>
    </html>
    """

    parser = HtmlParser(html)
    node = parser.find("h2", attrs={"id": "does-not-exist"})

    assert node is not None
    assert node.name == "h2"
    assert node.get_text().strip() == "Section Heading"


def test_selector_resolver_stays_document_scoped():
    """
    Resolver state should not leak between parser instances.
    """
    parser_a = HtmlParser("<main><h1 id='title'>Primary</h1></main>")
    parser_b = HtmlParser("<article><h1 id='heading'>Secondary</h1></article>")

    first = parser_a.find("h1", attrs={"id": "main-title"}, text_hint="Primary")
    second = parser_b.find("h1", attrs={"id": "main-title"}, text_hint="Secondary")

    assert first is not None
    assert second is not None
    assert first.get_text().strip() == "Primary"
    assert second.get_text().strip() == "Secondary"


def test_selector_resolver_cache_and_fallback_paths():
    parser = HtmlParser("<main><button class='cta'>Launch</button></main>")
    resolver = SelectorResolver(min_confidence=0.5)

    resolved = resolver.resolve(parser, "button#missing", text_hint="Launch")
    cached = resolver.resolve(parser, "button#missing", text_hint="Launch")
    split_name, split_attrs = resolver._split_selector("button#launch.cta", None)

    assert resolved is cached
    assert resolved.selector == "button.cta"
    assert resolved.repaired is True
    assert split_name == "button"
    assert split_attrs["id"] == "launch"
    assert split_attrs["class"] == ["cta"]
