# Platform capability matrix

This document records the code baseline before stage-six production tasks.
The live `/api/crawler/capabilities` response is authoritative after each
deployment. Every cell is independent: search verification never implies
detail, creator, or comments support.

| Platform | Search | Detail | Creator | Comments | Sub-comments |
| --- | --- | --- | --- | --- | --- |
| Bilibili | production_verified | code_ready | code_ready | code_ready | code_ready |
| Xiaohongshu | production_verified | code_ready | code_ready | code_ready | code_ready |
| Zhihu | production_verified | code_ready | code_ready | code_ready | code_ready |
| Weibo | production_verified | code_ready | code_ready | code_ready | deferred_platform_change |
| Tieba | production_verified | code_ready | code_ready | code_ready | deferred_platform_change |
| Kuaishou | deferred_upstream_breakage | code_ready | code_ready | code_ready | code_ready |
| Douyin | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained | deferred_resource_constrained |

At runtime, a `code_ready` cell becomes `enabled` only when its platform is in
`MEDIAOPS_ENABLED_PLATFORMS`. It becomes `production_verified` only after its
own small real task succeeds and the resulting library records, process
cleanup, and resource recovery are checked.

Known constraints:

- Xiaohongshu detail/creator/comment targets may require current `xsec` context
  in a valid URL.
- Weibo fixed upstream only exposes nested replies inside root-comment
  responses; it has no safe standalone parent-comment endpoint.
- Tieba fixed upstream recursively navigates reply pages, so standalone bounded
  sub-comment collection stays deferred.
- Kuaishou search uses a stale GraphQL contract. Detail, creator, and comments
  are audited separately and do not inherit the search deferral.
- Douyin remains the independent `douyin-runtime-capacity` task; stage six does
  not spend production browser capacity retrying it.
