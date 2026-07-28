# Pinned MediaCrawler content-mode audit

Audited read-only at pinned commit
`17f66121e0fcc40fc23958b995bec873d422667d`.

## CLI and output contract

- Upstream CLI supports only `search`, `detail`, and `creator`.
- `--specified_id` routes per-platform content IDs/URLs; `--creator_id`
  routes creator IDs/URLs, except Zhihu creator input is not wired by the
  upstream CLI even though its core uses `ZHIHU_CREATOR_URL_LIST`.
- First-level and second-level comments are flags on search/detail/creator,
  not standalone modes.
- First-level comments accept a per-content maximum. Upstream has no common
  maximum for second-level comments and several clients recursively page all
  replies.
- JSONL names follow
  `<crawler_type>_<contents|comments|creators>_<date>.jsonl` under each
  platform storage directory.

## Platform observations

### Bilibili

- Detail and creator core paths exist.
- Comments have a bounded `max_count`.
- The client exposes a direct level-two comment API using content ID and root
  comment ID, making bounded standalone sub-comment collection feasible
  through a reviewed process-local Runner seam.
- The teaching creator path retains minimal public profile fields in memory
  but does not persist a creator profile by default.

### Xiaohongshu

- Detail and creator paths exist, but valid content/creator URLs may require
  `xsec_token`/`xsec_source`.
- Comments are bounded.
- A direct sub-comment API exists and accepts note ID, root comment ID and
  xsec token; bounded standalone use is technically possible when the target
  URL carries valid token context.
- Creator JSONL persistence is intentionally a no-op in the teaching build.

### Zhihu

- Detail supports answers, articles and videos and preserves their distinct
  content types.
- Creator core exists, but upstream CLI does not route its creator argument.
- Root and child comment APIs exist. The all-comments helper ignores the
  common first-level maximum and recursively pages; Personal Media Ops must
  wrap it or use bounded direct calls.
- Creator JSONL persistence is intentionally a no-op.

### Weibo

- Detail and creator core paths exist.
- First-level comments are bounded. Sub-comments are only the nested replies
  already embedded in fetched root-comment responses; there is no independent
  target-parent endpoint in this pinned implementation.
- Content/comment HTML is stripped by the teaching store. Personal Media Ops
  must still treat every string as text.
- Creator JSONL persistence is intentionally a no-op.

### Tieba

- Detail, creator and root-comment paths exist. Creator input may be a profile
  URL or portrait ID.
- Sub-comments are fetched by navigating reply pages and are unbounded across
  a root’s pages in the common helper.
- Creator JSONL persistence exists in the store class, but the teaching
  `save_creator` entry is currently a no-op.

### Kuaishou

- Detail and creator core paths exist independently from the broken search
  call.
- Comment and sub-comment clients already use REST V2 endpoints and expose
  direct content/root-comment parameters.
- Detail and creator still depend on GraphQL endpoints and need real
  validation. Creator JSONL persistence is a no-op.

### Douyin

- Detail/creator/comment code exists upstream, but the application must not
  run production browser validation on the current resource-constrained host.

## Integration decision

- Keep the pinned upstream unchanged.
- Use Adapter-owned request/normalization contracts and narrow
  platform-scoped process-local Runner seams.
- Map standalone comments to one-target detail collection with comments on and
  sub-comments off.
- Only implement standalone sub-comments when the fixed client exposes a
  bounded direct target API. Mark other combinations precisely deferred
  instead of enabling recursive all-reply behavior.
- Capture only the public, privacy-safe creator fields authorized by the
  application contract. Preserve the teaching build’s anonymized source IDs
  and masked names where that is the available output.
