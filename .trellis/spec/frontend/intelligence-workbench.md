# Intelligence Workbench Contract

## 1. Scope / Trigger

Apply this contract when changing authenticated routing, the command/today
views, subscriptions, trends, creator watchlist, collections, API-key
management, or the stage-seven responsive visual system.

## 2. Signatures

```text
AuthProvider -> GET /api/auth/session
LoginPage    -> POST /api/auth/login
AppShell     -> ten capability routes

/                    command center
/today               today's intelligence
/subscriptions       subscription center
/library             content library
/trends              trend radar
/creators            creator watch
/collections         topic collections
/tasks               collection center
/integrations        Agent and integrations
/system              system status
```

API modules under `src/api` validate every response with Zod and accept an
`AbortSignal` for reads.

## 3. Contracts

- The session token exists only in the HttpOnly cookie. `AuthProvider` keeps
  the CSRF token in memory and blocks protected routes until session discovery
  completes. A 401 dispatches one shared unauthorized event.
- Navigation and platform choices come from implemented product capabilities;
  data cards use real API values and never synthetic dashboard metrics.
- API-key creation shows the complete value exactly once in the creation
  result. Later lists render only name, prefix, scopes, dates, and revocation.
- Trend cards display status, time window, platforms, score components,
  evidence contents, and `insufficient_data` without promotional AI language.
- The visual system uses mist/warm-gray surfaces, graphite text, teal/cyan
  primary states, and restrained orange warnings through shared CSS tokens.
  The 390 px layout keeps all ten routes reachable through a horizontal
  overflow navigation rail.
- Untrusted titles, descriptions, comments, and evidence render through React
  text nodes. External links are limited to validated HTTP(S) values and use
  `noopener noreferrer`.
- Planned MCP and Notion surfaces are informational status only; they do not
  simulate a connected integration.

## 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Session discovery is pending | Show neutral loading state |
| Session is absent or expires | Show login; clear protected query state |
| Login fails | Render the real normalized API error |
| Unsafe mutation | Send in-memory CSRF with cookie credentials |
| API response violates Zod | Throw HTTP-like 502 contract error |
| Request aborts | Preserve `AbortError` |
| Trend has insufficient evidence | Label it `insufficient_data` |
| Complete key was already dismissed | Never render it again |
| 390 px viewport | Navigation and primary actions remain reachable |

## 5. Good / Base / Bad Cases

- Good: resume an existing cookie session, load real command metrics, and
  invalidate only affected TanStack Query keys after a mutation.
- Good: copy a newly created API key from the one-time panel, dismiss it, and
  see only its prefix in subsequent lists.
- Base: an empty trend/brief response renders an honest empty or unavailable
  state.
- Bad: place session/API keys in local storage, catch API errors and replace
  them with mock cards, or hard-code platform availability.
- Bad: hide the desktop sidebar at 390 px without another path to every route.

## 6. Tests Required

- Test login success/failure, session expiry/unauthorized event, logout, CSRF,
  and cookie credentials.
- Test API request shapes and Zod validation for subscriptions, organization,
  watchlist, trends, briefs, and API keys.
- Test create/edit/pause/resume/manual subscription actions, favorite/tag/
  collection mutations, creator monitoring, and brief/trend evidence display.
- Test that a full API key appears only in the creation view and revocation
  remains available from prefix-only rows.
- Test all ten navigation labels in a 390 px viewport and plain-text rendering
  of HTML-looking source content.
- Run lint, Vitest coverage (all thresholds at least 80%), and production
  TypeScript/Vite build.

## 7. Wrong vs Correct

Wrong:

```typescript
localStorage.setItem("session", token);
const trend = (await response.json()) as Trend;
```

Correct:

```typescript
const trend = await requestJson(path, trendSchema, { signal });
// The browser session remains in the HttpOnly cookie.
```
