# Current Cross-Layer Contract Audit

## Registry and API

`backend/app/crawler/adapters.py` is the current source of platform metadata and
contains Bilibili, Xiaohongshu, and Douyin adapters. The FastAPI route already
delegates supported/enabled checks and result normalization to the registry,
which is the correct extension point.

The current capability response has one `verification_status` dimension with
the values `verified` and `code_ready`, plus `enabled`. That cannot represent
Douyin's required simultaneous state:

```text
code_ready + deferred_resource_constrained + enabled=false
```

Stage five will use two explicit dimensions:

- verification maturity:
  `not_implemented | code_ready | production_verified`
- availability:
  `enabled | disabled | deferred_resource_constrained |
  deferred_upstream_breakage | deferred_login_required`

The existing `enabled` boolean remains as a direct submission gate. The
registry will also expose icon text and platform-specific login guidance so
React does not need an independent platform allowlist.

## Adapter and Result Model

Adapters currently own:

- platform and display name;
- storage-directory discovery;
- fixed Runner argument construction;
- headless mode;
- login-success log recognition;
- JSONL discovery and normalization.

Four new adapters belong in the same registry. Shared parsing helpers should
handle URLs, numeric metrics, publication times, and null semantics. The
unified result model needs an explicit `raw_payload` dictionary containing the
privacy-normalized stored JSONL record.

Tieba publication time can be a string rather than an integer timestamp.
Timestamp normalization must accept bounded numeric or known textual formats
and return `null` for malformed values instead of failing result reads.

## Runner and Worker

`scripts/crawler/run_mediacrawler.py` already translates the common fixed
arguments and isolates output per task, but its platform choices currently
list only Bilibili, Xiaohongshu, and Douyin. The generic path supports the four
new upstream platform codes once choices and Adapter metadata are extended.
Douyin-specific navigation, login-dialog, Xvfb, and niceness workarounds remain
isolated to Douyin.

The Worker currently contains a direct `platform == "dy"` branch for the
pre-QR startup deadline. Stage five will move this value into Adapter metadata
and use one generic deadline state machine:

- QR pending;
- QR ready and operator may scan;
- persisted login or login success;
- login failure/captcha signal;
- pre-QR timeout;
- process completion/cancellation.

This preserves Douyin's 180-second guard while avoiding new platform branches
in the Worker loop.

The repository claim transaction already enforces one global active task.
Cancellation and timeout terminate the whole process group.

## Frontend

`frontend/src/api/crawler.ts` validates capabilities and result items with Zod.
The create dialog is already capability-driven and refuses disabled options.
Stage five must expand the schema for the two status dimensions, platform
metadata, login hints, and `raw_payload`.

The existing result browser renders React text, restricts links to HTTP(S),
uses `noopener noreferrer`, and has image-error fallback. It does not use
`dangerouslySetInnerHTML`; these properties must be preserved.

The task list currently filters by task status and search text only. Platform
filtering will be capability-driven. Task details currently use one generic QR
prompt and must render the capability-provided login hint.

## Compatibility Constraints

- Existing Bilibili/Xiaohongshu task and result contracts remain valid.
- Douyin stays registered, disabled, code-ready, and deferred for resources.
- The task API continues accepting only search, QR login, bounded counts, and
  fixed safe runtime options.
- Unavailable and unknown platforms remain different API errors.
- No Cookie, browser-state path, executable path, proxy, comment, or
  concurrency control is exposed to the user-facing API.
