# Upstream MediaCrawler Audit

## Audit Date

2026-07-28

## Development and Production Checkouts

The development host has no `/opt/mediacrawler` checkout. Development source
inspection therefore used an isolated, temporary clone of the official
repository. No production path or browser state was mounted or copied.

The production checkout is:

| Item | Value |
| --- | --- |
| Path | `/opt/mediacrawler` |
| Commit | `17f66121e0fcc40fc23958b995bec873d422667d` |
| Branch | `main` |
| Worktree | clean |
| Python | 3.11.15 |
| Playwright | 1.61.0 |
| Chromium path | `/home/mediaops/.cache/ms-playwright/chromium-1228/chrome-linux64/chrome` |
| Browser version | Google Chrome for Testing 149.0.7827.55 |

The checkout contains platform packages and stores for Bilibili, Xiaohongshu,
Douyin, Zhihu, Weibo, Tieba, and Kuaishou.

## Official Upstream Comparison

`git ls-remote` against the official `NanmiCoder/MediaCrawler` main branch
returned the exact production commit:

```text
17f66121e0fcc40fc23958b995bec873d422667d
```

An isolated partial clone and detached checkout confirmed there are zero
commits between the production revision and official main. Production is
already pinned to the current official main, so stage five does not require an
upstream update or a switch of `/opt/mediacrawler`.

Relevant included fixes and platform history:

- Tieba PC-page rewrite repair:
  `f328ee35b55e25e8aaeb9c847fe8b622e3f3447f`.
- Kuaishou pagination repair:
  `97e4142733b1ce1744714e29c9e43e540a503021`.
- The current Xiaohongshu dependency update is the pinned head commit.
- Recent Zhihu, Weibo, Bilibili, and privacy-oriented teaching-version changes
  are already ancestors of the pinned head.

## Runner CLI Contract

Official `cmd_arg/arg.py` accepts:

```text
--platform xhs|dy|ks|bili|wb|tieba|zhihu
--lt qrcode|phone|cookie
--type search|detail|creator
--keywords <text>
--get_comment yes|no
--get_sub_comment yes|no
--headless yes|no
--save_data_option json|csv|db|jsonl
--crawler_max_notes_count <positive integer>
--max_concurrency_num <positive integer>
--save_data_path <path>
--enable_ip_proxy yes|no
```

The repository Runner translates the Personal Media Ops fixed task contract to
these arguments. It must continue overriding comments, sub-comments, proxy,
media download, and CDP mode to safe production defaults.

## Storage and Login Isolation

JSONL content paths follow:

```text
<SAVE_DATA_PATH>/<platform-store>/jsonl/<crawler_type>_contents_<date>.jsonl
```

The storage directory names for the new platforms are `zhihu`, `weibo`,
`tieba`, and `kuaishou`. Upstream login-state directories include the platform
name, so the fixed checkout already supports platform-separated browser state.

Upstream login implementations have bounded internal waits, but the Worker
still needs an Adapter-owned pre-QR startup deadline because Chromium,
navigation, or platform JavaScript can stall before upstream reaches its login
wait. A QR file must not be assumed for every login path.

## Teaching-Version Result Fields

The pinned upstream writes privacy-normalized JSONL records:

- Zhihu: content/question identifiers and type, title, description/text, URL,
  timestamps, vote/comment counts, source keyword, and masked creator fields.
- Weibo: note ID, HTML-stripped text, timestamps, like/comment/share counts,
  URL, source keyword, and masked creator fields.
- Tieba: note ID, title, description, URL, publish time, forum name/link,
  reply/page counts, source keyword, and masked creator fields.
- Kuaishou: video ID/type, title, description, timestamp, like/view counts,
  video/cover/play URLs, source keyword, and masked creator fields.

Personal Media Ops will preserve each stored record as `raw_payload`, normalize
safe common fields, and never execute text as HTML.

## Decision

Keep production pinned at
`17f66121e0fcc40fc23958b995bec873d422667d`. Do not fetch, pull, or alter the
production checkout during the Personal Media Ops application deployment.
Document this revision in the public upstream note and server inventory.
