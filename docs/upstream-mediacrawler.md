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
| Browser | Google Chrome for Testing 149.0.7827.55 |

On 2026-07-28, an isolated official-repository fetch showed that the pinned
commit was exactly the official `main` head. No upstream update or production
checkout mutation was required for stage five.

The pinned history already includes the Tieba PC-page rewrite repair
`f328ee35b55e25e8aaeb9c847fe8b622e3f3447f` and the Kuaishou pagination repair
`97e4142733b1ce1744714e29c9e43e540a503021`.

## Supported integration contract

The reviewed Personal Media Ops Runner uses upstream platform codes:

```text
bili xhs dy zhihu wb tieba ks
```

Only `search` plus QR-code login is exposed. Comments, sub-comments, proxy
pool, media downloads, CDP mode, and caller-controlled concurrency remain
disabled. Each task receives an isolated output directory, log, and QR path;
upstream browser state remains platform-separated.

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
