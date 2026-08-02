# 8C completion initial audit

Date: 2026-08-02 (Asia/Shanghai)

## Local

* Local `main` and fetched `origin/main`: `07dbf85`.
* Existing quality foundation migration head: `0012_research_quality_foundation`.
* Existing 8C-1 implementation is in `app/services/ai/research_quality.py`,
  `research_tools.py`, `research_runtime.py`, `repositories/research.py`, and
  the Research page/API schemas.
* Existing defaults include `RESEARCH_DEFAULT_REQUESTED_COUNT = 12`; the
  production data also contains older five-item crawls, so the new runtime must
  preserve the 12-item default rather than regress to five.

## Production read-only evidence

* Host alias: `mediaops-prod`; API and Worker are active; localhost
  `/api/health` is OK; no active crawler or research task.
* Production commit: `f156017573af3f9ba5d72fcd6ba875c2ed11746b`; worktree clean.
* Database revision: `0012_research_quality_foundation`; integrity check `ok`.
* `/opt/mediacrawler` is clean at
  `17f66121e0fcc40fc23958b995bec873d422667d`.
* `/opt/personal-media-ops/scripts/crawler/run_mediacrawler.py` and
  `/var/lib/mediaops/bin/run_mediacrawler.py` have the same SHA-256.
* Targeted production configuration: `MEDIAOPS_ENABLED_PLATFORMS` is
  `bili,xhs,zhihu,wb,tieba,ks`. Effective search statuses are Bilibili, XHS,
  Zhihu, Weibo, Tieba production-verified/enabled; Douyin deferred for host
  resources; Kuaishou search deferred for upstream breakage.
* Database counts: 100 crawler tasks (77 succeeded, 22 failed, 1 cancelled),
  16 research tasks (5 done, 10 failed, 1 cancelled), 82 queries, 49 findings,
  150 finding-content links, 193 evidence occurrences, and 151 AI invocations.
* Research platform distribution: 13 tasks explicitly `['bili']`; 3 tasks
  specified `['bili','xhs','zhihu','wb','tieba']`. The completed multi-platform
  task crawled only `bili` and `xhs`; its `queries` table was empty because it
  predates the quality migration path. Recent failures include
  `all research query candidates were rejected` and an older
  `IngestionResult` attribute error.
* AI records: MiniMax is tested tool-capable and streaming; GLM is tested
  non-tool-capable; DeepSeek is tested non-tool-capable. All 151 invocations
  are currently uncosted and the live routes put MiniMax on `tool_calling` and
  DeepSeek on `default`/`fallback`.
* Unauthenticated `/api/crawler/capabilities` correctly returns 401. Internal
  registry inspection was used only to confirm the effective capability facts;
  no auth or credential boundary was bypassed.
* Public health from the observer failed with `OpenSSL SSL_ERROR_SYSCALL`; the
  production local health gates passed and the exception remains subject to
  post-release helper/Nginx/SNI checks.

## Main diagnosis

The Bilibili-only behavior is not caused by the current production allow-list:
the allow-list already contains five real search platforms. Most old tasks
stored Bilibili because the task request explicitly selected it (the old
frontend default/previous operator scope), while the runtime's platform
rotation was tied to the small crawl budget and stopped after its first two
platforms. 8C must make platform coverage a durable plan with per-platform
completion/skip reasons instead of relying on incidental round-robin order.
