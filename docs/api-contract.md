# Crawler and library API contract

All endpoints are under `/api`. The API is an internal, same-origin contract
for the Personal Media Ops workbench and future read-only Agent tools.
Platform and mode availability comes only from the backend Adapter registry;
clients must not maintain an independent allowlist.

## Mode-level capabilities

`GET /api/crawler/capabilities`

Each of `bili`, `xhs`, `zhihu`, `wb`, `tieba`, `ks`, and `dy` returns exactly
five mode records:

```text
search | detail | creator | comments | sub_comments
```

Each record contains its own `status`, `enabled`, input fields, bounded count
contract, browser/login requirements, and an optional reason:

```json
{
  "platform": "bili",
  "display_name": "哔哩哔哩",
  "enabled": true,
  "verification_status": "production_verified",
  "availability_status": "enabled",
  "modes": [
    {
      "mode": "comments",
      "label": "一级评论",
      "status": "enabled",
      "enabled": true,
      "reason": null,
      "input_fields": ["parent_content_id", "target_ids", "target_urls"],
      "requested_count": {"minimum": 1, "maximum": 20, "default": 1},
      "requested_comment_count": {
        "minimum": 1,
        "maximum": 10,
        "default": 10
      },
      "requested_sub_comment_count": null,
      "requires_browser": true,
      "login_type": "qrcode"
    }
  ]
}
```

Mode states are:

```text
not_implemented | code_ready | enabled | production_verified |
deferred_resource_constrained | deferred_upstream_breakage |
deferred_login_required | deferred_platform_change | disabled
```

`code_ready` means reviewed code and tests exist. `enabled` additionally means
the platform is present in `MEDIAOPS_ENABLED_PLATFORMS`.
`production_verified` requires a recorded small real task for that exact
platform × mode. Platform-level legacy fields remain for old clients and
summarize search only.

## Create a task

`POST /api/crawler/tasks`

The preferred discriminator is `mode`; legacy `crawler_type` remains accepted
when it matches `mode`. Unknown fields are rejected. The API performs
mode-specific validation before a task can enter the Worker:

```json
{"platform":"bili","mode":"search","keywords":"AI Agent","requested_count":5}
```

```json
{
  "platform": "bili",
  "mode": "detail",
  "target_urls": ["https://www.bilibili.com/video/BV123"],
  "requested_count": 1
}
```

```json
{"platform":"bili","mode":"creator","creator_ids":["123"],"requested_count":1}
```

```json
{
  "platform": "bili",
  "mode": "comments",
  "parent_content_id": "BV123",
  "requested_comment_count": 10
}
```

```json
{
  "platform": "bili",
  "mode": "sub_comments",
  "parent_content_id": "BV123",
  "parent_comment_id": "456",
  "requested_sub_comment_count": 5
}
```

Rules:

- search accepts `keywords`;
- detail accepts `target_ids` or `target_urls`; total targets cannot exceed
  `requested_count`;
- creator accepts `creator_ids` or `creator_urls`; total targets cannot exceed
  `requested_count`;
- comments accepts exactly one content ID/URL and 1–10 comments;
- sub-comments accepts exactly one content target, one parent comment ID, and
  1–5 replies;
- comments never imply sub-comment recursion;
- disabled/deferred modes return HTTP 409;
- invalid fields or unsupported platforms return HTTP 422;
- URLs must be credential-free HTTP(S), must use a hostname allow-listed by
  the selected Adapter, and Adapter-specific URL requirements are revalidated;
- an HTTP URL cannot be smuggled through an ID/parent-ID field;
- caller-controlled commands, paths, cookies, proxy settings, concurrency, or
  recursive-comment flags are never accepted.

Task responses include both `mode` and the legacy `crawler_type`, all
mode-specific inputs, requested counts, state, timestamps, and operational
paths. Sensitive query values such as token/cookie/signature parameters are
removed from returned target URLs. Old search rows remain readable.

## Task operations

- `GET /api/crawler/tasks`
- `GET /api/crawler/tasks/{task_id}`
- `POST /api/crawler/tasks/{task_id}/cancel`
- `GET /api/crawler/tasks/{task_id}/logs`
- `GET /api/crawler/tasks/{task_id}/qrcode`
- `GET /api/crawler/tasks/{task_id}/results`

Statuses remain `pending`, `running`, `waiting_login`, `succeeded`, `failed`,
and `cancelled`. Logs are bounded to 256 KiB per offset request or 1–1000 tail
lines. QR responses are PNG only. The legacy result endpoint continues to
normalize content JSONL for old tasks; new durable consumers should use the
library endpoints.

A process exit code of zero is not sufficient for success. The Worker requires
parseable expected output, normalized records or a platform-proven legal empty
comment result, an atomic library write, and task provenance before marking
the task succeeded. Unexplained zero results fail closed.

## Persistent library

### Content

`GET /api/library/contents`

Supported filters:

```text
platform content_type keyword creator date_from date_to
has_comments sort offset limit
```

`sort` is one of `last_collected_desc`, `published_desc`, `published_asc`, or
`first_collected_desc`. `limit` is 1–100. The response uses the same
`items/offset/limit/next_offset/has_more` pagination shape as other lists.
List responses never contain raw payloads.

`GET /api/library/contents/{id}` returns the stable library ID, source
platform/ID/URL, safe normalized fields, nullable metrics, first/last
collection timestamps, one linked creator, up to 100 stored comments, and
task provenance. `include_raw=true` explicitly adds the JSON object for
developer diagnosis; default is `null`.

### Creators

- `GET /api/library/creators?platform=&query=&offset=&limit=`
- `GET /api/library/creators/{id}`

Creator detail includes linked normalized contents and task provenance.
`include_raw=true` is explicit and off by default.
Creator-mode capture follows the pinned MediaCrawler teaching edition's
privacy boundary: source user IDs are hashed, nicknames are masked, and only
non-identifying aggregate counts are retained. Avatar, profile URL, biography,
gender, IP location, browser state, and URL tokens are not persisted.

### Comments and counts

- `GET /api/library/comments`
- `GET /api/library/stats`

Comments filter by platform, source content ID, or parent comment ID. Raw
comment payloads are not returned by the list contract. Missing metrics remain
`null`; a real zero remains `0`.

## Safety and rendering

The API uses stable application UUIDs while retaining string source IDs and
original HTTP(S) links. All SQL values are parameterized; sort expressions and
table/column identifiers come from internal allowlists. Raw payloads are
stored for provenance but are never treated as trusted HTML. React renders
titles, descriptions, creator bios, and comments as text; external links open
with `noopener`, and invalid image URLs degrade to a placeholder.
