# External Agent API v1

The stable Agent API is under `/api/v1`. It is backed by
`app.services.agent_tools.AgentToolService`, not React components or ORM
objects. OpenAPI is available at `/docs` and `/openapi.json`.

## Authentication

Send a scoped key:

```http
X-API-Key: pmo_<prefix>_<secret>
```

Do not put keys in URLs. Library calls require `library:read`, intelligence
calls require `intelligence:read`, and subscription calls require
`subscriptions:read`. Revoked/expired keys return 401. Missing scopes return
403. The full key is never retrievable after creation.

## Resources

```text
GET /api/v1/library/search
GET /api/v1/library/contents/{id}
GET /api/v1/library/contents/{id}/provenance
GET /api/v1/library/creators/{id}
GET /api/v1/library/creators/{id}/activity
GET /api/v1/library/comments
GET /api/v1/intelligence/trends
GET /api/v1/intelligence/briefs/latest
GET /api/v1/subscriptions
GET /api/v1/subscriptions/{id}
```

Search supports `q`, platform, tag, favorite, offset, and bounded limit.
Paged success responses use:

```json
{
  "data": [],
  "meta": {
    "offset": 0,
    "limit": 20,
    "next_offset": 0,
    "has_more": false
  }
}
```

Single resources use `{"data": {...}}`. Errors use:

```json
{"error":{"code":"not_found","message":"Content not found"}}
```

Times are UTC ISO-8601 strings. Content and creator records return stable
internal IDs plus nested platform source ID/URL, first/last collection time,
nullable metrics, and provenance. Raw payload, filesystem paths, log paths,
cookies, process IDs, and browser state are never returned.

Callers should pass abort signals and enforce their own reasonable request
timeout. Lists are bounded to 100 records per call. Existing `/api/library`
and `/api/crawler` contracts remain available for the workbench; consumers
that need a stable external contract should use v1.
