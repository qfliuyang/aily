from aily.parser.parsers import _extract_title, ParseResult, parse_generic, parse_kimi


def test_extract_title_from_html_title():
    html = "<html><head><title>  My Page  </title></head><body></body></html>"
    assert _extract_title(html) == "My Page"


def test_extract_title_from_h1():
    html = "<html><body><h1>Header <span>One</span></h1></body></html>"
    assert _extract_title(html) == "Header One"


def test_extract_title_returns_untitled():
    html = "<html><body><p>No headers here</p></body></html>"
    assert _extract_title(html) == "Untitled"


def test_parse_generic_returns_markdown():
    result = parse_generic("https://example.com", "<title>Example</title><body>Hi</body>")
    assert result.title == "Example"
    assert result.source_type == "generic"
