# Crawler Platform Contract

## 1. Scope / Trigger

Apply this contract when adding a crawler platform, changing Runner arguments,
normalizing MediaCrawler JSONL, or exposing platform choices to the frontend.

## 2. Signatures

```text
GET  /api/crawler/capabilities
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
MEDIAOPS_ENABLED_PLATFORMS=bili[,xhs,zhihu,wb,tieba,ks]
DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS=<finite positive seconds; default 180>
```

Adapters implement capability metadata, fixed Runner arguments,
`is_login_success(line)`, content-file discovery, and `normalize_result(raw)`.

## 3. Contracts

- Registry keys are `bili`, `xhs`, `dy`, `zhihu`, `wb`, `tieba`, and `ks`; it
  is the backend source of truth.
- Verification is `not_implemented`, `code_ready`, or
  `production_verified`. Availability is independently `enabled`, `disabled`,
  `deferred_resource_constrained`, `deferred_upstream_breakage`, or
  `deferred_login_required`. `enabled` is the actual task-submission gate.
- `bili` and `xhs` are `production_verified`; `dy` is `code_ready` and
  `deferred_resource_constrained`; the four stage-five adapters remain
  `code_ready` until a real task is recorded.
- Only explicitly enabled platforms accept new tasks; the default is `bili`.
- Search, QR login, count `1..20`, one global task, no comments, no
  sub-comments, and no proxy are fixed service constraints.
- The Worker calls fixed Python and Runner paths with an argument array.
- The existing Bilibili Runner argument contract remains compatible. Proxy is
  disabled inside the reviewed Runner, not exposed as a new Worker argument.
- Browser headfulness is a per-Adapter capability passed as `--headless`:
  `bili` and `xhs` are headless, `dy` is headful because douyin.com serves a
  captcha interstitial to headless browsers. The reviewed Runner re-execs
  itself under `xvfb-run` when a headful run has no `DISPLAY`, so the host
  needs `xvfb`; API callers never choose this value. A Runner installed before
  the matching Worker restarts defaults a missing `--headless` argument to the
  historical headless mode for deployment-window compatibility.
- Douyin may redirect again after its initial `goto()` completes, destroying
  the JavaScript execution context while MediaCrawler reads the user agent.
  The reviewed Runner installs an in-process integration patch only for `dy`:
  the exact Playwright `Execution context was destroyed` error waits for
  `domcontentloaded` and retries client creation at most three times. Other
  Playwright errors and retry exhaustion propagate unchanged; MediaCrawler
  source files are never edited.
- Douyin's visible login entry keeps the exact text `登录`, but its HTML tag is
  not stable. The Runner first accepts the automatically visible
  legacy `#login-panel-new` or current `[id^="login-full-panel-"]`; otherwise
  it examines exact-text entries every 0.5 seconds for at most 40 scans to span
  the WAF reload window, clicks only a visible one with a short timeout, and
  confirms either supported dialog became visible. Missing entries and failed
  dialog confirmation fail explicitly without fuzzy matching or an unbounded
  retry.
- Douyin's WAF proof-of-work can monopolize a small single-core host. After
  Xvfb re-exec, the Runner applies a non-privileged `nice +10` only to the
  `dy` process so Chromium descendants cannot starve API, Worker, and SSH
  control traffic. Other platforms keep their existing priority; failure to
  lower Douyin priority stops before browser startup.
- The Worker terminates the full Douyin process group if its QR code is not
  ready within `DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS` (180 seconds by
  default). This startup deadline applies only before the QR code appears; an
  operator's scan window remains unbounded by this guard.
- Resource-constrained production keeps `dy` registered as `code_ready` but
  excludes it from `MEDIAOPS_ENABLED_PLATFORMS`. Cookie login is not a resource
  fallback because MediaCrawler still launches Chromium and it would introduce
  sensitive browser state.
- Each Adapter owns display/icon metadata, the unavailable state, login prompt,
  storage directories, default small count, headless mode, finite pre-QR
  startup timeout, login-line classification, normalization, and raw payload.
  The four new store directories are `zhihu`, `weibo`, `tieba`, and
  `kuaishou`.
- The Runner wraps the selected upstream client's read-only `pong` method and
  emits `[MediaOps] Existing login state ready: <platform>` only when the
  persisted state is valid. It never logs Cookie values. The Worker uses that
  marker plus Adapter classifiers to distinguish persisted login, QR waiting,
  captcha, expiration, and timeout without platform branches.
- Pre-QR timeout and cancellation terminate the whole process group. Seeing a
  QR file changes the task to `waiting_login`; seeing success returns it to
  `running`. A success marker before any QR disables the startup deadline.
- Numeric result fields accept non-negative integers plus platform display
  forms such as `1,544`, `1000+`, `5.7万`, `1.2w`, and `3亿`. Abbreviated
  values use a bounded decimal format; malformed, negative, non-finite, or
  oversized strings normalize to `null` instead of failing result reads.
- Result items use the unified Pydantic schema and are read incrementally,
  path-checked, paginated, and capped at `requested_count`.
- `raw_payload` is the privacy-normalized JSONL object. Textual publication
  times accept ISO-8601 and `YYYY-MM-DD[ HH:MM:SS]` as UTC; malformed values
  become `null`. React may show raw JSON only as escaped text.

## 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Unknown platform | Task API returns 422 |
| Registered but disabled platform | Task API returns 409 |
| Unknown enabled-platform config | API/Worker startup fails |
| Unsafe stored result path | Results API returns 409 |
| Invalid JSONL object | Results API returns 500 |
| QR-save log line | Task remains `waiting_login` |
| `Login successful` log line | Task returns to `running` |
| Headful run without `DISPLAY`, `xvfb-run` available | Runner re-execs once under `xvfb-run -a` |
| Headful run without `DISPLAY` or `xvfb-run` | Runner exits before MediaCrawler import or output mutation |
| Xvfb-wrapped run still has no `DISPLAY` | Runner exits explicitly; never loops or silently continues |
| Douyin client creation hits the exact navigation-context race | Wait for `domcontentloaded`; retry up to the fixed limit |
| Douyin client creation hits another Playwright error | Propagate immediately without retry |
| Douyin navigation race exceeds three attempts | Propagate the final error and fail the task |
| Douyin login dialog is already visible | Continue without clicking another entry |
| Douyin login entry is briefly absent during the WAF reload | Poll every 0.5 seconds for at most 40 scans |
| Douyin login entry tag changes but exact visible text remains | Click the visible exact-text entry and confirm the dialog |
| Douyin has no visible exact-text entry or no dialog after click | Fail explicitly after bounded attempts |
| Douyin WAF proof-of-work runs on a small host | Apply `nice +10` only to the `dy` process after Xvfb wrapping |
| Douyin process priority cannot be lowered | Exit before browser startup with an explicit error |
| Douyin QR code is not ready before its startup deadline | Terminate the task process group and persist an explicit failure |
| Douyin QR code becomes ready before its startup deadline | Stop applying the startup deadline while the operator scans |
| Existing platform login state is valid | Emit the non-sensitive ready marker and do not wait for QR |
| Adapter detects captcha, expired login, or login timeout | Terminate the process group and persist a normalized failure |
| Malformed or oversized metric text | Normalized metric is `null` |
| Malformed textual publication time | Normalized publication time is `null` |

## 5. Good / Base / Bad Cases

- Good: add one Adapter, register it once, test normalized sample output, then
  let the capability API drive the UI.
- Good: render `production_verified + disabled` as verified and unavailable;
  enabled state does not erase verification history.
- Base: a missing optional raw field becomes `null` or an empty display value.
- Bad: hard-code a platform list in the frontend or pass Cookie/path/command
  controls through the task API.
- Bad: hard-code every platform to headless or continue a headful run after an
  Xvfb wrapper failed to establish `DISPLAY`.
- Bad: modify `/opt/mediacrawler` to add sleeps, retry every Playwright error,
  or loop indefinitely around browser startup.

## 6. Tests Required

Test registry truthfulness for all seven platforms, disabled/unknown platforms,
fixed commands, platform JSONL samples, raw payloads, timestamp/null semantics,
unsafe URLs/paths, QR progression, result caps, and
cross-platform competing claims. Assert per-platform `--headless` arguments,
legacy missing-argument compatibility, Xvfb re-exec/failure paths, abbreviated
metric parsing, malformed/oversized metric rejection, Douyin navigation-race
recovery, unrelated-error propagation, bounded retry exhaustion, automatic
Douyin login-dialog detection, visible exact-text fallback, and missing-entry
failure. Assert that only Douyin receives the fixed niceness increment and
that priority failures are explicit. Worker tests must assert that a pre-QR
timeout terminates the subprocess and persists failure, a ready QR code or
persisted-login marker disables that deadline, captcha terminates the process
group, and Bilibili/Xiaohongshu are unaffected. Configuration
tests must reject zero, negative, NaN, and infinite deadlines. Real platform
tests require explicit authorization and are not part of unit tests.

## 7. Wrong vs Correct

Wrong:

```typescript
const platforms = ["bili", "xhs", "dy"];
```

Correct:

```typescript
const capabilities = await getCrawlerCapabilities(signal);
const platforms = capabilities.platforms;
```

Wrong:

```python
config.HEADLESS = True
```

Correct:

```python
config.HEADLESS = args.headless
config.CDP_HEADLESS = args.headless
```

Wrong:

```python
# Editing MediaCrawler core or retrying every browser failure hides real bugs.
while True:
    await crawler.create_douyin_client(proxy)
```

Correct:

```python
if args.platform == "dy":
    install_douyin_navigation_retry()
```

Wrong:

```python
# Cookie login still launches Chromium and adds sensitive browser state.
enabled_platforms = ("bili", "xhs", "dy")
login_type = "cookie"
```

Correct:

```text
MEDIAOPS_ENABLED_PLATFORMS=bili,xhs
DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS=180
```
