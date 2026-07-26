# Crawler task API contract

All endpoints are under `/api`. This phase supports only Bilibili keyword
search. The API never accepts commands, executable paths, cookies, output
paths, comment controls, or concurrency controls.

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

Validation:

* `platform` must be `bili`.
* `crawler_type` must be `search`.
* `keywords` must contain 1–200 printable, non-whitespace characters.
* `requested_count` must be an integer from 1 through 20.
* Unknown fields are rejected with HTTP 422.
* `login_type=qrcode`, crawler concurrency `1`, and disabled first-/second-level
  comments are enforced by the service.

The response is HTTP 201 with the created task. Initial status is `pending`.

## List and inspect tasks

* `GET /api/crawler/tasks` returns all tasks newest first.
* `GET /api/crawler/tasks/{task_id}` returns one task or HTTP 404.

Statuses are `pending`, `running`, `waiting_login`, `succeeded`, `failed`, and
`cancelled`.

Task fields:

```json
{
  "id": "uuid",
  "platform": "bili",
  "crawler_type": "search",
  "keywords": "AI Agent",
  "login_type": "qrcode",
  "status": "pending",
  "requested_count": 20,
  "actual_count": 0,
  "output_dir": "/var/lib/mediaops/crawler-output/tasks/uuid",
  "log_path": "/var/log/mediaops/crawler/uuid.log",
  "qrcode_path": "/var/lib/mediaops/qrcodes/uuid.png",
  "pid": null,
  "error_message": null,
  "created_at": "2026-07-26T00:00:00Z",
  "started_at": null,
  "finished_at": null,
  "cancel_requested": false
}
```

## Logs

`GET /api/crawler/tasks/{task_id}/logs`

Query options:

* `offset=N` reads at most 256 KiB from byte offset `N`; the
  `X-Next-Offset` response header identifies the next byte.
* `tail=N` returns the last `N` lines, where `N` is at most 1000.
* `offset` and `tail` cannot be combined.

The server uses only the log path generated for that task. Missing logs return
HTTP 404; invalid stored paths return HTTP 409.

## QR code

`GET /api/crawler/tasks/{task_id}/qrcode`

When available, this returns `image/png`. Before creation it returns HTTP 404:

```json
{
  "status": "running",
  "detail": "QR code is not available yet"
}
```

The route never accepts or returns an arbitrary requested file.

## Results

`GET /api/crawler/tasks/{task_id}/results?offset=0&limit=20`

`offset` is a JSONL record offset. `limit` is from 1 through 100. Files are
read incrementally from the task's own directory.

```json
{
  "items": [{"id": 1}],
  "offset": 0,
  "limit": 20,
  "next_offset": 1,
  "has_more": false
}
```

## Cancel

`POST /api/crawler/tasks/{task_id}/cancel`

Only `pending`, `running`, and `waiting_login` tasks can be cancelled.
Pending tasks become `cancelled` immediately. Active tasks set
`cancel_requested=true`; the worker terminates the subprocess and finalizes
the status. Invalid state transitions return HTTP 409.

## Web workbench integration

The React workbench consumes this contract without a separate frontend-only
API:

* The overview computes task totals and status counts from
  `GET /api/crawler/tasks`; there is no statistics endpoint.
* Active task details (`pending`, `running`, or `waiting_login`) are polled.
  High-frequency detail polling stops after a terminal state.
* The log viewer requests `tail=300`, renders the response as plain text, and
  never inserts log content as HTML.
* A QR-code HTTP 404 is treated as an expected "not ready" state. PNG responses
  are held in a short-lived browser object URL and are not persisted.
* The result browser uses `offset` and `limit=12`, and reads only one page at a
  time. JSONL result fields are optional and are normalized defensively.
* The create form sends exactly `platform`, `crawler_type`, `keywords`, and
  `requested_count`. Fixed login and worker constraints are not user inputs.

Although task responses include worker-owned filesystem paths and `pid` for
operations use, the web workbench does not display those fields. External
result links and cover URLs are accepted only when their scheme is HTTP or
HTTPS.
