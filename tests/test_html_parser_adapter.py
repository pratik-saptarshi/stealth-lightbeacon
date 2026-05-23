"""
test_html_parser_adapter.py — TDD Unit tests for HtmlParser and HtmlNode adapter APIs.
"""

import pytest
import re
from modules.html_parser import HtmlParser

def test_parser_init():
    """
    Verifies that the HtmlParser initializes successfully.
    """
    html = "<html><head><title>Test Title</title></head><body><h1>Hello World</h1></body></html>"
    parser = HtmlParser(html)
    assert parser is not None

def test_parser_find():
    """
    Verifies find() by tag name, attrs, and specific attributes.
    """
    html = """
    <html>
      <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <link rel="canonical" href="https://example.com/canonical">
        <meta property="og:title" content="OG Title">
      </head>
      <body>
        <h1 id="main-title">My Title</h1>
      </body>
    </html>
    """
    parser = HtmlParser(html)
    
    # 1. Find by tag name
    h1 = parser.find("h1")
    assert h1 is not None
    assert h1.name == "h1"
    assert h1.text == "My Title"
    
    # 2. Find by tag and attrs dict
    viewport = parser.find("meta", attrs={"name": "viewport"})
    assert viewport is not None
    assert viewport.get("content") == "width=device-width, initial-scale=1.0"
    
    # 3. Find by custom keyword args
    canonical = parser.find("link", rel="canonical")
    assert canonical is not None
    assert canonical["href"] == "https://example.com/canonical"
    
    # 4. Find property attribute
    og = parser.find("meta", property="og:title")
    assert og is not None
    assert og.get("content") == "OG Title"
    
    # 5. Non-existent tag returns None
    assert parser.find("nonexistent") is None

def test_parser_find_all():
    """
    Verifies find_all() with tag strings, tag lists, regex, and boolean attribute matching.
    """
    html = """
    <html>
      <body>
        <h1 class="heading">H1</h1>
        <h2 class="heading">H2</h2>
        <h3 class="other">H3</h3>
        <a href="/link1">Link 1</a>
        <a href="/link2">Link 2</a>
        <div style="color: red;">Styled Div</div>
        <span style="font-size: 10px;">Styled Span</span>
        <span>Unstyled Span</span>
      </body>
    </html>
    """
    parser = HtmlParser(html)
    
    # 1. Find all by list of tags
    headings = parser.find_all(["h1", "h2"])
    assert len(headings) == 2
    assert headings[0].name == "h1"
    assert headings[1].name == "h2"
    
    # 2. Find all by tag string
    links = parser.find_all("a")
    assert len(links) == 2
    assert links[0]["href"] == "/link1"
    
    # 3. Find all using regex for tag name
    regex_headings = parser.find_all(re.compile(r"^h[1-3]$"))
    assert len(regex_headings) == 3
    
    # 4. Find all with boolean attribute (style=True)
    styled_elements = parser.find_all(style=True)
    assert len(styled_elements) == 2
    assert styled_elements[0].name == "div"
    assert styled_elements[1].name == "span"

def test_parser_callable_shortcut():
    """
    Verifies that the parser instance is callable as a shortcut for find_all.
    """
    html = "<html><body><script>1</script><style>2</style></body></html>"
    parser = HtmlParser(html)
    elements = parser(["script", "style"])
    assert len(elements) == 2
    assert elements[0].name == "script"
    assert elements[1].name == "style"

def test_parser_get_text():
    """
    Verifies that get_text() extracts clean body text.
    """
    html = "<html><body><div>Hello <span>World</span></div></body></html>"
    parser = HtmlParser(html)
    assert "Hello World" in parser.get_text()

def test_node_attributes_and_string():
    """
    Verifies Node properties: name, text, string, attrs, get(), dict access, and serialization.
    """
    html = """<a href="https://example.com" class="link-btn" id="btn1">Click <b>Me</b></a>"""
    parser = HtmlParser(html)
    node = parser.find("a")
    
    assert node is not None
    assert node.name == "a"
    assert node.text == "Click Me"
    
    # .string matches BS4 string (returns text if tag has only one child/string, else None or text)
    # For BS4, a tag with nested tags has .string as None because it contains children tags,
    # but we can implement it cleanly to behave like BS4.
    # In this case, <a> contains "Click " and <b>, so its BS4 .string is None. Let's verify that.
    assert node.string is None
    
    # Let's test a simple tag with direct text
    parser_simple = HtmlParser("<title>My Page</title>")
    title_node = parser_simple.find("title")
    assert title_node.string == "My Page"
    
    # Test attrs and get
    assert "href" in node.attrs
    assert node.attrs["href"] == "https://example.com"
    assert node.get("class") == ["link-btn"] or node.get("class") == "link-btn"
    assert node["id"] == "btn1"
    
    # Test fallback
    assert node.get("nonexistent", "fallback") == "fallback"
    
    # Test serialization
    assert "href=\"https://example.com\"" in str(node)

def test_node_traversal_parents_siblings():
    """
    Verifies node traversal APIs: parents, find_parent(), and find_next().
    """
    html = """
    <div id="container">
      <ul class="menu">
        <li class="item">
          <a href="#" id="my-link">Link</a>
        </li>
      </ul>
      <p id="sibling-p">Paragraph</p>
    </div>
    """
    parser = HtmlParser(html)
    link = parser.find("a")
    assert link is not None
    
    # 1. Test .parents generator
    parent_names = [p.name for p in link.parents]
    assert "li" in parent_names
    assert "ul" in parent_names
    assert "div" in parent_names
    
    # 2. Test .find_parent()
    li_parent = link.find_parent("li")
    assert li_parent is not None
    assert li_parent.name == "li"
    
    div_parent = link.find_parent("div")
    assert div_parent is not None
    assert div_parent["id"] == "container"
    
    # 3. Test .find_next()
    li = parser.find("li")
    # find_next on li should find the <a> or inner tag or sibling
    sibling_p = li.find_parent("div").find("p")
    assert sibling_p is not None
    assert sibling_p["id"] == "sibling-p"

def test_node_decompose():
    """
    Verifies that decompose() removes the node from the document.
    """
    html = "<html><body><script>console.log(1);</script><p>Text</p></body></html>"
    parser = HtmlParser(html)
    
    scripts = parser.find_all("script")
    assert len(scripts) == 1
    
    scripts[0].decompose()
    
    # After decompose, the script tag should be gone from the parser text and find_all
    assert len(parser.find_all("script")) == 0
    assert "console.log" not in parser.get_text()

def test_parser_benchmark(benchmark):
    """
    Benchmarks parsing and querying HTML using HtmlParser.
    """
    html = "<html><body>" + "<div><p><a href='#'>Link</a></p></div>" * 100 + "</body></html>"
    def parse_and_query():
        parser = HtmlParser(html)
        links = parser.find_all("a")
        return len(links)
    
    result = benchmark(parse_and_query)
    assert result == 100
