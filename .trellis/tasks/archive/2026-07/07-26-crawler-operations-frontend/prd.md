# Crawler Operations Frontend

## Objective

Build the phase-three web workbench for the existing Personal Media Ops FastAPI
service. Users must be able to create a constrained Bilibili keyword crawler
task, monitor it through QR-code login and execution, inspect bounded logs, and
browse paginated JSONL results.

## Confirmed API contract

The implementation must use the repository's generated FastAPI OpenAPI schema:

- `GET /api/health`
- `GET|POST /api/crawler/tasks`
- `GET /api/crawler/tasks/{task_id}`
- `GET /api/crawler/tasks/{task_id}/logs` with `offset` or `tail`
- `GET /api/crawler/tasks/{task_id}/qrcode`
- `GET /api/crawler/tasks/{task_id}/results` with `offset` and `limit`
- `POST /api/crawler/tasks/{task_id}/cancel`

Task statuses are `pending`, `running`, `waiting_login`, `succeeded`, `failed`,
and `cancelled`. Task lists are returned as a JSON array. Results are returned
as `{items, offset, limit, next_offset, has_more}`. Logs are plain text.

## Scope

### Application foundation

- Create `frontend/` with React, Vite, TypeScript, Tailwind CSS, React Router,
  TanStack Query, and a small reusable shadcn-style component layer.
- Default API base URL to same-origin and support `VITE_API_BASE_URL`.
- Proxy local `/api` requests to `http://127.0.0.1:8000`.
- Produce deployable files in `frontend/dist`.

### Routes

- `/`: real task-derived metrics, recent tasks, and API/task-derived engine
  state.
- `/crawler/tasks`: searchable and filterable task list with task creation.
- `/crawler/tasks/:taskId`: task metadata, bounded live logs, QR login, paged
  results, and cancellation.

### Task creation

- Submit only `{platform: "bili", crawler_type: "search", keywords,
  requested_count}`.
- Keep platform, crawler type, and QR login fixed in the UI.
- Validate keywords and count (1–20), prevent duplicate submissions, then
  navigate to the created task.

### Runtime behavior

- Poll active tasks and stop high-frequency polling when terminal.
- Fetch QR images as short-lived blobs without local persistence; treat 404 as
  "not ready".
- Request at most 300 log lines per refresh and render as plain text.
- Request result pages using backend `offset` and `limit`; never load the full
  JSONL file.
- Safely degrade when result records omit expected MediaCrawler fields.

### Security and privacy

- Never render log or result content as HTML.
- Accept only HTTP(S) result and image URLs.
- Do not expose filesystem paths or PID in the UI.
- Do not provide Cookie, command, path, concurrency, comments, or arbitrary
  platform controls.
- Do not persist QR codes or sensitive task data in local storage.
- Do not add mock fallbacks to production requests.

### Documentation

Update the root README and API/deployment docs with local frontend startup,
Vite proxy behavior, production build, same-origin Nginx/BaoTa static hosting,
and `/api` reverse proxy requirements.

## Verification

- `npm run build`
- `npm run lint`
- `npm run test`
- `npm run test:coverage` with at least 80% coverage for the API and crawler
  data-normalization modules
- `uv run pytest` in `backend/`
- Browser smoke/visual checks for dashboard, task list, task detail, and narrow
  layout against a deterministic local API stub
- Production output is exactly `frontend/dist`

## Out of scope

- AI analysis or SDKs
- Automated publishing
- Platforms other than Bilibili search
- Comments, custom concurrency, Cookie entry, custom commands, or file paths
- Changes to MediaCrawler
- New backend behavior unless verification reveals a concrete defect
