# Quality Guidelines

> Code quality standards for frontend development.

## Overview

Frontend changes must pass ESLint, strict TypeScript production build, Vitest,
the configured coverage gate, and proportional browser layout checks.

## Forbidden Patterns

- `any`, silent type assertions around API data, or ignored request errors.
- `dangerouslySetInnerHTML` for logs or unsanitized result records. The only
  exception is Research Result HTML after the explicit DOMPurify allow-list
  pass described below.
- Hardcoded production hostnames, IPs, commands, Cookie controls, paths, or
  concurrency controls.
- Unbounded log or JSONL loading.
- Production-default mock responses.

## Required Patterns

- Validate API JSON with Zod.
- Send request cancellation signals.
- Restrict external URLs to HTTP(S).
- Use plain-text rendering for untrusted strings. For the Research Center's
  derived `summary_html`, sanitize again in the browser before DOM insertion;
  never render the raw Markdown or raw API field directly.
- Keep `frontend/dist`, `.env`, logs, databases, QR codes, and crawler output
  out of Git.

## Testing Requirements

Unit-test API error normalization, endpoint request shapes, status-derived
logic, and unknown JSONL field normalization. Coverage is enforced at 80% for
`src/api` and `features/crawler/lib`.

## Code Review Checklist

1. Run `npm run lint`, `npm run test:coverage`, and `npm run build`.
2. Confirm no filesystem path or PID is rendered.
3. Confirm active polling stops or slows at terminal states.
4. Confirm mobile controls and task content remain visible.
5. Confirm `VITE_API_BASE_URL` defaults to same-origin.

## Scenario: Sanitized Research Result HTML

### 1. Scope / Trigger

Apply when displaying `research_tasks.result.summary_html`, which is derived
from model-controlled Markdown by the backend.

### 2. Signatures

```text
sanitizeResearchHtml(value: string) -> string
ResearchResultCard(result: { summary_markdown?: string, summary_html?: string })
```

### 3. Contracts

- The API response is validated with Zod and the HTML is sanitized with a
  narrow tag/attribute allow-list and `http`/`https`/anchor URL policy.
- The browser runs DOMPurify again before using `dangerouslySetInnerHTML`.
- The component provides a Markdown view for audit/copy and a text fallback if
  HTML is absent or empty.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| `<script>`, event attribute, iframe, or unsafe URL | Removed or escaped before DOM insertion |
| Missing HTML but Markdown exists | Show the Markdown fallback; API compatibility normally supplies HTML |
| Invalid API result shape | Zod response error, never a cast or mock result |
| 390px viewport | HTML, Markdown toggle, and primary controls remain reachable |

### 5. Good / Base / Bad Cases

- Good: headings, lists, code, tables, and safe links render; Markdown remains
  available through the toggle.
- Base: an older result with only `summary` remains readable as text.
- Bad: inject `result.summary`, allow arbitrary attributes, or hide a failed
  sanitizer behind a fake empty report.

### 6. Tests Required

- Test HTML rendering and script removal in `research-tasks-page.test.tsx`.
- Test API schema parsing for both explicit format fields and legacy results.
- Test the Markdown toggle and empty/fallback state at a narrow viewport.

### 7. Wrong vs Correct

Wrong:

```tsx
<div dangerouslySetInnerHTML={{ __html: result.summary_html }} />
```

Correct:

```tsx
const safeHtml = DOMPurify.sanitize(result.summary_html, allowListOptions)
<div dangerouslySetInnerHTML={{ __html: safeHtml }} />
```
