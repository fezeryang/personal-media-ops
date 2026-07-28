# Tieba PC Login Audit

Date: 2026-07-28

## Scope

Production task `cffa6e3b-6ae5-42ab-b9eb-6297d345219c` tested the pinned
MediaCrawler commit `17f66121e0fcc40fc23958b995bec873d422667d` with keyword
`人工智能` and requested count 5. No upstream source or browser state was
modified during diagnosis.

## Evidence

- The pinned history includes the upstream PC rewrite repair
  `f328ee35b55e25e8aaeb9c847fe8b622e3f3447f`.
- `_navigate_to_tieba_via_baidu` still checks the HTTP Tieba link before the
  HTTPS link. The HTTP route repeatedly produced `百度安全验证`.
- In the same browser context, a bounded navigation to
  `https://tieba.baidu.com/` with a Baidu referrer restored the normal PC page.
- The normal 2026 PC page exposes `div.user-or-login`; the upstream fallback
  still searches only for removed `li.u_login`.
- Clicking the current entry renders the existing upstream QR selector
  `img.tang-pass-qrcode-img`.
- The task log line `login failed, have not found qrcode` is intermediate in
  upstream Tieba: upstream intends to click its fallback entry after that
  line. The generic Worker classifier correctly treats this wording as a
  terminal timeout for other platforms, so merely ignoring it for Tieba could
  allow upstream's final `sys.exit(0)` to become a false zero-result success.

## Decision

Keep the generic terminal classifier unchanged. Patch only the reviewed
`tieba` Runner process:

1. Let the upstream Baidu navigation finish.
2. Recover HTTP or `百度安全验证` through the HTTPS homepage once.
3. If safety verification persists, emit `captcha required` and fail.
4. Before upstream QR discovery, keep an existing QR or click one visible
   current/legacy login entry.
5. Delegate the QR bytes and login-state polling to unchanged MediaCrawler.

All waits are bounded. The patch neither treats `扫码验证` as a login QR nor
edits `/opt/mediacrawler`.
