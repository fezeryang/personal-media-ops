# Phase 8C Production Validation

Date: 2026-08-02 (Asia/Shanghai)

## Release and database

- Initial local/origin implementation baseline: `07dbf85`.
- Initial production baseline: `f156017573af3f9ba5d72fcd6ba875c2ed11746b`.
- Implementation commits: `cf6b26c`, `ffb57a5`, `b324216`, and
  `d7a530aa673c90cb826f631e88217e46e681035f`.
- Final local/origin code commit: `d7a530aa673c90cb826f631e88217e46e681035f`.
- Final production commit: `d7a530aa673c90cb826f631e88217e46e681035f`.
- Forward migration: `0013_cross_platform_research_completion`, from
  `0012_research_quality_foundation`; the final metric durability fix did not
  change the schema.
- Final production database revision: `0013_cross_platform_research_completion`.
- Final SQLite `integrity_check`: `ok`.

Backups were created before database-affecting deployment and before each
subsequent release. The migration backup was
`/var/backups/mediaops/20260802T043250Z`:

```text
5d541a4a2cede2a86545104a080b1883296dae23debf96835aaeb99eafd6025b  mediaops.db
1b0b9ca53618419956e1b9c68ff38af313076a7da4eb5c3445e330d62af1c8f5  metadata.txt
```

The final release backup was `/var/backups/mediaops/20260802T063101Z`:

```text
aca4878e0509005cadde83ebcd38da20101ae3d528d8f38e38b783a590a7c9a4  mediaops.db
ad42caf62059f0c1d5f1d2048c05bc459d9946d6dfe68af84fa650b1d9888b0b  metadata.txt
```

The downgrade guard remains fail-closed when Phase 8C data exists. Rollback
is a forward code fix; database restoration is an irreversible administrative
operation and was not performed.

## Why old research was Bilibili-only

The production environment was not narrowed: `MEDIAOPS_ENABLED_PLATFORMS`
contained `bili,xhs,zhihu,wb,tieba,ks`, and the effective search registry had
five verified search cells. Thirteen of the sixteen old tasks had explicitly
persisted `['bili']`. The remaining multi-platform snapshots were stopped by
the old Runtime's bounded crawl-round/branch budget after the first platform,
not by the allow-list, adapter registry, login state, or a failed deployment.
The new Coverage Plan and one-crawl-at-a-time rotation remove that accidental
fallback while preserving the real platform capability facts.

## Platform verification

| Platform | Status | Evidence |
| --- | --- | --- |
| Bilibili | `production_verified` | Baseline and both bounded acceptance tasks |
| Zhihu | `production_verified` | Acceptance task `0fe13920-34b8-48ee-971b-36bf42ba0462` |
| Weibo | `production_verified` | Acceptance task `fdf25155-4e10-493e-884b-a40e071b0c68` |
| Tieba | `production_verified` | Real task `52d19084-7f17-4ede-8293-36f716919272`, 5/5 results |
| Xiaohongshu | `production_verified` while login context is usable | Acceptance task `0fe13920-34b8-48ee-971b-36bf42ba0462` |
| Douyin | `deferred_resource_constrained` | Explicitly out of scope |
| Kuaishou search | `deferred_upstream_breakage` | Explicitly out of scope |

The pinned MediaCrawler commit remained
`17f66121e0fcc40fc23958b995bec873d422667d`. The Runner repository and
installed copy remained SHA-256
`b9e0e9a264c18f4186cda4934ea05f3b90f6e87127074aba015bbd9d85d7429d`.
No QR or captcha pause was needed in the acceptance tasks. Requested counts
were 12 for the real Research runs, within the verified small bounded range.

## Real Research acceptance

Task `0fe13920-34b8-48ee-971b-36bf42ba0462` used the objective
“vibecoding的最佳教学” and planned `bili`, `xhs`, and `zhihu`. It produced:

- 3 actual platforms;
- 17 entities;
- 9 independent evidence items;
- 28 new library contents;
- 0 qualifying negative/contradictory items;
- 86 distinct collected contents across 99 occurrence rows and 111 total
  occurrences, with 10 repeated contents;
- 9 adopted contents and 77 explicit non-adoptions;
- no unexplained `approved_pending` query.

The three successful crawler tasks were:

| Platform | Crawler task | Result |
| --- | --- | --- |
| Bilibili | `d406d3d7-3186-4454-aa15-32fe5f0cff27` | 12/12 |
| Xiaohongshu | `e2d7a554-eddb-41c1-892d-02d79bf03c69` | 12/12 |
| Zhihu | `e03ea9e6-9296-4c3a-a04f-4dd64fc84152` | 12/12 |

The source-linked query chain included:

1. Bilibili: `vibecoding workshop learning outcomes` from `user_goal`;
2. Xiaohongshu: `coding 使用体验 缺点`, linked to parent query
   `cd0f9be5-5177-42d2-b622-0f5bbca3dbba` and source content
   `e6518108-bc9d-4eb3-ab09-0eaf59f96ab3`;
3. Zhihu: `话题 使用体验 不好用`, linked to parent query
   `7ec6f937-72c8-419f-a357-b260733c00ea` and source content
   `e2ded3ca-6306-4335-9e41-5c58da21c217`;
4. Bilibili expansion: `codex 使用体验 失败`, linked to parent query
   `0fc7c905-9639-4c7e-838b-567414201ad6` and source content
   `fdbdc484-e6b6-4f1a-99be-67c3d9c3f342`.

Query lifecycle totals were `completed=4`,
`rejected_duplicate=13`, `rejected_generic=6`, `rejected_low_relevance=7`,
and `skipped_low_marginal_value=7`. The low-yield branch had a persisted
marginal score of `0.35`; no query remained approved without a terminal reason.
The supplied objective did not yield a qualifying negative item. The report
therefore records `counterevidence_status=not_found` for the five generated
facts and does not claim that the products had no weaknesses.

The earlier task `fdf25155-4e10-493e-884b-a40e071b0c68` used `bili` and `wb`.
It produced 5 new contents, 4 independent evidence items and 1 negative item;
the Bilibili crawler returned 12/12 and the Weibo crawler returned 1 relevant
item. Its historical Bilibili platform row remains `executing` because the
old task completed before the post-production finalization repair; there are
no active tasks or crawlers, so this is a legacy display row rather than a
running job.

## Evidence and coverage

Facts are direct-evidence constrained. Findings are split into Facts,
Inferences and Contradictions, with source roles, quality, completeness,
independence, content IDs, URLs, platform, and publication time retained.
The acceptance task's 13 Finding-content links resolve to 9 distinct
independent content IDs; repeated hits only increment occurrences. Repost
signals use normalized title, body hash, URL, author, publication time and
bounded text similarity and do not increase the independent count.

Entity coverage reached 17 entities. The concentrated `code` and `codex`
branches were marked saturated and reduced in priority; their evidence ratio
was visible as 1.0 for that entity, while the final concentration gate used
unique adopted non-repost content IDs and correctly reported the task's
single-entity target as not reached. The final evidence was still primarily
Bilibili, so it is not a market-wide claim.

Non-adopted content was explainable: the acceptance task recorded 77
`无事实增量` decisions. The earlier task also recorded `内容过短` and
`无事实增量`; no result was silently discarded. The runtime distinguishes
collected, new, candidate, adopted, and non-adopted content.

## Usage, compaction, billing and budgets

The acceptance task recorded 18 MiniMax `subscription_fixed` invocations:
158,229 total tokens (37,242 input, 7,963 output, 113,024 cached), with 18
null marginal-cost calls and no false `0`-cost display. Step usage covered
planning, query generation/review, research actions/artifacts, finding
generation, and final report; each row carries provider instance, vendor,
model, billing mode, token fields, latency and fallback metadata where
available. The acceptance task used no DeepSeek charge, relay provider, or
pay-as-you-go invocation.

The gateway data model distinguishes vendor, provider instance, billing
profile and model. MiniMax and GLM use subscription semantics; DeepSeek
official has an isolated pay-as-you-go price-version path; relay and unknown
price paths never inherit official prices and report null cost when unavailable.
Resource budgets cover input/output/total tokens, calls, crawler tasks,
runtime, new contents and pay-as-you-go amount. Route policy is deterministic
and capability-aware: MiniMax for tools, GLM for ordinary analysis when tool
turns are unnecessary, and DeepSeek only for configured quality/summary or a
tested equivalent fallback.

The historical acceptance task's compaction snapshot was taken before the
final evidence-provenance fix and therefore reported
`candidate_query_count=37`, `candidate_content_count=20`,
`loaded_full_content_count=12`, `final_evidence_count=0`, and
`compressed_branch_count=13`. The runtime now compacts after evidence
selection, preserves content IDs/URLs/platforms/timestamps/roles, and has a
regression test requiring final evidence provenance to survive compaction.
The latest crawler-metric fix also persists metrics on asynchronous crawler
completion rather than only updating pre-existing rows.

## Reliability and controls

The implemented checkpoint/budget model was tested for API/Worker/Runtime
restart, model timeout/rate-limit/auth/tool-format failures, crawler failure,
login timeout/cancel, SQLite lock retry, fallback success/failure, token and
amount budget exhaustion, and structured-output degradation. The bounded
structured chain is native output → tool schema → strict JSON → one repair →
explicit failure. Streams are never transparently continued on another model.

Pause stops new model calls and crawler submissions while an active short
request may finish; Resume claims the persisted checkpoint; Cancel stops new
work, requests attached-crawler cancellation, retains traces/evidence, and
never auto-resumes. A server reboot during a deployment was recovered through
the release markers and `--resume`; the final deployment then completed with
all gates passing.

## Verification and production state

- Backend: `394 passed`, coverage `86.49%`.
- Frontend: 22 test files / 56 tests, lint passed, build passed; prior local
  coverage was `90.05%`.
- Shell syntax and restricted release-script tests passed.
- Remote release repeated backend `394 passed` and frontend 22/56, lint and
  build passed. Vite emitted only the existing large-chunk warning.
- API and Worker are active; localhost health is OK.
- Active crawler tasks: 0. Active Research tasks: 0. Browser processes: 0.
- Public observer still reports `SSL_ERROR_SYSCALL`; helper verification,
  Nginx checks, local health and production SNI loopback all passed, so this
  is the documented external-observer exception.
- Normal-user `status.sh` cannot read Nginx configuration directly, while
  the restricted helper's `verify` gate passed Nginx syntax and route checks.
- Production worktree is clean. Local worktree contains only the pre-existing
  untracked `CLAUDE.md`, which was not changed or committed.

## Scope and Phase 8D

Phase 8C-1 remains archived. No Discovery Engine traversal, recursive
recommendations, creator-graph expansion, multi-Agent, MCP, Notion, knowledge
graph, unattended monitor, auto-publishing, or automatic user action was
introduced. Phase 8D should start with a bounded candidate-discovery design
that reuses the completed Coverage Plan, entity concentration gate, source
chain, evidence independence and budget/runtime controls rather than adding
another Agent abstraction.
