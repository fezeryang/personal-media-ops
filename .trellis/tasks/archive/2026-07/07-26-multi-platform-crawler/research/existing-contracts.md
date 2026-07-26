# Existing Crawler Contracts

## Repository State

- Baseline commit:
  `0a23f47f3b6931fa0cdfe1bb17cf448324176b58`.
- The worktree was clean and matched `origin/main`.
- The API, SQLite DDL, Worker command builder, docs, and React form are
  Bilibili-specific.
- The Worker already enforces one process globally with a file lock and an
  atomic SQLite claim.
- Existing task paths and API pagination are generated from the task UUID and
  must remain unchanged.

## Production Evidence (Read-only)

The production host was inspected through `mediaops-prod` without running a
crawler or reading `.env`, cookies, browser state, QR codes, or result data.

- Runner:
  `/var/lib/mediaops/bin/run_mediacrawler.py`
- Runner SHA-256:
  `1c2905781ed718206ed382bcd52c710afd0477eb4d20c7fe9fc8071bb92cafdb`
- MediaCrawler revision:
  `17f66121e0fcc40fc23958b995bec873d422667d`
- The installed Runner accepts only `bili`.
- The installed MediaCrawler source contains `bili`, `xhs`, and `dy`
  keyword-search crawlers with QR-code login.
- All three login implementations call `tools.utils.show_qrcode`; successful
  login logs contain `Login successful`.
- XHS search uses a fixed 20-item page and raises a request below 20 to 20.
- Douyin search uses a fixed 10-item page and raises a request below 10 to 10.

## Result Source Fields

- Bilibili content JSONL contains `video_id`, `title`, `nickname`,
  `video_url`, `video_cover_url`, video/like/favorite/comment/share counts,
  `create_time`, and `source_keyword`.
- XHS content JSONL contains `note_id`, `type`, `title`, `desc`, `nickname`,
  `note_url`, comma-separated `image_list`, like/favorite/comment/share
  counts, `time`, and `source_keyword`.
- Douyin content JSONL contains `aweme_id`, `aweme_type`, `title`, `desc`,
  `nickname`, `aweme_url`, `cover_url`, like/favorite/comment/share counts,
  `create_time`, and `source_keyword`.

## Constraints

- Do not modify or copy MediaCrawler core source.
- A repository-owned Runner may adapt fixed, validated task options to the
  external checkout.
- Public results must be capped at `requested_count` because external platform
  page sizes may produce extra raw records.
- Raw JSONL remains task-local and unchanged for compatibility and diagnosis.
- XHS and Douyin are code-supported but not production-verified in this task.
