# Platform capability matrix

This document records the stage-six production evidence as of 2026-07-28.
The live `/api/crawler/capabilities` response is authoritative after each
deployment. Every cell is independent: search verification never implies
detail, creator, or comments support.

| Platform | Search | Detail | Creator | Comments | Sub-comments |
| --- | --- | --- | --- | --- | --- |
| Bilibili | production_verified | production_verified | production_verified | production_verified | production_verified |
| Xiaohongshu | production_verified | deferred_login_required | deferred_login_required | deferred_login_required | deferred_login_required |
| Zhihu | production_verified | production_verified | production_verified | production_verified | production_verified |
| Weibo | production_verified | production_verified | production_verified | production_verified | deferred_platform_change |
| Tieba | production_verified | production_verified | production_verified | production_verified | deferred_platform_change |
| Kuaishou | deferred_upstream_breakage | production_verified | code_ready | production_verified | code_ready |
| Douyin | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained |

At runtime, a `code_ready` cell becomes `enabled` only when its platform is in
`MEDIAOPS_ENABLED_PLATFORMS`. It becomes `production_verified` only after its
own small real task succeeds and the resulting library records, process
cleanup, and resource recovery are checked.

Known constraints:

- Xiaohongshu detail/creator/comment targets require current signed URL
  context. The normalized search result intentionally does not persist or
  expose that context, so those cells fail closed as `deferred_login_required`.
- Weibo fixed upstream only exposes nested replies inside root-comment
  responses; it has no safe standalone parent-comment endpoint.
- Tieba fixed upstream recursively navigates reply pages, so standalone bounded
  sub-comment collection stays deferred.
- Kuaishou search uses a stale GraphQL contract. Detail, creator, and comments
  are audited separately and do not inherit the search deferral.
- Douyin remains the independent `douyin-runtime-capacity` task; stage six does
  not spend production browser capacity retrying it.
