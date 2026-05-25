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

    assert resolved.node is not None
    assert resolved.node.name == "h1"
    assert resolved.node.get_text().strip() == "Hero Title"
    assert resolved.confidence >= resolver.min_confidence
    assert resolved.repaired is True


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
