# Crawler task API contract

All endpoints are under `/api`. Platform availability comes from the backend
Adapter registry; clients must not maintain an independent allowlist. The API
never accepts commands, executable paths, cookies, output paths, proxy/comment
controls, or concurrency controls.

## Capabilities

`GET /api/crawler/capabilities`

```json
{
  "max_concurrent_tasks": 1,
  "platforms": [
    {
      "platform": "bili",
      "display_name": "哔哩哔哩",
      "icon_label": "哔",
      "enabled": true,
      "verification_status": "production_verified",
      "availability_status": "enabled",
      "login_prompt": "使用哔哩哔哩客户端扫码登录",
      "crawler_types": [{"value": "search", "label": "关键词搜索"}],
      "login_types": [{"value": "qrcode", "label": "二维码登录"}],
      "requested_count": {"minimum": 1, "maximum": 20, "default": 20},
      "supports_comments": false,
      "supports_sub_comments": false
    }
  ]
}
```

The registry contains `bili`, `xhs`, `dy`, `zhihu`, `wb`, `tieba`, and `ks`.
Verification maturity is independent of availability:

```text
verification_status:
  not_implemented | code_ready | production_verified

availability_status:
  enabled | disabled | deferred_resource_constrained |
  deferred_upstream_breakage | deferred_login_required
```

`bili`, `xhs`, and `zhihu` are production-verified. Zhihu was verified on
2026-07-28 by task `bb63be5c-0a9b-48e2-bde5-b20bdaf637e6`, which returned five
normalized answer/article results. `dy` is code-ready, disabled, and
`deferred_resource_constrained`. `wb`, `tieba`, and `ks` remain code-ready and
disabled until each production rollout explicitly enables and verifies it.
`enabled=false` always prevents task submission.

## Create a task

`POST /api/crawler/tasks`

```json
{
  "platform": "bili",
  "crawler_type": "search",
  "keywords": "AI Agent",
  "requested_count": 20
}
```

`platform` must be registered and enabled; disabled platforms return HTTP 409
and unsupported platforms return HTTP 422. `crawler_type` must be a capability
advertised for that platform. Keywords contain 1–200 printable,
non-whitespace characters; count is an integer from 1 through 20. Unknown
fields are rejected.

The service fixes `login_type=qrcode`, global crawler concurrency `1`, and
disables first-/second-level comments and proxies. HTTP 201 returns the task
with initial status `pending`.

## List and inspect tasks

- `GET /api/crawler/tasks` returns tasks newest first.
- `GET /api/crawler/tasks/{task_id}` returns one task or HTTP 404.

Statuses are `pending`, `running`, `waiting_login`, `succeeded`, `failed`, and
`cancelled`. Existing Bilibili rows retain their IDs, fields, timestamps,
paths, counts, and status through the multi-platform migration. Task responses
still include worker-owned paths and PID for operational compatibility, but
the workbench does not display them.

## Logs and QR code

`GET /api/crawler/tasks/{task_id}/logs` accepts either `offset=N` (at most
256 KiB, next position in `X-Next-Offset`) or `tail=N` (1–1000 lines). Paths
are reconstructed inside the configured task log root.

`GET /api/crawler/tasks/{task_id}/qrcode` returns `image/png` when ready.
Before creation it returns HTTP 404 with the current task status and a
not-ready detail. It never accepts or returns an arbitrary file path.

## Unified results

`GET /api/crawler/tasks/{task_id}/results?offset=0&limit=20`

The backend reads platform content JSONL incrementally, normalizes each record
through its Adapter, and never returns more than `requested_count`. `limit` is
1–100.

```json
{
  "items": [{
    "platform": "bili",
    "content_id": "BV123",
    "content_type": "video",
    "title": "Example",
    "description": null,
    "author_name": "Uploader",
    "content_url": "https://www.bilibili.com/video/BV123",
    "cover_url": "https://example.test/cover.jpg",
    "published_at": 1700000000,
    "source_keyword": "AI Agent",
    "raw_payload": {
      "video_id": "BV123",
      "title": "Example"
    },
    "metrics": {
      "play_count": 100,
      "like_count": 10,
      "favorite_count": 5,
      "comment_count": 2,
      "share_count": 1
    }
  }],
  "offset": 0,
  "limit": 20,
  "next_offset": 1,
  "has_more": false
}
```

Missing source fields become empty or `null`. Unsafe non-HTTP(S) content and
cover URLs become `null`. `raw_payload` is the stored, privacy-normalized JSONL
object; the workbench renders its JSON as text and never executes HTML.

## Cancel and polling

`POST /api/crawler/tasks/{task_id}/cancel` only accepts `pending`, `running`,
or `waiting_login`. Pending tasks cancel immediately; active tasks set
`cancel_requested` and the Worker terminates the subprocess.

The workbench polls active details, bounded logs, and pending QR images. It
stops high-frequency detail polling at terminal status and pages results with
`offset`/`limit=12`. The create form is generated from the capabilities route
and sends exactly `platform`, `crawler_type`, `keywords`, and
`requested_count`.
