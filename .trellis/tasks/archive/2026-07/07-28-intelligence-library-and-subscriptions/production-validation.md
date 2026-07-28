# Stage Seven Production Validation

Validated on 2026-07-28 against the production release lineage beginning at
`668fec71e1ee18254acba173af72a66a0d41ed0d`. The last application validation
release before task archival was
`7e0e4583ff4687df330cf846785d9940c10a39b8`; the archival and journal commits
are recorded by Git and the final deployment report.

## Database and deployment

- Alembic upgraded from `0005_library_entities` to
  `0009_metrics_and_intelligence`.
- The migration backup is
  `/var/backups/mediaops/20260728T095102Z/mediaops.db`, SHA-256
  `5656c432a78f10985a8a88846cbf861b15174c4a2af0c60973ff1ff55c071cbd`.
- `PRAGMA integrity_check` returned `ok`.
- Production contains all 22 stage-seven tables and the reviewed due,
  active-session/key, entity-time, run-history, and evidence indexes.
- The existing task, library, provenance, and raw crawler output data were
  preserved. MediaCrawler remained pinned at
  `17f66121e0fcc40fc23958b995bec873d422667d`.

## Access control

- One owner was initialized interactively; no password entered chat, Git,
  command arguments, or deployment output.
- Browser login and session persistence succeeded. One remaining validation
  session was explicitly revoked, leaving zero active sessions.
- Session writes exercised the CSRF-protected browser path. Anonymous
  protected API access returns `401`; `/api/health` remains public.
- The production read-only validation key had prefix `4974803e` and only
  `library:read` plus `intelligence:read`. It received `403` from
  subscriptions, was revoked, then received `401`; its mode-0600 temporary
  file was removed. The full key was never printed or persisted outside its
  hash.
- All short-lived admin validation keys were revoked. Production has zero
  active API keys.
- A real Xiaohongshu run exposed an omitted quoted-dictionary redaction form.
  The Worker redactor and tests were fixed; 59 crawler logs were checked, 9
  were sanitized in place, and a second pass found zero files requiring
  further redaction.

## Subscription and scheduling

- Subscription `6452777f-2d5b-4826-ae01-08a71504a2cc` is named
  `AI Agent 每日观察`, queries `AI Agent`, targets `bili,xhs`, requests two
  results per platform, and remains disabled/manual.
- Manual run `5a652608-edd8-4fdd-876c-eeb8a5352e81` succeeded. Bilibili task
  `26f9f59f-90ca-4598-a4eb-09928d6bc3ad` ran before Xiaohongshu task
  `d4564da3-6fdb-42e0-a59a-e167eec2e7ca`.
- The run recorded 3 new contents, 1 existing content, and 1 existing content
  with changed metrics.
- A mode-0600 temporary copy of the production database verified scheduler
  idempotency without queuing extra production crawls: the first due poll
  created one run, the second created zero, the unique scheduled slot count
  was one, and the run contained two ordered platform tasks. The copy was
  deleted.

## Organization and creator observation

- Real content `f06c5ed3-8b13-43a0-82fd-acdcab68255e` was favorited, assigned
  tag `AI Agent` (`43fd6435-ac99-4faa-896e-f939d44b437b`), and added to
  collection `AI Agent` (`ed4d1620-8ba4-4a52-a682-93cbf4e61ca8`).
- The Bilibili watch run
  `a12ec6df-8018-41ff-9aaf-1f05cbb02cc2` reused its verified creator-task
  target and succeeded with one profile result.
- The Zhihu watch run
  `9b7b30dd-9937-48a9-ba48-33dfdf1de8d2` reused the verified creator URL and
  succeeded with one profile result. It created a creator metric snapshot
  with 8,527 followers and 818 following.
- Both watch records remain disabled. The production creator adapters returned
  no new content in these bounded profile checks, so the runs truthfully
  recorded zero new/existing contents rather than inventing activity.

## Trends, brief, and Agent API

- Three deterministic trend signals were generated from real data:
  `AI工作台` scored 71.67/detected, `AI Agent` scored 55.83/detected, and
  `咖啡` scored 23.66/insufficient_data.
- Brief `ca4b4c7d-c992-41fb-9ebe-ec5b25fb5db4` is the ready version 2 for the
  validated 24-hour window. It has 6 typed items and 30 evidence links. Version
  1 remains superseded. The daily schedule exists but is disabled.
- API v1 returned `200` for search, content, provenance, creator, creator
  activity, trends, and latest brief. Content and creator responses contained
  platform source metadata, and content omitted `raw_payload`.

## Final observed data and quality

- Production: 61 tasks, 30 contents, 32 creators, 60 comments, 142 task/entity
  provenance rows, 4 content snapshots, 1 creator snapshot, 3 trends, 2 brief
  versions, and 12 brief items.
- Zero active crawler tasks, subscriptions, watches, sessions, API keys, and
  browser processes.
- Backend: 316 tests passed; line coverage 87.31%.
- Frontend: 19 files / 45 tests passed; statements 95.63%, branches 89.54%,
  functions 98.85%, lines 95.83%; lint and production build passed.
- Server release-script tests and Bash syntax checks passed. ShellCheck was
  not installed.
- API and Worker were active. Nginx and production SNI loopback checks passed.
  The external Codex observer continued to see the previously documented TLS
  reset and was recorded as non-blocking under the established production
  exception.

