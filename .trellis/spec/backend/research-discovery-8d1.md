# Research Discovery and Spaces 8D-1/2/3

## 1. Scope / Trigger

Apply this contract when changing bounded Discovery generation, owner feedback
memory, Discovery Inbox APIs, or long-lived Research Spaces. The feature is
downstream of the 8D-0 Intent Contract and must never turn a search result into
an unverified product claim.

## 2. Signatures

The authenticated API surface is:

```text
GET  /api/research/discoveries?state=&research_task_id=&limit=&offset=
GET  /api/research/discoveries/{candidate_id}
POST /api/research/discoveries/{candidate_id}/feedback
POST /api/research/discoveries/{candidate_id}/continue
POST /api/research/discoveries/{candidate_id}/add-to-space
GET  /api/research/spaces
POST /api/research/spaces
GET  /api/research/spaces/{space_id}
POST /api/research/spaces/{space_id}/items
GET  /api/research/preferences
```
`DiscoveryEngine.generate_for_task(task_id, max_depth=1, max_seeds=24,
max_candidates=30)` is deterministic and source-bound. The repository owns
candidate lifecycle, score snapshots, source independence, feedback rules,
and typed space items.

Alembic revisions `0015_limited_discovery_and_feedback` and
`0016_research_spaces` own the Discovery run/seed/candidate/source/score/event,
feedback/preference, space, and space-item tables. Runtime startup must verify
`0016_research_spaces` as the current head; it must not upgrade the database.

## 3. Contracts

Candidate types are `entity`, `creator`, `topic`, `event`, `query`,
`pain_point`, `need`, `product_opportunity_signal`, and
`content_opportunity_signal`. Candidate depth is only `0` or `1`. Candidate
states are `generated`, `scored`, `queued`, `accepted`, `ignored`, `deferred`,
`converted_to_research`, `added_to_space`, `dismissed_duplicate`, and
`expired`.

Every candidate stores a normalized key, source task, source seed/content,
bounded score components, final score, counts, and an explanation containing
why it is relevant/new, evidence and independence, counterevidence, risks,
feedback impact, and a recommended next step. Sources retain platform,
content, URL/author, repost status, similarity, and independent group. Repost
match reasons are retained in the candidate's score explanation rather than
being added as an unversioned source-table field.

Feedback types are `valuable`, `irrelevant`, `already_known`, `duplicate`,
`follow`, `mute_topic`, `deprioritize_similar`, `needs_more_evidence`,
`converted_to_research`, and `added_to_space`. Scopes are `global`, `platform`,
`research_intent`, `research_space`, and `topic`. An undo marks the feedback
undone and deactivates the preference rule created from that feedback before
rescoring the candidate.

`continue` creates a new independent Research Task, records the follow-up task
on feedback, and marks the candidate `converted_to_research`. The new task
context retains the parent candidate ID, source task ID, source seed ID,
candidate type/normalized key, source content IDs, and a bounded source
summary. It does not mutate the original Research Task. `add-to-space` stores
a typed `discovery_candidate` item and records the space-scoped preference.

Research Spaces accept only these item types: `research_task`,
`discovery_candidate`, `evidence`, `entity`, `event`, `finding`,
`unresolved_question`, and `memory`. Space and candidate queries are always
owner-scoped.

The feature flags exposed by `/api/research/preferences` are
`research_primary_enabled`, `discovery_inbox_enabled`,
`legacy_today_visible`, `legacy_trends_visible`,
`legacy_subscriptions_visible`, `legacy_creator_watch_visible`, and
`manual_crawler_primary`. They are read from the corresponding
`MEDIAOPS_*` environment variables with primary Research/Discovery enabled
and legacy primary surfaces hidden by default.

Discovery seed collection is ordered and bounded: information-utility content,
favorites, owner-accepted candidates, active-space entity items, confirmed
events, then task entity/event candidates. A seed with no real content or
candidate source may be recorded for the run but cannot produce a candidate.
Cross-platform source lookup receives the intersection of the task's requested
platforms and `production_verified` search adapters that are currently enabled;
deferred or merely code-ready adapters are never used as validation evidence.
An empty platform intersection is fail-closed at the repository query boundary.
Source independence is also fail-closed: sources are compared in bounded
arrival order before they contribute to counts. An exact source URL, a
meaningful cross-platform title match, body similarity of at least `0.88`, or
a same-author cross-platform synchronization with title similarity at least
`0.75` (or body similarity at least `0.72`) is grouped with the first matching
source. The source retains `is_repost`, `repost_of_content_id`,
`similarity_score`, `repost_reason`, and the shared `independent_group`; the
score explanation exposes `repost_detection.suspected_repost_count` and the
matched reasons. This comparison is deterministic, bounded to the source list,
and never persists raw comparison text.
`confirmed_event`/`event_signal` seeds also create a source-bound lightweight
`event` candidate before aggregation, so event evidence is not limited to an
already-existing 8D-0 event row.
Event explanations additionally expose `first_seen`, `latest_seen`,
`related_entities`, `platforms`, `positive_evidence_count`,
`negative_evidence_count`, and `unknown_evidence_count`. The default Inbox
query excludes terminal low-value states (`ignored`, `dismissed_duplicate`, and
`expired`); an explicit state filter may still inspect them.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Discovery depth outside `0..1` | Reject the run; never recurse without a bounded depth |
| Candidate has no real source | Do not create a candidate; keep a seed/empty run explanation only |
| Exact normalized candidate already exists for owner/type | Upsert score/source facts without duplicating the candidate |
| Candidate is accepted/converted/added and receives a new score | Preserve the explicit owner state |
| Owner reads another owner's candidate/task/space | Return not found/owner-scoped failure; never leak existence |
| Feedback omits `feedback_type` without an undo ID | Return a validation/conflict error |
| Non-global feedback omits `scope_key` or global feedback supplies one | Return a validation/conflict error; never create a no-op preference rule |
| Undo belongs to another candidate or owner | Reject the undo and leave both feedback and preference active |
| Undo succeeds | Mark `undone_at`, deactivate its preference rule, then rescore |
| Continue request is blank/short/oversized | Reject; use the candidate title only when request is omitted |
| Space name duplicates an active owner space | Return conflict; do not overwrite the existing space |
| Space item target does not exist or is not owner-scoped | Return conflict/not found; do not create an orphan item |
| Populated 8D-1/2/3 tables are downgraded | Refuse downgrade to prevent data loss |
| Candidate generation raises | Finish the run as failed/partial with a visible runtime trace; never fabricate data |

## 5. Good / Base / Bad Cases

- Good: a real content card yields a depth-1 pain-point candidate with its
  seed, content ID, platform, independent-source count, and a score
  explanation that recommends more evidence.
- Base: a task with no utility/entity/event source produces a completed/partial
  run with zero candidates and an honest empty Inbox.
- Good: `valuable` raises feedback score, `irrelevant` lowers it, and undoing
  the feedback restores the neutral preference state.
- Good: continuing a candidate creates a separate task while preserving the
  original task and candidate lifecycle, with bounded source lineage in the
  follow-up context.
- Bad: creating a candidate from a model noun with no content/source, using
  search verification as detail/creator/comment verification, or making an
  old content collection serve as a research space without typed ownership.

## 6. Tests Required

- Migration tests upgrade a populated pre-`0015` database, pass SQLite
  `integrity_check`, preserve existing rows, and refuse downgrade when new
  tables contain data.
- Engine tests assert depth `1`, source-bound candidates, deterministic score
  components/explanations, exact and near-duplicate repost grouping with
  explainable reasons, cross-platform counts, pain-point generation, and no
  candidate without a source.
- Acceptance-contract tests cover the product-discovery objective with at least
  three high-scoring entities and a cross-platform source, plus the
  pain-point objective with direct negative evidence and an honest
  production-platform gate.
- Repository tests assert owner isolation, upsert uniqueness, lifecycle
  transitions, score snapshots, feedback rule creation/deactivation, and
  typed space-item validation.
- API tests assert exact list/detail response-model payloads, feedback/undo,
  continue-task creation, add-to-space, space retrieval, feature flags, and
  owner-safe errors.
- Runtime tests assert one bounded Discovery run per task and a visible
  `discovery_failed` trace event when generation fails.

## 7. Wrong vs Correct

### Wrong

```python
candidate = {"title": model_text, "final_score": 0.9}
save_candidate(candidate)
```

This makes an unsupported model phrase look like a product fact and cannot be
audited or reversed.

### Correct

```python
sources = sources_for_seed(seed, task, limit=12)
if sources:
    score = score_candidate(seed, sources, task, owner_id=owner_id)
    repository.upsert_candidate(
        source_seed_id=seed["id"],
        source_content_id=seed["source_content_id"],
        scores=score["scores"],
        score_explanation=score["explanation"],
        depth=1,
    )
```
