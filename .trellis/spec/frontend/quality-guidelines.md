# Quality Guidelines

> Code quality standards for frontend development.

## Overview

Frontend changes must pass ESLint, strict TypeScript production build, Vitest,
the configured coverage gate, and proportional browser layout checks.

## Forbidden Patterns

- `any`, silent type assertions around API data, or ignored request errors.
- `dangerouslySetInnerHTML` for logs or result records.
- Hardcoded production hostnames, IPs, commands, Cookie controls, paths, or
  concurrency controls.
- Unbounded log or JSONL loading.
- Production-default mock responses.

## Required Patterns

- Validate API JSON with Zod.
- Send request cancellation signals.
- Restrict external URLs to HTTP(S).
- Use plain-text rendering for untrusted strings.
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
