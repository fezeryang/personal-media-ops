# Crawler Platform Contract

## 1. Scope / Trigger

Apply this contract when adding a crawler platform, changing Runner arguments,
normalizing MediaCrawler JSONL, or exposing platform choices to the frontend.

## 2. Signatures

```text
GET  /api/crawler/capabilities
POST /api/crawler/tasks
GET  /api/crawler/tasks/{task_id}/results?offset=N&limit=N
MEDIAOPS_ENABLED_PLATFORMS=bili[,xhs,dy]
```

Adapters implement capability metadata, fixed Runner arguments,
`is_login_success(line)`, content-file discovery, and `normalize_result(raw)`.

## 3. Contracts

- Registry keys are `bili`, `xhs`, and `dy`; it is the backend source of truth.
- `bili` and `xhs` are `verified`; `dy` is `code_ready`.
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
- Numeric result fields accept non-negative integers plus platform display
  forms such as `1,544`, `1000+`, `5.7万`, `1.2w`, and `3亿`. Abbreviated
  values use a bounded decimal format; malformed, negative, non-finite, or
  oversized strings normalize to `null` instead of failing result reads.
- Result items use the unified Pydantic schema and are read incrementally,
  path-checked, paginated, and capped at `requested_count`.

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
| Malformed or oversized metric text | Normalized metric is `null` |

## 5. Good / Base / Bad Cases

- Good: add one Adapter, register it once, test normalized sample output, then
  let the capability API drive the UI.
- Good: render a disabled-but-verified platform as verified and unavailable;
  enabled state does not erase verification history.
- Base: a missing optional raw field becomes `null` or an empty display value.
- Bad: hard-code a platform list in the frontend or pass Cookie/path/command
  controls through the task API.
- Bad: hard-code every platform to headless or continue a headful run after an
  Xvfb wrapper failed to establish `DISPLAY`.
- Bad: modify `/opt/mediacrawler` to add sleeps, retry every Playwright error,
  or loop indefinitely around browser startup.

## 6. Tests Required

Test registry truthfulness, disabled/unknown platforms, fixed commands,
platform JSONL samples, unsafe URLs/paths, QR progression, result caps, and
cross-platform competing claims. Assert per-platform `--headless` arguments,
legacy missing-argument compatibility, Xvfb re-exec/failure paths, abbreviated
metric parsing, malformed/oversized metric rejection, Douyin navigation-race
recovery, unrelated-error propagation, and bounded retry exhaustion. Real
platform tests require explicit authorization and are not part of unit tests.

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
