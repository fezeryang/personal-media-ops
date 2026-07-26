# Adapter and Capability Design

## Selected Shape

Create a repository-owned crawler domain package with:

- a platform adapter protocol/base class;
- one adapter each for `bili`, `xhs`, and `dy`;
- a registry that is the only platform lookup source;
- immutable capability metadata;
- adapter-owned Runner arguments, login-success detection, content-file
  selection, and raw-to-unified result conversion.

The API, Worker, and frontend must consume this registry contract instead of
maintaining independent platform allowlists.

## Capability Contract

`GET /api/crawler/capabilities` returns:

- global maximum active browser tasks (`1`);
- each platform's key and Chinese display name;
- `enabled` state;
- verification status (`verified` or `code_ready`);
- supported crawler/login types;
- requested-count min/max/default;
- comment/sub-comment support, both false.

`MEDIAOPS_ENABLED_PLATFORMS` defaults to `bili`. XHS and Douyin remain visible
as code-ready capabilities but task creation is disabled until an operator
explicitly enables them after approval.

## Unified Result

Each result item exposes a stable shape:

- platform, content ID/type;
- title and optional description/author;
- safe content and cover URLs;
- optional publication timestamp and source keyword;
- nullable numeric play/like/favorite/comment/share metrics.

Adapters consume legacy/raw MediaCrawler JSONL, so old Bilibili output needs no
rewrite. The API reads content JSONL incrementally, normalizes one record at a
time, and caps the visible record set at the task's `requested_count`.

## Worker Behavior

- The Worker asks the registry for an enabled adapter after claiming a task.
- The fixed Python and fixed repository-owned Runner remain the only
  executables.
- Adapter values are fixed code constants; API callers cannot pass commands,
  paths, cookies, proxies, comments, or concurrency.
- QR appearance moves a task to `waiting_login`.
- Only an adapter-recognized successful-login log line moves it back to
  `running`; the QR-save log itself must not do so.
- The existing process lock and SQLite claim continue to enforce one global
  browser task across all platforms.
