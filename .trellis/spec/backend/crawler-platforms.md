# Crawler Platform Contract

## 1. Scope / Trigger

Apply this contract when adding a crawler platform, changing Runner arguments,
normalizing MediaCrawler JSONL, or exposing platform choices to the frontend.

## 2. Signatures

```text
GET  /api/crawler/capabilities
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
GET  /api/library/contents
GET  /api/library/contents/{library_id}
GET  /api/library/creators
GET  /api/library/creators/{library_id}
GET  /api/library/comments
MEDIAOPS_ENABLED_PLATFORMS=bili[,xhs,zhihu,wb,tieba,ks]
DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS=<finite positive seconds; default 180>
CRAWLER_LOGIN_TIMEOUT_SECONDS=<finite positive seconds; default 180>
```

Adapters implement mode-level capability metadata, fixed Runner arguments,
login/QR/failure classification, entity-file discovery, and content, creator,
and comment normalization.

## 3. Contracts

- Registry keys are `bili`, `xhs`, `dy`, `zhihu`, `wb`, `tieba`, and `ks`; it
  is the backend source of truth.
- Verification is `not_implemented`, `code_ready`, or
  `production_verified`. Availability is independently `enabled`, `disabled`,
  `deferred_resource_constrained`, `deferred_upstream_breakage`, or
  `deferred_login_required`. `enabled` is the actual task-submission gate.
- Each `platform × mode` cell independently uses `not_implemented`,
  `code_ready`, `enabled`, `production_verified`,
  `deferred_resource_constrained`, `deferred_upstream_breakage`,
  `deferred_login_required`, `deferred_platform_change`, or `disabled`.
  Platform-level fields remain a compatibility summary of `search`; clients
  that submit work must use the selected mode's `enabled` field.
- Task modes are `search`, `detail`, `creator`, `comments`, and
  `sub_comments`. Pydantic validates the exact input family before persistence,
  and the Adapter validates it again before a Runner command is built.
- Detail/creator target totals cannot exceed `requested_count`. HTTP targets
  must use URL fields, contain no user-info credentials, and match the
  selected Adapter's platform-host allowlist.
- `bili`, `xhs`, `zhihu`, `wb`, and `tieba` are `production_verified`; `dy`
  is `code_ready` and `deferred_resource_constrained`; `ks` is `code_ready`
  and `deferred_upstream_breakage`.
- Only explicitly enabled platforms accept new tasks; the default is `bili`.
- Search/detail/creator count is `1..20`; comments is `1..10`; standalone
  sub-comments is `1..5`. The service keeps QR login, one global task, no
  proxy, no implicit comments, and no implicit recursive sub-comments.
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
  default). This startup deadline applies only before the QR code appears.
  Once any platform QR file exists, `CRAWLER_LOGIN_TIMEOUT_SECONDS` (180
  seconds by default) bounds the wait for a success marker or a classified
  login failure. A stalled captcha/verification page therefore becomes an
  explicit platform failure and releases the single Worker; it is never
  treated as a successful crawl or an Owner-session failure.
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
- XHS QR login also preserves a bounded login-state probe around the pinned
  upstream helper. Each polling round checks a SHA-256 fingerprint of the
  allow-listed auth-cookie set (`web_session`, `id_token`, `websectiga`,
  `sec_poison_id`, `xsecappid`) before and after the upstream probe; it never
  logs or persists cookie values. The upstream probe has a two-second hard
  timeout because its verification-page content read is otherwise unbounded.
  After a QR scan plus phone-side secondary verification, a changed
  fingerprint emits the exact `Login successful` marker consumed by the
  generic Adapter/Worker state machine even when that page probe hangs or
  raises. If the bounded wait expires, it emits a login-timeout marker and
  must not let the upstream helper fall through as success.
- The pinned Bilibili detail parser accepts BV targets only even though search
  persists public AV IDs and AV URLs. The reviewed Runner resolves AV/BV
  targets centrally, sends AV values through the upstream client's `aid`
  parameter, and resolves BV to AV before standalone sub-comment persistence.
  API/Worker code does not branch on this platform difference.
- MediaCrawler opens Weibo with a mobile user agent, for which the passport
  page defaults to SMS login and does not render the QR image until the exact
  visible `扫码登录` entry is clicked. The reviewed Runner patches only the
  `wb` process's QR-discovery seam: it keeps an already visible QR, otherwise
  scans for that exact entry at most 20 times at 0.5-second intervals, clicks
  it, confirms the upstream QR selector within 10 seconds, and then delegates
  image reading to MediaCrawler. It never edits upstream source or uses a
  fuzzy text match.
- The pinned Tieba PC rewrite still prefers an `http://tieba.baidu.com/` Baidu
  navigation link before HTTPS; that route can open `百度安全验证`. The
  `tieba`-only Runner patch lets the upstream navigation complete, then
  recovers HTTP or that title through `https://tieba.baidu.com/` with the
  Baidu referrer. A persistent safety page emits the generic non-sensitive
  `captcha required` marker and fails. On the normal page, the patch keeps an
  existing QR or clicks one visible current/legacy login entry
  (`div.user-or-login, li.u_login`) before delegating the unchanged
  `tang-pass-qrcode-img` read to upstream. All scans and waits are bounded.
- Kuaishou's exact visible `//p[text()='登录']` entry can be covered by a
  transparent element that intercepts pointer-coordinate clicks. The
  `ks`-only Runner patch keeps an existing QR, otherwise scans only that exact
  entry, requires it to be visible, dispatches its DOM `click()`, and requires
  the existing `//div[@class='qrcode-img']//img` selector within a bounded
  timeout. It skips only upstream's immediately repeated coordinate click
  after the QR is open, then delegates QR reading and login polling to
  unchanged upstream.
- The pinned Kuaishou crawler still calls GraphQL `visionSearchPhoto`, which
  returned `result=50` with zero feeds after a verified login on 2026-07-28.
  The current website instead calls `POST /rest/v/search/feed`; both headless
  and headful/Xvfb website requests returned `result=2` without result data on
  the production host. The `ks`-only Runner guard therefore rejects a missing
  search object, non-success result, malformed feeds, or empty feeds with a
  non-zero failure. It never lets this known upstream-contract drift become a
  zero-result `succeeded` task.
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
  become `null`. Numeric publication times may be Unix seconds, milliseconds,
  microseconds, or nanoseconds and must be reduced to bounded Unix seconds
  before crossing into persistence; values beyond year 9999 at nanosecond
  precision become `null`. React may show raw JSON only as escaped text.
- A zero subprocess exit is only a transport signal. Before success, the
  Worker requires expected JSONL discovery, parseable objects, successful
  normalization, a valid non-empty result (or a verified empty comment set),
  atomic library ingestion, task/entity provenance, and the final
  `actual_count` update.
- Creator-mode process-local capture must inherit MediaCrawler teaching
  edition privacy rules. Persist only an anonymized creator hash, a masked
  nickname, and non-identifying aggregate counts. Never persist source user
  IDs, IP location, avatar, profile URL, biography, gender, Cookie, browser
  state, or URL tokens in creator JSONL/raw payload.

## 4. Validation & Error Matrix

| Condition | Result |
| --- | --- |
| Unknown platform | Task API returns 422 |
| Registered but disabled platform | Task API returns 409 |
| Platform enabled but selected mode deferred/disabled | Task API returns 409 before queue insertion |
| Mode fields are missing, mixed, duplicated, or over limit | Task API returns 422 before queue insertion |
| Unknown enabled-platform config | API/Worker startup fails |
| Unsafe stored result path | Results API returns 409 |
| Invalid JSONL object | Results API returns 500 |
| Subprocess exits zero without expected valid entities | Worker persists a task failure |
| Comment output is empty and content explicitly reports zero comments | Worker may persist a legal zero-result success |
| Entity normalization or library write fails | Entire entity/provenance transaction rolls back and task is failed by the Worker boundary |
| Creator client returns a full public profile | Runner allow-lists anonymized ID, masked nickname, and aggregate counts only |
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
| Any platform QR code is ready but no success/captcha/expiry signal arrives before `CRAWLER_LOGIN_TIMEOUT_SECONDS` | Terminate the process group and persist an explicit platform-login timeout; continue the research platform plan |
| Existing platform login state is valid | Emit the non-sensitive ready marker and do not wait for QR |
| XHS QR scan rotates an allow-listed auth cookie after secondary verification | Emit the generic `Login successful` marker and return the crawler task to `running` |
| XHS verification page blocks the upstream login probe | Time out the probe after two seconds, re-check the allow-listed cookie fingerprint, and continue bounded polling |
| XHS QR wait reaches its bounded deadline without a valid UI/cookie signal | Emit a login-timeout marker and persist failure; never report a successful crawl |
| Bilibili detail/comment target is a public AV ID or AV URL | Runner maps it to the upstream `aid` request and retains the source AV identity |
| Bilibili target is a BV ID or BV URL | Runner uses the upstream BV path and resolves the canonical AV identity for standalone sub-comments |
| Weibo mobile-UA login page defaults to SMS | Click the exact visible `扫码登录` entry and require the QR image within a bounded timeout |
| Weibo QR entry is absent or does not reveal a QR | Fail explicitly without changing login method or waiting indefinitely |
| Tieba upstream finishes on HTTP or `百度安全验证` | Navigate once to the HTTPS homepage with the Baidu referrer |
| Tieba safety verification remains after HTTPS recovery | Emit `captcha required` and fail without treating it as a login QR |
| Tieba normal page has the current or legacy login entry | Click one visible reviewed entry and require `tang-pass-qrcode-img` within a bounded timeout |
| Kuaishou login entry is covered by the transparent page layer | Dispatch DOM `click()` only to the exact visible entry and require the reviewed QR selector |
| Kuaishou exact login entry is absent or does not expose a QR | Fail explicitly after bounded attempts without removing page overlays |
| Kuaishou GraphQL search is missing, non-successful, malformed, or empty | Raise an explicit upstream-contract failure; never report zero-result success |
| Adapter detects captcha, expired login, or login timeout | Terminate the process group and persist a normalized failure |
| Malformed or oversized metric text | Normalized metric is `null` |
| Numeric publication time uses milliseconds, microseconds, or nanoseconds | Adapter normalizes it to bounded Unix seconds before persistence |
| Numeric publication time exceeds the supported nanosecond epoch range | Normalized publication time is `null`; the entity transaction does not crash |
| Malformed textual publication time | Normalized publication time is `null` |

## 5. Good / Base / Bad Cases

- Good: add one Adapter, register it once, test normalized sample output, then
  let the capability API drive the UI.
- Good: render `production_verified + disabled` as verified and unavailable;
  enabled state does not erase verification history.
- Good: keep content-mode differences inside Adapter/Runner and let the
  mode-level capability matrix drive both API validation and the form.
- Good: parse all discovered entity files, then commit entity upserts,
  provenance, and task completion in one transaction.
- Base: a missing optional raw field becomes `null` or an empty display value.
- Bad: hard-code a platform list in the frontend or pass Cookie/path/command
  controls through the task API.
- Bad: hard-code every platform to headless or continue a headful run after an
  Xvfb wrapper failed to establish `DISPLAY`.
- Bad: make Weibo wait on its desktop QR selector without first handling the
  mobile-UA login-mode switch, or use a fuzzy click that could select another
  login control.
- Bad: accept Tieba's HTTP safety page as a login page, treat its “扫码验证” as
  a login QR, or let the Worker's generic timeout classifier kill upstream
  before its intended login-entry fallback.
- Bad: force a Kuaishou coordinate click, delete arbitrary overlay elements,
  or replace the whole upstream login implementation.
- Bad: let Kuaishou's `result=50` or empty feeds exit zero and mark a task
  successful without stored results.
- Bad: infer detail/creator/comment verification from a platform's verified
  search cell, or mark `exit 0 + 0 rows` successful without platform evidence.
- Bad: dump a full creator API response to JSONL merely because it is public;
  this bypasses upstream's teaching-edition privacy boundary.
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
persisted-login marker disables that pre-QR deadline, a QR code with a stalled
verification flow terminates at `CRAWLER_LOGIN_TIMEOUT_SECONDS`, captcha
terminates the process group, and Bilibili/Xiaohongshu are unaffected.
Configuration tests must reject zero, negative, NaN, and infinite deadlines
for both timeout settings. Real platform
tests require explicit authorization and are not part of unit tests.
Runner tests must also assert that Weibo keeps an already-visible QR without
clicking, clicks only a visible exact-text QR entry when needed, fails clearly
when the entry is absent, and installs this patch only for `wb`.
Tieba Runner tests must assert that normal HTTPS navigation stays unchanged,
HTTP/safety navigation recovers through HTTPS, persistent safety verification
is classified as captcha, the current login entry exposes the legacy QR
selector, and the patch is installed only for `tieba`.
Kuaishou Runner tests must assert exact-entry DOM dispatch, QR confirmation,
bounded missing-entry failure, suppression of only the redundant upstream
click, acceptance of a valid non-empty search response, rejection of
missing/non-successful/empty responses, and installation only for `ks`.
They must also import the exact pinned class name (`KuaishouCrawler`) for
creator and sub-comment patches so case drift fails in tests before production.
Content-mode tests must cover the five request shapes, per-mode registry
gating, output discovery, null semantics, raw payload retention, bounded
comments, standalone sub-comments, unexplained-zero rejection, legal empty
comments, creator-profile sanitization, and transaction rollback. A real
platform result changes a mode cell to `production_verified` only after the
task result and resource recovery are recorded.
Adapter timestamp tests must cover seconds plus millisecond, microsecond, and
nanosecond payloads, including the supported upper bound. At least one
platform fixture that emits milliseconds must assert the normalized
seconds value so a unit drift cannot reach `datetime.fromtimestamp`.

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
if args.platform == "wb":
    install_weibo_qrcode_entry_patch()
if args.platform == "tieba":
    install_tieba_runtime_patch()
if args.platform == "ks":
    install_kuaishou_qrcode_entry_patch()
    install_kuaishou_search_guard()
```

Wrong:

```python
# A QR file exists, so waiting on the upstream process forever blocks the
# single-concurrency Worker when a platform shows a captcha page.
await process.wait()
```

Correct:

```python
# Start the post-QR deadline when the QR is observed. Only a classified
# success signal can release it; timeout terminates the whole process group.
if qrcode_seen and not login_ready and elapsed >= settings.crawler_login_timeout_seconds:
    await terminate_process_group(process)
    return "platform login timed out"
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
CRAWLER_LOGIN_TIMEOUT_SECONDS=180
```

Wrong:

```python
if process.returncode == 0:
    repository.complete_success(task_id, actual_count=0)
```

Correct:

```python
if process.returncode == 0:
    batch = parse_task_entities(...)
    library_repository.ingest_task(task_id=task_id, batch=batch)
```

## Scenario: Research platform scope

### 1. Scope / Trigger

Apply when the Research Center creates a task that may use more than one
platform. The UI and API must consume the same registry facts; they must not
invent a second platform allow-list.

### 2. Signatures

```text
CrawlerPlatformRegistry.enabled_platforms_for_mode(mode, enabled_platforms)
  -> list[str]
POST /api/research/tasks { platforms?: string[] }
```

### 3. Contracts

- The capabilities response lists all seven registered platforms and every
  mode's independent status.
- A research task may contain up to seven platform keys. When `platforms` is
  omitted, the API selects every configured platform whose selected mode is
  actually enabled; it does not default to a literal platform key.
- Research currently submits `search` crawls, so only `search.enabled=true`
  platforms can be selected. Deferred, disabled, and unverified platforms stay
  visible with their reason but are rejected before a crawler row is created.
- The selected platform list is persisted in the task snapshot. Multiple
  selected platforms are scheduled round-robin by bounded crawl submissions;
  the Worker remains globally single-concurrency.

### 4. Validation & Error Matrix

| Condition | Required result |
| --- | --- |
| Omitted platform list and configured search platforms exist | Use all configured enabled search platforms |
| Unknown platform key | `409` research conflict; no task/crawl row |
| Platform disabled or search mode deferred | `409` research conflict; no crawler row |
| No configured enabled search platform | `409` explicit no-search-platform error |
| Multiple selected platforms | Persist snapshot and rotate only among selected keys |

### 5. Good / Base / Bad Cases

- Good: the page shows all registry entries, selects every currently enabled
  search platform by default, and displays a deferred Kuaishou reason.
- Base: a task with one platform behaves exactly as before.
- Bad: the frontend hard-codes `bili`, enables every registered key regardless
  of mode status, or silently falls back to Bilibili after a selected platform
  fails validation.

### 6. Tests Required

- Registry tests assert enabled-platform filtering by mode.
- API tests assert omitted defaults, seven-key bounds, disabled/deferred
  rejection, and persisted multi-platform snapshots.
- Runtime tests assert the first and second bounded crawl rotate across the
  selected platform list without introducing parallel Worker execution.
- Frontend tests assert all capability entries render, disabled entries cannot
  be checked, and the request body contains the selected enabled keys.

### 7. Wrong vs Correct

Wrong:

```python
platform = str((task.get("platforms") or ["bili"])[0])
```

Correct:

```python
platform, index = self._planned_crawl_platform(task, context)
# Persist index + 1 only after the async crawler row enters WaitingCrawl.
```
