# Research Center 8D-0

## 1. Scope / Trigger

Apply this contract when changing the natural-language Research creation
flow, Intent Contract understanding card, information utility views, discovery
candidate/event/memory cards, or Intent Alignment Review. This supplements the
archived 8C page contract without reopening or renaming it.

## 2. Signatures

`src/api/research.ts` owns Zod schemas for the 8D-0 detail fields:
`intent_contract`, `intent_versions`, `assumptions`, `unknowns`,
`information_utilities`, `entity_candidates`, `event_candidates`,
`memory_items`, `alignment_review`, and the typed query fields
`record_type`, `gate_status`, `query_role`, and `decision`.

`ResearchTasksPage` renders the natural-language creation form, understanding
card, Research Plan, execution-query trajectory, information-value
distribution, candidates/events/memory, and alignment review from the
authenticated API response.

## 3. Contracts

- The creation form accepts a natural-language goal first. Advanced budget and
  platform controls remain available but do not replace the goal field.
- The understanding card shows interpreted goal, primary/secondary intents,
  confidence, assumptions/ambiguities, unknowns, time scope, platforms,
  evidence and counterevidence requirements, exclusions, and desired output.
- Draft tasks may submit one intent revision through the typed API mutation;
  the UI must not pretend a revision succeeded before the server response.
- Query trajectory visibly separates `user_goal` from `execution_query` and
  shows role, gate, decision, and lifecycle. A user goal is never rendered as
  a platform-executed search query.
- Utility cards show real counts and explainable labels for core evidence,
  discovery seeds, background material, counterevidence, event signals, noise,
  and duplicates. Empty data produces an honest empty state.
- Candidate entities are labelled `candidate_discovery`; events retain their
  source content; memory rows show type/key/confidence and do not imply
  automatic monitoring.
- Alignment review shows score, covered requirements, missing requirements,
  scope drift, status, and next step. `partial_completion` is displayed as
  incomplete rather than as success.
- API failures or Zod mismatches remain visible. The page never invents
  research counts, findings, sources, or model results.
- The page remains readable at 390px: cards wrap, long query values break,
  and the primary actions remain reachable without horizontal overflow.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Empty goal | Keep the create action invalid and show the real validation state |
| Low confidence | Show the one server-provided clarification question |
| Medium confidence | Show assumptions while allowing the default start action |
| Intent revision on non-Draft task | Disable/hide the revision form and preserve server state |
| Missing legacy 8D-0 fields | Parse defaults and label the historical/empty state |
| API/Zod error | Show a visible error; do not replace it with fixtures |
| No utility/candidate/event/memory rows | Show explicit empty states and zero only when the API count is real |
| Unknown cost/token field | Use the existing unavailable/not-applicable wording; never render zero as a fallback |
| 390px viewport | Wrap cards and keep create/control actions reachable |

## 5. Good / Base / Bad Cases

- Good: an exploration task opens with “我理解你希望探索……” and lists
  unknown product names and evidence gaps before execution.
- Base: a legacy task shows its historical intent source and no fabricated
  utility distribution.
- Good: a content row appears under both discovery seed and counterevidence
  when the API supplies both utility labels.
- Bad: start with a complex query-builder form, show only a single
  `research_mode`, or label every non-final item as noise.

## 6. Tests Required

- Parse populated and legacy-safe 8D-0 detail payloads with Zod.
- Render understanding card confidence, assumptions, unknowns, platforms,
  evidence requirements, and the Draft-only revision control.
- Render distinct exploration and comparison contracts and query roles.
- Render real utility distribution, candidate entities, event candidates,
  memory updates, and alignment review/partial completion.
- Test API error/empty states and 390px narrow-screen wrapping.
- Run `npm run lint`, `npm run test`, and `npm run build`.

## 7. Wrong vs Correct

### Wrong

```tsx
const utilityCount = detail.result?.items.length ?? 0;
<span>核心证据：{utilityCount}</span>
```

### Correct

```tsx
const coreEvidence = detail.information_utilities.filter(
  (item) => item.utility_type === "core_evidence",
).length;
<span>核心证据：{coreEvidence}</span>
```
