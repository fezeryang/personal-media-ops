from __future__ import annotations

import bleach
import mistune

_MARKDOWN = mistune.create_markdown(
    escape=True,
    plugins=("table", "strikethrough"),
)
_ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}
_ALLOWED_ATTRIBUTES = {"a": ["href", "title"]}


def render_research_markdown(markdown: str) -> str:
    """Return a bounded, sanitized HTML representation of a research report."""

    rendered = _MARKDOWN(markdown)
    return bleach.clean(
        rendered,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        protocols=("http", "https"),
        strip=True,
        strip_comments=True,
    )
