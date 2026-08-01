from app.services.ai.research_rendering import render_research_markdown


def test_research_markdown_is_rendered_and_sanitized() -> None:
    html = render_research_markdown(
        "# Report\n\n**fact** [source](https://example.com)\n\n"
        "<script>alert(1)</script>\n\n"
        "[unsafe](javascript:alert(1))\n\n"
        "<img src=x onerror=alert(1)>"
    )

    assert "<h1>Report</h1>" in html
    assert "<strong>fact</strong>" in html
    assert 'href="https://example.com"' in html
    assert "<script" not in html
    assert "javascript:" not in html
    assert "<img" not in html


def test_research_markdown_keeps_plain_text_for_empty_or_raw_html() -> None:
    assert render_research_markdown("") == ""
    assert "&lt;div&gt;raw&lt;/div&gt;" in render_research_markdown(
        "<div>raw</div>"
    )
