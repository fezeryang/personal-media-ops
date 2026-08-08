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
- When a research response contains a crawler task ID, Overview also exposes a
  typed link to the canonical `/tools/crawls/:taskId` detail route. The link
  explains that platform login is separate from the Owner Workbench login; a
  `WaitingLogin` task tells the owner to complete the platform QR/verification
  in their Windows browser while the server Worker continues the task. The
  QR itself remains owned by the crawler detail surface and is never copied
  into the research page or a temporary automation profile.
- Query execution groups are collapsed by default and sorted by
  `expected_value_score` descending. Rejected queries remain available with
  their durable reason. Trace groups are collapsed, searchable, and do not
  render empty tool/reason/token detail rows.
- Discovery cards show candidate type/state, final score, why-relevant/why-new
  explanations, independent-source/platform/repost counts, a suggested next
  action, feedback actions, continue-to-research, and add-to-space. No card
  invents a title, source, score, or count when the API is empty or invalid.
- Discovery detail renders event aggregation (`first_seen`, `latest_seen`,
  platforms, related entities, and positive/negative/unknown evidence counts)
  when present, and shows `experimental_status` as an explicit unavailable-
  capability notice rather than implying a creator relationship or
  recommendation.
- Candidate feedback controls expose valuable, defer/follow, more-evidence,
  lower-similar-priority, mute-topic, known, irrelevant, and duplicate actions;
  topic-level actions send an explicit normalized topic scope, and the follow
  action states that it stores intent only and does not start an 8E monitoring
  task. Undo always targets the newest active feedback returned by the API.
- Space items are typed and display the resolved item summary plus the real
  object ID. A missing item/error is visible; it is not replaced by a fixture.
- Budget views expose semantic resource totals and billing categories;
  model-call trace and raw execution context remain collapsed under Technical
  Details.
- Research HTML is still passed through the existing DOMPurify allow-list.
  JSON/API error and Zod mismatch states remain visible to the owner.
- Route-level page imports are lazy-loaded behind the existing Suspense
  loading boundary. All layouts must remain usable at 390px.
- `/tools/overview` is the runtime-only operations surface: it reads service
  health, active Research and crawler work, platform capability facts, model
  health, and resource usage. It must not reuse legacy library counts,
  subscription activity, trend generation, or “command center” copy.
- Legacy Today, Trends, Subscription, and Creator Watch pages remain reachable
  only for historical audit. Each page shows the explicit stopped-core-product
  notice and exposes no create, edit, run, pause, resume, or regenerate action.

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
| Research has a crawler task ID | Show a direct platform采集 detail link from Overview; distinguish platform login from Owner Workbench login |
| Research status is `WaitingLogin` | Show the platform采集 link and tell the owner to scan/verify in Windows Chrome; do not request a WSL browser or browser state export |
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
  trace/raw context, searchable/grouped trace, partial-completion copy, direct
  crawler-detail links for platform authentication, and real empty or
  API-error states.
- Discovery/Space page tests assert source explanations, feedback/undo,
  continue-to-research, add-to-space, owner-safe errors, and typed item forms.
- Runtime overview tests assert real operations metrics and the absence of
  legacy command-center metrics. Legacy page tests assert the stopped-product
  notice and read-only action boundary.
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

## Scenario: Progressive-disclosure workbench surfaces

### 1. Scope / Trigger

Apply when refining the existing authenticated 8D–8F workbench without adding
business capability: navigation, list density, filters, master/detail layouts,
tabs, dialogs, action menus, technical disclosure, or responsive behavior.

### 2. Signatures

```text
FilterBar({ search, filters, sort, chips, onClear })
MasterDetailLayout({ list, detail, listLabel, storageKey })
CollapsibleSection({ title, description, count, children })
SegmentedTabs({ value, onChange, label, items })
SideDrawer({ open, onOpenChange, title, children })
GET /api/research/space-items -> human-readable picker options
```

### 3. Contracts

- Core lists with more than ten likely rows expose search, a business filter,
  and sort. Desktop keeps the bar compact; mobile uses search plus a filter
  Drawer.
- Research, Discovery, Space, and Memory expose a simple list expanded/
  collapsed control. `localStorage` is optional and failures cannot block the
  page.
- Default detail content is summary-first. Technical IDs, raw enums, budget
  internals, traces, and long raw evidence sit behind named disclosure.
- One visually primary action remains on the page. Secondary mutations use an
  Action Menu; reject/archive/cancel/abandon use the existing Radix
  AlertDialog when they have consequential state effects.
- Every mutation exposes pending state and visible updated state, success, or
  error. Failed requests are not replaced with fixtures.
- Tabs have tab semantics and keyboard navigation. Drawer/Dialog uses Radix
  focus management and Escape. Icon-only controls have accessible names and
  collapse controls expose `aria-expanded`.
- Ordinary pages do not create document-level horizontal overflow at 390px.
  Tab strips, table viewports, and code/log viewers may scroll internally.

### 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| No list results | Truthful empty state without a disabled-button wall |
| Search/filter has no match | Keep chips and show a clear no-match state |
| Mobile filter opens | Focus is managed, Escape works, and page width stays bounded |
| List is collapsed | Detail fills content width and exposes “显示列表” |
| Storage read/write fails | Use default expanded state; never throw during render |
| Mutation is pending | Disable only the affected action and show progress text |
| Mutation fails | Keep current data and show actionable error |
| Technical disclosure closed | Do not render UUID/raw lifecycle/budget internals in normal flow |
| Document width exceeds viewport | Fix the owning layout; do not rely on page scrolling |

### 5. Good / Base / Bad Cases

- Good: a user identifies the page, filters a dense list, collapses it, reads a
  summary, and reaches the primary next action within one screen.
- Base: a long Chinese title wraps inside a `min-w-0` row while raw evidence
  remains available through a named disclosure.
- Bad: five mobile selects in a row, a UUID input in the normal Space flow,
  twelve equal-weight buttons, or a decorative button with no handler.

### 6. Tests Required

- Shared primitive tests cover FilterBar search/clear/mobile Drawer, Tabs
  keyboard semantics, CollapsibleSection `aria-expanded`, and Master/Detail
  collapse/persistence.
- Page tests cover real filter changes, clear chips, Tabs, Picker selection,
  destructive confirmation, mutation calls, and pending labels.
- Local UX fixtures render 24 rows plus loading/empty/error/platform-blocked/
  long-text states and assert `scrollWidth <= clientWidth` at all viewports.
- Run the full local gate before preparing an RC.

### 7. Wrong vs Correct

#### Wrong

```tsx
<input aria-label="对象 ID" />
<button className="primary">归档</button>
<div>{rawInternalStatus}</div>
```

#### Correct

```tsx
<Button onClick={() => setArchiveOpen(true)}>更多</Button>
<AlertDialog open={archiveOpen}>...</AlertDialog>
<details><summary>技术详情</summary>{rawInternalStatus}</details>
```
