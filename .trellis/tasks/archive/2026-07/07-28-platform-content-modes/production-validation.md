# Stage-six production validation

Captured on 2026-07-28 Asia/Shanghai. This record distinguishes successful
real tasks, deferred cells, and failed diagnostic tasks.

## Baseline and release

- Initial production application:
  `4df42050ff35d1a61e3e55bcf983419a9cbd13b5`.
- Initial GitHub main:
  `9d66834dafdb90db02224a74ebfcea538359acc5`.
- Stage-six implementation:
  `45d57d74476f854cd67df49ae0b636843be739fb`.
- Timestamp repair:
  `05825e39ec3d7541ee6914d65968abc23f7a3480`.
- Runner/mode repair:
  `792e7f78596bfc6e1b73de815da19af9883b1767`.
- MediaCrawler stayed pinned and clean at
  `17f66121e0fcc40fc23958b995bec873d422667d`.
- Alembic advanced from `0003_remaining_platforms` through
  `0004_content_modes` to `0005_library_entities`.
- Migration backup:
  `/var/backups/mediaops/20260728T065514Z`, database SHA-256
  `f13244cdef22993a25f3560a605819bfc1ffc4fa81c8bd1d179d9dbbf639db05`.
- Latest retained deployment backup:
  `/var/backups/mediaops/20260728T075214Z`, database SHA-256
  `b203405b6510f432a1207c9a0084b913b9325eb723e1f4a1fdd7a9bf77519ca6`.

The only production configuration key changed was
`MEDIAOPS_ENABLED_PLATFORMS`, from the five verified-search platforms to
`bili,xhs,zhihu,wb,tieba,ks`. Its permission-safe backup is
`/var/lib/mediaops/config-backups/mediaops.env.20260728T074107Z.bak`.
Douyin was not enabled.

## Successful real tasks

| Platform | Mode | Task | Actual |
| --- | --- | --- | ---: |
| Bilibili | search | `9b26c3e9-3a6d-47a4-aa88-a8a2fdc1d238` | 2 |
| Bilibili | detail (post-fix numeric ID) | `ca0f3eb5-40a3-4dfa-921d-81cb9f845cfe` | 1 |
| Bilibili | creator | `25a6f29f-28d1-45ac-bf2b-8b3482055d92` | 1 |
| Bilibili | comments | `535e4506-7aeb-414d-b2ef-022f0e26305f` | 10 |
| Bilibili | sub_comments | `eaccefb3-58fe-4ab9-8447-4507898468ad` | 5 |
| Xiaohongshu | search (post-fix) | `0c62d3e0-adce-4c67-80c5-aab8a99d7d3a` | 2 |
| Zhihu | detail | `b5d947ff-4356-49a2-b986-e81df6f37653` | 1 |
| Zhihu | creator | `6056342c-43ca-4807-bedf-dd7c321e5218` | 1 |
| Zhihu | comments | `7d0aa675-4807-4439-92a7-8cda71819de4` | 10 |
| Zhihu | sub_comments | `21af707a-66b7-49fe-b26d-fa9babb22dc0` | 5 |
| Weibo | detail | `82e6e4a1-821f-4588-b2a2-fb97b49e4908` | 1 |
| Weibo | creator | `6b57cd58-39c3-43db-87c3-0986ad34f929` | 1 |
| Weibo | comments | `e987bfcd-c94d-4061-b91b-27087a02f53a` | 10 |
| Tieba | detail | `e460d0e4-57fb-46ff-9b56-34c4c3a74b35` | 1 |
| Tieba | creator | `d53d5d1c-5931-45f3-8f47-52067dd4d0ba` | 1 |
| Tieba | comments | `98a656f9-28ac-44cd-8023-17deedb69f86` | 10 |
| Kuaishou | detail | `ebc1a0b2-1ef7-4dcc-85eb-281bd24e16b7` | 1 |
| Kuaishou | comments | `00b4a974-9000-49da-a3bb-797075648a75` | 10 |

Existing browser state was valid for every successful task. Stage six required
no new QR scan or captcha.

## Deferred and diagnostic evidence

- Xiaohongshu detail task
  `7de6a658-fee8-4c2b-bfd7-f41e62146544` proved that a normalized safe URL
  without signed URL context cannot fetch detail. Detail, creator, comments,
  and sub-comments are `deferred_login_required`; the application does not
  persist or expose the signed value.
- Weibo and Tieba standalone sub-comments remain
  `deferred_platform_change` because the pinned flows cannot safely bound one
  parent reply traversal.
- Kuaishou search remains `deferred_upstream_breakage`. Detail and comments
  succeeded independently. Creator tasks
  `e5374933-d92c-4784-81bb-dec5d2dbed2a` and
  `f043fbd4-858e-4fba-8c2c-3a1b8a30e9cb` reached the fixed upstream call but
  returned no profile for distinct public targets, so creator is
  `deferred_upstream_breakage`. Sub-comments is `code_ready`; the bounded
  comment sample had no reply-bearing parent and was not marked verified.
- Douyin stays `deferred_resource_constrained` under the separate
  `douyin-runtime-capacity` task. No Douyin browser was started.

Failed diagnostics remain in the database. They were not relabeled as
successful.

## Library and compatibility evidence

- SQLite integrity: `ok`.
- Tasks: 55 total, including all 28 pre-stage-six tasks; active tasks: 0.
- Library totals: 8 contents, 10 privacy-safe creators, 60 comments.
- Per platform `(contents, creators, comments)`:
  Bilibili `(2,2,15)`, Xiaohongshu `(2,2,0)`, Zhihu `(1,1,15)`,
  Weibo `(1,1,10)`, Tieba `(1,3,10)`, Kuaishou `(1,1,10)`, Douyin `(0,0,0)`.
- Duplicate groups under the three platform/source unique keys: 0.
- Task/entity provenance rows: 94.
- Re-collecting the same Bilibili content retained one library row, advanced
  `last_collected_at`, preserved `first_collected_at`, and linked four task
  provenance records.
- Raw JSONL remained in the isolated task outputs and was not rewritten.

## Quality and runtime

- Backend full suite after Runner fixes: 286 passed; total coverage 90.50%.
- Frontend: lint passed, 33 tests passed, production build passed; coverage
  96.06% statements, 91.60% branches, 100% functions, and 96.38% lines.
- Server release script tests and shell syntax: passed. ShellCheck was not
  installed and was not added.
- API and Worker: active. Local API and library stats: HTTP 200.
- Repository, build marker, and published marker matched the deployed commit;
  server worktree was clean.
- Browser processes: 0. D-state processes: 0.
- Memory: 1,608 MiB total, 941 MiB available. Swap: 1,024 MiB total, 0 used.
- Restricted helper, Nginx, localhost health, and production SNI loopback
  passed. The external Codex observer still received its known
  `SSL_ERROR_SYSCALL`; this stayed non-blocking only after all origin-side
  checks passed.

## Next task

`intelligence-library-and-subscriptions` remains planning-only. Its scope is
keyword subscriptions, schedules, deduplication, tags, favorites, metric
snapshots, creator monitoring, daily briefs, and trend analysis. None of that
scope was implemented in stage six.
