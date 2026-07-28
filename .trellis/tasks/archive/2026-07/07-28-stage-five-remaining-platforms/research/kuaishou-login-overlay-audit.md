# Kuaishou Login Overlay Audit

Date: 2026-07-28

## Scope

Production task `75315ab6-2412-4345-8f4b-f47d7fe2455d` tested the pinned
MediaCrawler commit `17f66121e0fcc40fc23958b995bec873d422667d` with keyword
`AI` and requested count 3. The task used the reviewed Personal Media Ops
Runner and did not modify upstream source or browser login state.

## Evidence

- Kuaishou's API probe returned `UNAUTHENTICATED`, so upstream correctly
  entered its QR-code login path.
- The exact upstream locator `//p[text()='登录']` resolved to one visible
  `p.user-default` node inside the toolbar login item.
- A transparent, classless `div` intercepted pointer events at the target
  coordinates. Playwright retried its normal click for 30 seconds and then
  raised `Locator.click: Timeout 30000ms exceeded`.
- An isolated temporary browser reproduced the interception without reading
  or changing the production browser-state directory.
- `force=True` still sent a coordinate click to the interceptor and did not
  expose a QR code.
- Dispatching `element.click()` directly to the exact visible login node
  exposed the existing upstream QR selector
  `//div[@class='qrcode-img']//img`. The temporary browser then closed with
  zero residual browser processes.

## Decision

Patch only the reviewed `ks` Runner process:

1. Keep an already visible QR code unchanged.
2. Scan only the exact upstream login selector with finite attempts.
3. Require a visible entry, dispatch its DOM `click()`, and require the
   reviewed QR selector within a bounded timeout.
4. Skip only upstream's immediately repeated coordinate click after the QR is
   already visible, then delegate QR reading, display, login-state polling,
   and collection to unchanged MediaCrawler.

Do not use a fuzzy selector, remove arbitrary overlays, copy the upstream
login implementation, or edit `/opt/mediacrawler`.

## Production Search Validation

- Task `a090a2a4-8e68-4408-87ff-9270032e62f0` generated a QR code after the
  login-overlay fix but timed out after its QR expired.
- Refreshed task `5002a187-cfd6-4622-9ee4-c054223dd205` completed QR login,
  reached Kuaishou search, and exited with zero stored results.
- The pinned GraphQL `visionSearchPhoto` response had `result=50` and zero
  feeds for cursors `1`, empty, and `0`.
- The current logged-in website opens `/search/AI` and calls
  `POST /rest/v/search/feed`, not GraphQL. Its safe response shape was
  `result`, `error_msg`, and `request_id`; both headless and headful/Xvfb
  probes returned `result=2` without result data.
- Every diagnostic closed its browser, active tasks returned to zero, memory
  returned above 960 MiB available, and swap use remained zero.

## Final Capability Decision

Keep Kuaishou `code_ready`, disable task submission, and report
`deferred_upstream_breakage`. Install a `ks`-only Runner guard that turns the
known missing/non-successful/empty GraphQL response into an explicit non-zero
failure so it cannot be recorded as a zero-result success. Do not claim
`production_verified` until a reviewed REST/upstream compatibility change and
a real non-empty task both pass.
