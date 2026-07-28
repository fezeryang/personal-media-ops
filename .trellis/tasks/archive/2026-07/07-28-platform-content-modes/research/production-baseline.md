# Stage-six production baseline

Captured read-only on 2026-07-28 Asia/Shanghai.

## Application

- Production application, frontend build marker, and published marker:
  `4df42050ff35d1a61e3e55bcf983419a9cbd13b5`.
- Production branch: `main`; worktree: clean.
- Local and GitHub `origin/main`:
  `9d66834dafdb90db02224a74ebfcea538359acc5`.
- API and Worker: active since 2026-07-28 13:31:06 CST.
- Local health: OK. Restricted helper status and Nginx check: OK.
- Production SNI loopback for `/`, `/api/health`, and `/crawler/tasks`: HTTP
  200.
- Codex external observer: `SSL_ERROR_SYSCALL`; this is the existing narrow
  non-blocking observer exception, not origin evidence.

## Database and resources

- Alembic: `0003_remaining_platforms` at head.
- Tables: `alembic_version`, `crawler_tasks`.
- Tasks: 28 total; 0 pending/running/waiting-login.
- Platform task counts: bili 7, dy 7, ks 3, tieba 2, wb 2, xhs 5, zhihu 2.
- Browser processes: 0. D-state processes: 0.
- Memory available: about 999 MiB. Swap: 1 GiB total, 0 used.
- Disk: about 28 GiB available.

## Capability API

- Enabled and production-verified search: bili, xhs, zhihu, wb, tieba.
- Douyin: disabled, code-ready, `deferred_resource_constrained`.
- Kuaishou: disabled, code-ready, `deferred_upstream_breakage`.
- Existing API advertises only search and reports no comment support.

## Pinned upstream

- `/opt/mediacrawler` commit:
  `17f66121e0fcc40fc23958b995bec873d422667d`.
- Branch/worktree: main/clean.
- Python 3.11.15, Playwright 1.61.0, Google Chrome 150.0.7871.186.
- No upstream update was performed.
