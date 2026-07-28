# Stage Five Remaining Platform Rollout

## Goal

Add truthful keyword-search support for Zhihu (`zhihu`), Weibo (`wb`), Baidu
Tieba (`tieba`), and Kuaishou (`ks`) without allowing any one platform to block
the others or regress the production-verified Bilibili and Xiaohongshu paths.

## Production Baseline

- Personal Media Ops production commit:
  `28cc6b78368e57076a95159ca269e6ca0afe01c8`.
- Enabled platforms: `bili,xhs`.
- Bilibili and Xiaohongshu are `production_verified`.
- Douyin is disabled, `code_ready`, and
  `deferred_resource_constrained`; stage five must not enable or retest it.
- Alembic is `0002_multiplatform_tasks`; API and Worker are active.
- The host has 2 vCPU, about 1.6 GiB RAM, 1 GiB swap, and one global browser
  task.

## Requirements

### Upstream audit and pinning

- Record development and production `/opt/mediacrawler` commit, branch,
  worktree, Python environment, Playwright/browser versions, platform source
  paths, and Runner CLI dependencies.
- Fetch the official upstream without pulling or mutating the verified
  production checkout. Compare the pinned commit with upstream main and
  identify changes affecting `zhihu`, `wb`, `tieba`, `ks`, `bili`, and `xhs`.
- If an upstream change is required, validate it in an isolated worktree or
  versioned release directory. Switch production only after Bilibili,
  Xiaohongshu, the target platform, dependencies, browsers, state isolation,
  process cleanup, and memory recovery pass.
- Pin and document the verified upstream commit; never track latest during a
  production deploy.

### Backend and persistence

- Register all seven platform codes in one Adapter registry.
- Add `ZhihuAdapter`, `WeiboAdapter`, `TiebaAdapter`, and `KuaishouAdapter`.
  Each owns capabilities, login behavior, Runner arguments, result discovery,
  normalization, URLs, raw payloads, errors, resource limits, and verification
  state.
- Expand capability state to distinguish `not_implemented`, `code_ready`,
  `enabled`, `production_verified`, `deferred_resource_constrained`,
  `deferred_upstream_breakage`, `deferred_login_required`, and `disabled`.
- Keep platform conditionals out of API routes, the Worker loop, React pages,
  and deployment scripts.
- Inspect the real SQLite schema before deciding on migration
  `0003_remaining_platforms`. Create it only if a real platform CHECK or schema
  contract requires expansion. Preserve all tasks and completed states and
  test both fresh creation and upgrade from `0002`.

### Runner and Worker

- Extend the reviewed repository Runner for `zhihu`, `wb`, `tieba`, and `ks`
  without modifying upstream MediaCrawler source.
- Preserve per-task output, logs, QR files, platform-isolated browser state,
  one global task, comments/sub-comments/proxies disabled, small requested
  counts, whole-process-group timeout/cancellation, and browser cleanup.
- Model login readiness per platform: QR pending, persisted login, expired
  login, no QR required, captcha required, and login timeout. No platform may
  wait indefinitely for a QR file.
- Every Runner/Worker/upstream/login/result change requires small real
  Bilibili and Xiaohongshu regressions after deployment.

### Frontend

- Drive all seven platforms and their real states from the capability API.
- Show Douyin as “资源限制，暂不可用”; distinguish `code_ready`,
  `production_verified`, disabled, and deferred states.
- Reject task submission for unavailable platforms, add platform filtering,
  consistent icons/names, platform-specific login hints, safe unified result
  cards, new-tab source links, broken-image fallback, and no untrusted HTML
  execution or mock fallback.

### Production rollout

- Integrate and verify platforms independently, normally in this order:
  Zhihu → Weibo → Tieba → Kuaishou. Reorder when upstream/runtime evidence
  supports it.
- Enable only one new platform per production window and run a small real
  keyword task before recording `production_verified`.
- A blocked platform gets an evidence-backed deferred state and does not stop
  the next independent platform.
- Pause only for QR/captcha/account action, a new external grant/secret,
  irreversible data work, new system privilege, or external-console action.

## Platform Validation

- Zhihu: `AI Agent`, requested count 5; validate question/article type, title,
  author, summary, URL, time, votes, comments, raw payload, and nulls.
- Weibo: `AI Agent`, requested count 5; validate safe text, author, time,
  reposts/comments/likes, URL, media, login state, and raw payload.
- Tieba: `人工智能`, requested count 5; validate title, forum, author, replies,
  time, URL, summary, raw payload, and the upstream PC-page compatibility fix.
- Kuaishou: `AI`, requested count 3; validate host memory/swap/process state
  before launch and resource recovery afterward. Defer as
  `deferred_resource_constrained` if it reproduces Douyin-like saturation.

## Acceptance Criteria

- [x] Upstream MediaCrawler audit and fixed commit are documented.
- [x] Four new Adapters, capabilities, login contracts, and result
      normalization are tested.
- [x] Any necessary Alembic migration preserves existing data and passes fresh
      and `0002` upgrade tests; no meaningless migration is added.
- [x] Capability API and frontend truthfully represent all seven platforms.
- [ ] Zhihu has a real successful task or an evidence-backed deferred state.
- [ ] Weibo has a real successful task or an evidence-backed deferred state.
- [ ] Tieba has a real successful task or an evidence-backed deferred state.
- [ ] Kuaishou has a real successful task or an evidence-backed deferred state.
- [ ] Bilibili and Xiaohongshu real regressions pass after relevant changes.
- [x] Douyin remains disabled and `deferred_resource_constrained`.
- [ ] Backend tests and frontend lint/test/build pass locally and in deploy.
- [ ] Code is committed and pushed; production is clean, healthy, idle, and
      has no browser residue.

## Definition of Done

- Each target platform is either `production_verified` or has one precise,
  evidence-backed deferred status.
- Production data, migrations, API, Worker, frontend, helper, Nginx, SNI
  loopback, resource recovery, backups, commits, and task results are reported.
- Independent observer TLS reset may use the existing narrow exception only
  after every origin-side gate passes.

## Technical Approach

Audit first, then extend the registry-driven platform contract and shared
Runner/Worker state machine. Deploy the multi-platform infrastructure once it
is green, then roll out one platform at a time with isolated configuration,
small tasks, regression checks, and resumable deployment stages.

## Decision (ADR-lite)

**Context:** Douyin showed that a resource-heavy or broken platform can block a
monolithic rollout.

**Decision:** Treat platform implementation and production verification as
independent state machines. Preserve one shared registry and one global task,
but let each platform advance or defer without changing unrelated platforms.

**Consequences:** A deferred platform remains visible and truthful; it does not
become a synthetic success or block other production verification.

## Out of Scope

- Re-enabling Douyin or implementing the capacity options in its deferred task.
- `detail`, `creator`, `comments`, or `sub-comments`; those belong to
  `platform-content-modes`.
- Automatic publishing, increased concurrency, proxies, large-scale
  collection, upstream core edits, or new root/system/network permissions.

## Research References

- `research/upstream-mediacrawler-audit.md`
- `research/current-cross-layer-contract.md`
- `research/database-schema-audit.md`
