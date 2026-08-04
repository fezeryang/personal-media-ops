# AI Research Workbench 8D-1/2/3/4/5

## 1. Scope / Trigger

Apply this contract when changing the AI Research home, Discovery Inbox,
Research Spaces, memory/evidence surface, or the navigation/legacy-surface
cutover. This is the primary product shell for the 8D workbench.

## 2. Signatures

`src/api/research.ts` owns Zod schemas and typed calls for Discovery candidates,
feedback, Research Spaces, and `/api/research/preferences`. Server state uses
TanStack Query through `use-discovery-queries.ts` and is invalidated after
feedback, follow-up creation, and space changes.

The canonical routes are:

```text
/research
/discoveries[/:candidateId]
/spaces[/:spaceId]
/memory
/tools
/settings
```
Legacy URLs remain compatibility redirects or low-level tool routes. They are
not primary navigation entries.

## 3. Contracts

- The primary sidebar and mobile rail contain only AI Research, Discovery
  Inbox, Research Spaces, Memory & Evidence, Tools, and Settings. The list is
  filtered by the server feature flags; legacy surfaces are hidden by default.
- The AI Research home starts with the natural-language goal, then exposes
  Recent Research, pending Discovery, owner decisions, the understanding card,
  bounded progress, and links to evidence/discovery. Advanced boundaries
  remain collapsed.
- Research creation is a two-step owner confirmation: the first submit displays
  a deterministic understanding preview; the preview accepts optional
  supplementary requirements; only the explicit confirmation starts the task,
  while “back to edit” does not call the create API.
- Research detail uses tabs: Overview, Research Process, Discovery, Evidence,
  Queries, Budget, and Technical Details. Overview is the default and shows
  goal/status/coverage/finding/new-content/discovery summary. Technical UUID,
  provider/model route, token detail, crawler IDs, internal status, raw errors,
  model-call trace, and raw context are not rendered in the default summary or
  user-facing tabs.
- Query execution groups are collapsed by default and sorted by
  `expected_value_score` descending. Rejected queries remain available with
  their durable reason. Trace groups are collapsed, searchable, and do not
  render empty tool/reason/token detail rows.
- Discovery cards show candidate type/state, final score, explanation, source
  counts, feedback actions, continue-to-research, and add-to-space. No card
  invents a title, source, score, or count when the API is empty or invalid.
- Discovery detail renders event aggregation (`first_seen`, `latest_seen`,
  platforms, related entities, and positive/negative/unknown evidence counts)
  when present, and shows `experimental_status` as an explicit unavailable-
  capability notice rather than implying a creator relationship or
  recommendation.
- Candidate feedback controls expose valuable, defer/follow, more-evidence,
  lower-similar-priority, mute-topic, known, irrelevant, and duplicate actions;
  the follow action states that it stores intent only and does not start an 8E
  monitoring task.
- Space items are typed and display the resolved item summary plus the real
  object ID. A missing item/error is visible; it is not replaced by a fixture.
- Budget views expose semantic resource totals and billing categories;
  model-call trace and raw execution context remain collapsed under Technical
  Details.
- Research HTML is still passed through the existing DOMPurify allow-list.
  JSON/API error and Zod mismatch states remain visible to the owner.
- Route-level page imports are lazy-loaded behind the existing Suspense
  loading boundary. All layouts must remain usable at 390px.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| `/api/research/preferences` fails | Keep the primary navigation stable, but never invent candidate/space data |
| Discovery list is empty | Show a real empty Inbox with the bounded-source explanation |
| Candidate detail/API mutation fails | Show the API error and keep the current candidate state |
| Feedback is pending | Disable feedback controls until the server response arrives |
| No Research Space exists | Explain that a space must be created before add-to-space can succeed |
| Space item API rejects an ID | Show the conflict/error; do not append an optimistic fake item |
| Task has partial completion | Label it as partial/incomplete and show missing requirements/next step |
| Legacy URL is opened | Redirect to the canonical surface or explicit low-level tool route |
| Feature flag disables Discovery | Hide the Inbox navigation entry and do not show fake Inbox content |
| Narrow viewport | Wrap grids and keep primary actions and tabs horizontally reachable |

## 5. Good / Base / Bad Cases

- Good: `/research` opens with “what do you want to know?”, and the owner can
  move from understanding to a real task without first designing platform
  queries.
- Good: a candidate detail explains relevance, novelty, evidence,
  independence, risk, and next action before exposing follow-up buttons.
- Base: no discoveries or spaces produce honest empty states while the rest of
  the authenticated workbench remains usable.
- Bad: keep twelve old modules in the primary rail, show a hard-coded “today”
  count, or treat a discovery candidate as a verified conclusion.

## 6. Tests Required

- API tests validate discovery filters, response parsing, feedback payloads,
  and Research Space summaries with Zod.
- Shell tests assert exactly the six canonical primary entries and no default
  legacy labels at 390px.
- Research page tests assert default Overview, the natural-language home and
  supplementary requirements, tab switching across process/discovery/
  evidence/queries/budget/technical detail, collapsed query groups/model-call
  trace/raw context, searchable/grouped trace, partial-completion copy, and
  real empty or API-error states.
- Discovery/Space page tests assert source explanations, feedback/undo,
  continue-to-research, add-to-space, owner-safe errors, and typed item forms.
- Run `npm run lint`, `npm run test`, and `npm run build` after route changes.

## 7. Wrong vs Correct

### Wrong

```tsx
const discoveries = apiError ? demoCandidates : apiCandidates;
```

### Correct

```tsx
{query.isError ? (
  <ErrorState error={query.error} onRetry={() => void query.refetch()} />
) : query.data?.length === 0 ? (
  <EmptyDiscoveryState />
) : (
  <DiscoveryList items={query.data ?? []} />
)}
```
