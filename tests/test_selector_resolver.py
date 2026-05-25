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
