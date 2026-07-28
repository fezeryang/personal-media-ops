# MediaCrawler upstream pin

Personal Media Ops integrates MediaCrawler as an external runtime. It does not
vendor, copy, or modify upstream core source, and a production deployment must
never follow `latest` automatically.

## Current verified revision

| Item | Value |
| --- | --- |
| Official repository | `NanmiCoder/MediaCrawler` |
| Pinned commit | `17f66121e0fcc40fc23958b995bec873d422667d` |
| Production path | `/opt/mediacrawler` |
| Production branch | `main` |
| Production worktree | clean at the 2026-07-28 audit |
| Python | 3.11.15 |
| Playwright | 1.61.0 |
| Browser | Google Chrome for Testing 150.0.7871.186 |

On 2026-07-28, an isolated official-repository fetch showed that the pinned
commit was exactly the official `main` head. No upstream update or production
checkout mutation was required for stage five.

The pinned history already includes the Tieba PC-page rewrite repair
`f328ee35b55e25e8aaeb9c847fe8b622e3f3447f` and the Kuaishou pagination repair
`97e4142733b1ce1744714e29c9e43e540a503021`.

The Kuaishou pagination repair only stops retrying after an empty response; it
does not update the search transport. Production verification on 2026-07-28
showed that the pinned GraphQL `visionSearchPhoto` call returns `result=50`
with no feeds, while the website now sends `POST /rest/v/search/feed`.
Headless and headful/Xvfb website requests both returned `result=2` without
result data on the production host. Kuaishou therefore remains
`deferred_upstream_breakage`; Personal Media Ops fails this response closed
instead of recording a zero-result success. Independent stage-six tasks proved
that one current public detail target and its bounded first-level comments are
usable. The creator-profile call returned no profile for multiple public
targets, so creator remains independently `deferred_upstream_breakage`.

Production inspection on 2026-07-28 found two remaining Tieba integration
gaps at this pinned head: Baidu navigation prefers its HTTP Tieba link before
HTTPS and can land on `百度安全验证`, while QR login still falls back only to
the removed `li.u_login` entry. The reviewed Personal Media Ops Runner handles
these through a `tieba`-only HTTPS recovery and current/legacy login-entry
adapter seam. `/opt/mediacrawler` remains unchanged.

## Stage-six content-mode audit

The pinned CLI natively exposes only `search`, `detail`, and `creator`.
Comments are flags on those native modes, and several platforms recursively
page sub-comments without a common bound. Personal Media Ops therefore maps
its five task modes through Adapter-owned request contracts:

- `search`, `detail`, and `creator` use the pinned native entry points;
- standalone `comments` runs one-target detail with first-level comments on,
  sub-comments off, and a maximum of 10;
- standalone `sub_comments` is enabled only where a bounded direct client API
  exists (Bilibili, Xiaohongshu, Zhihu, and Kuaishou);
- Weibo and Tieba standalone sub-comments are
  `deferred_platform_change`, because their pinned flows cannot safely bound a
  single parent reply traversal;
- creator profile persistence is captured through narrow process-local Runner
  seams because the teaching build intentionally leaves several creator
  stores as no-ops. The seam preserves that build's privacy contract by
  allow-listing only an anonymized creator hash, masked nickname, and aggregate
  counts; it never writes raw user IDs, avatar/profile URLs, biographies, IP
  location, gender, URL tokens, Cookie data, or browser state.
- the pinned Bilibili detail parser accepts BV only while search stores AV
  identities. The reviewed Runner maps public AV IDs/URLs to the client's
  `aid` path and resolves BV to AV for standalone reply provenance.

No upstream source is patched. The Runner seam is version-specific and covered
by argument, safety, output-discovery, normalization, timeout, cancellation,
and process-group tests.

## Supported integration contract

The reviewed Personal Media Ops Runner uses upstream platform codes:

```text
bili xhs dy zhihu wb tieba ks
```

The application exposes independent `search`, `detail`, `creator`, `comments`,
and `sub_comments` modes only where the mode-level registry permits them.
Proxy pool, media downloads, CDP mode, implicit recursive replies, and
caller-controlled concurrency remain disabled. Each task receives an isolated
output directory, log, and QR path; upstream browser state remains
platform-separated.

The pinned teaching version writes privacy-normalized JSONL. Personal Media Ops
retains each record in `raw_payload` and derives a safe common result without
rendering raw HTML.

## Upgrade procedure

1. Record production commit, branch, worktree, Python, Playwright, and browser.
2. Fetch official main into an isolated clone, worktree, or versioned release
   directory; never `git pull` the verified production checkout.
3. Review commits affecting the target platform plus Bilibili and Xiaohongshu.
4. Verify dependencies, browser launch, state/output isolation, process cleanup,
   memory recovery, and small real tasks for the target, Bilibili, and
   Xiaohongshu.
5. Pin the accepted commit here and in the production inventory before
   switching the Runner runtime.

An upstream license or product-capability change requires separate review.
Search success does not imply support for detail, creator, comments, or
sub-comments.
