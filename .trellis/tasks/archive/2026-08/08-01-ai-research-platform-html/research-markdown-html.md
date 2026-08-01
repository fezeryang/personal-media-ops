# Markdown to safe HTML research

## Repository constraints

The API currently stores a model-generated Markdown summary in a JSON result and
the React page renders it as escaped plain text. The user requested both a
rendered HTML view and a reusable HTML API field. Model output is untrusted, so
the implementation must escape raw HTML, allow only a small Markdown subset, and
filter link protocols and event attributes. Existing content, credentials and
raw prompts must not be copied into a new storage system.

## Candidate approaches

### A. Server-side `mistune` + `bleach`, client-side defense-in-depth (recommended)

* Use `mistune` to convert Markdown into HTML with raw HTML disabled/escaped.
* Use `bleach` with an explicit allow-list for headings, paragraphs, lists,
  emphasis, code, blockquotes, tables and `http`/`https` links. Strip event
  attributes, scripts, styles and dangerous URL schemes.
* Save the original Markdown and sanitized HTML in the existing JSON result.
  For old results missing HTML, API detail serialization can derive it without a
  migration and without changing historical Markdown.
* The React page renders the API HTML only after a second `DOMPurify.sanitize`
  pass. A Markdown copy/view remains available.

Pros: one canonical API representation for the page, exports and future
consumers; server-side safety does not depend on a particular browser.

Cons: two small dependencies and an explicit allow-list to maintain.

### B. Client-only `marked` + `DOMPurify`

Convert Markdown in React and sanitize it before rendering. This avoids a
backend dependency but cannot provide a canonical `summary_html` API field,
and other consumers would each need to reimplement the conversion.

### C. Hand-written Markdown subset

Escape all text and implement only headings/paragraphs/lists/code/links with
regular expressions. This adds no dependency but is fragile around nesting,
tables, multiline code and future model formatting. It is not recommended for
an API field intended for reuse.

## Decision

Use A. Pin compatible major versions in the existing backend/frontend lock
files, keep the sanitizer allow-list narrow, and test malicious Markdown such
as `<script>`, `onerror`, `javascript:` links, raw iframes and data URLs. The
frontend still sanitizes the API HTML because the result is model-controlled
and browser rendering is a separate trust boundary.

## Platform UI implication

The platform selector must consume the existing `/api/crawler/capabilities`
response. It should show every registered platform, but selection is derived
from the platform's `search` mode `enabled` flag. `production_verified` and
`enabled` remain separate labels; deferred or disabled platforms are visible
with their reason and cannot be submitted.
