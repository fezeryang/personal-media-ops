# Frontend UX Audit

Date: 2026-08-08
Baseline: `b75215d4279e6eb7a65b7024b3838bca63601593` plus documentation-only
commits on `origin/main`
Scope: existing authenticated 8D–8F workbench; no new product phase

## Audit method

The audit inspected the route tree, every requested route-level page, the
shared shell/header/primitives, query hooks, API schemas, local fixture entry
points, and the local visual gate. The findings below describe the existing
implementation before the refinement changes.

## Route inventory

| Route | Page purpose | Primary user task | Primary CTA | Secondary actions |
| --- | --- | --- | --- | --- |
| `/research` | Start and review AI research | State a research goal and inspect progress | View research understanding / start research | Pause, resume, cancel, complete, rerun, inspect evidence and opportunities |
| `/discoveries` | Triage bounded discovery candidates | Decide whether a candidate matters | Candidate detail / feedback | Continue research, analyze opportunity, add to space, undo feedback |
| `/discoveries/:id` | Explain one candidate and its provenance | Understand why it was recommended and choose a next step | Continue research | Feedback, opportunity analysis, add to space, source links |
| `/spaces` | Organize long-lived research contexts | Choose or create a space | Create space / select space | Add materials, open discoveries |
| `/spaces/:id` | Review one research space | Add and browse accumulated material | Add item | Browse linked surfaces |
| `/memory` | Review persisted research knowledge | Compare conclusions, evidence, unknowns, and memory | Select a research record | Open source content, start research, open tools |
| `/monitoring` | Manage recurring research missions | Find a mission needing attention | Create monitoring | Open mission, inspect notifications |
| `/monitoring/:id` | Explain a mission and its runs | Decide whether to run, pause, or investigate a change | Run now | Pause, resume, archive, inspect changes/runs/baseline/scope/budget |
| `/opportunities` | Triage evidence-bound opportunities | Decide which opportunity is worth validating | Open opportunity | Return to research or discovery inbox |
| `/opportunities/:id` | Move one opportunity through validation/action | Make a bounded judgment and choose next step | Create or continue validation | Feedback, evidence, related research, action/outcome, add to space |
| `/tools` | Secondary operational entry point | Open low-level runtime and compatibility tools | Open a tool | Open capabilities, crawls, overview, legacy audit routes |
| `/settings` | Secondary configuration entry point | Choose configuration surface | Open a settings section | Models, integrations, security |
| `/settings/models` | Configure provider/model/runtime routing | Review and change model configuration | Add provider/model, test, save | Routes, usage, debug, prompt governance |
| `/settings/integrations` | Manage scoped API access | Create/copy/revoke an API key | Create API key | Copy one-time key, open OpenAPI docs |

## Cross-cutting findings

| Area | Before refinement | User impact | Target treatment |
| --- | --- | --- | --- |
| Information hierarchy | Page headers, teaching flow, summary cards, forms, lists, and detail content are simultaneously visible | The first useful action is pushed below the fold | Compact title/optional one-line support/action header; summary first; advanced/technical content behind disclosure |
| App shell | Desktop sidebar is always 272px; mobile renders every primary item in a horizontal overflow rail | Permanent desktop width; mobile requires scrolling to discover navigation | Persisted 72–80px collapsed sidebar; mobile top bar + Radix navigation drawer |
| Page headers | Every page has an eyebrow, large title, long description, and padded border block | Repeated product history consumes the first viewport | Remove phase/history language; title + optional one-line support + action |
| Filters | Several lists have no search/filter/sort; discoveries have only search + raw state select | 20–50 rows become hard to scan | Shared filter bar, business labels, sort control, removable chips, mobile filter panel |
| Master/detail | Research, discoveries, spaces, and memory use a two-column layout but no hide-list control | Detail never gets full width and mobile has no deliberate list/detail transition | Shared master-detail layout with persisted expanded/collapsed list state |
| Cards | Rows and secondary content are often nested in large bordered cards | High visual and vertical density; all content looks equally important | Use section/row surfaces; reserve cards for independent objects |
| Technical leakage | IDs, raw lifecycle/enum values, budgets, score internals, provider/model fields appear in normal or prominent views | Users must interpret implementation details | User labels in normal view; technical details grouped and collapsed |
| Action semantics | Feedback, validation, and action controls are shown as multiple same-weight buttons | High cognitive load and accidental state changes | One primary CTA; secondary actions in action menu; confirmations only for consequential destructive mutations |
| Mutation feedback | Pending labels exist in some flows, but many mutations have only cache invalidation or an error paragraph | A click can appear to do nothing | Pending state plus inline success/error feedback and visible updated state |
| Accessibility | Existing Radix dialogs provide a good base; tabs and custom card buttons lack a consistent shared contract | Keyboard/focus behavior varies by page | Shared primitives with labels, `aria-expanded`, tab semantics, focus restoration, Escape behavior |
| Overflow | Tab strips intentionally use `overflow-x-auto`, but page-level overflow is not guarded | Long Chinese text or controls can create document scrolling at 390px | `min-w-0`, wrapping, mobile filter/dialog, and automated document-width assertion |

## Page-by-page audit

### `/research`

* **Purpose/task:** Start a natural-language research task, then monitor and
  review its real execution/evidence.
* **Before:** Page header → four always-visible research-flow cards → 8F
  opportunity pulse → three equal home cards → open creation form → task list
  and task detail. The creation form is initially open and the task detail can
  expose seven tabs plus crawler, alignment, coverage, findings, actions,
  evidence, memory, and result surfaces.
* **Filters/sort:** None on tasks. The list is capped by a fixed 330px column;
  no search, business status filter, or sort selection.
* **Density:** Very high vertical density; nested cards and metric grids are
  repeated in home, task summary, evidence, coverage, and technical tabs.
* **Mobile:** Most grids wrap, but the page starts with several full-width
  sections and tab strips; the user must scroll a long stack before reaching
  the task list.
* **States:** Real loading/error/empty states exist for queries and creation,
  but the homepage empty state repeats across three cards.
* **Technical fields:** UUID, provider/model route, raw internal status,
  crawler IDs, token details, raw context, query lifecycle, and JSON scope
  drift are available; some are correctly technical-only, while labels such as
  `Bounded discovery`, `8D-0`, `inference`, and raw IDs still leak.
* **Actions:** Pause/resume/cancel/complete/rerun are real mutations. The
  primary CTA is not visually stable because the header action, composer, and
  task controls compete. Research Flow is explanatory content rendered as
  permanent cards and should be a collapsible help section.
* **Required refinement:** Focus the first screen on “你想研究什么？” plus
  compact Today/Focus groups; keep advanced fields collapsed; use a collapsible
  task list and detail tabs; group query/trace content; keep technical details
  behind explicit disclosure.

### `/discoveries` and `/discoveries/:id`

* **Purpose/task:** Triage discovery candidates and select a follow-up action.
* **Before:** Search and a state select are inside a large card. Candidate
  rows expose score, independent sources, platform/content/repost counts, two
  explanation lines, and next action. Detail exposes six metrics, six
  explanation cards, event aggregation, feedback, opportunity analysis,
  follow-up creation, space selection, and all sources in one vertical flow.
* **Filters/sort:** Search + raw state only. No type, platform, source,
  importance, sort, filter chips, or clear action.
* **Density:** Candidate rows show technical score/count fields that belong in
  detail; detail exposes nine feedback actions at once.
* **Mobile:** Feedback buttons wrap into a dense multi-row toolbar; space and
  follow-up forms remain in the main page.
* **States:** Real list/detail error and empty states exist. Mutation errors
  are visible; success mostly relies on query invalidation.
* **Required refinement:** Shared FilterBar; compact candidate rows; hide-list
  control; detail tabs (overview/evidence/why recommended/related/next
  actions/technical); one primary “继续研究” action with feedback/action menu.

### `/spaces` and `/spaces/:id`

* **Purpose/task:** Maintain a durable context and add existing research
  materials.
* **Before:** Inline create form and two-column list/detail. Add-material form
  requires a type select plus manual “对象 ID”, then displays IDs in each
  normal material row.
* **Filters/sort:** No space search, active/archived filter, sort, or item
  tab/search/sort.
* **Density:** Three large cards in the detail, with all typed items in one
  list. The list column cannot collapse.
* **Mobile:** The type/ID form stacks, but asking for an ID is a developer
  workflow and long item rows are dense.
* **States:** Real space list/detail loading/error/empty states exist; add
  mutation error is visible; no inline success state.
* **Required refinement:** Compact space list with search/status/sort and hide
  control; add-material picker dialog with search/type filter and resolved
  titles; current-space tabs for overview/research/discoveries/opportunities/
  evidence/actions; IDs only in technical details.

### `/memory`

* **Purpose/task:** Browse the knowledge retained by a research task.
* **Before:** Left research-task list plus one detail page that renders summary
  metrics, findings, all evidence, unresolved questions, and memory in two
  large columns/sections simultaneously.
* **Filters/sort:** No search, status filter, or sort on the task list; no
  evidence role/platform filter; no current/history or fact/inference/change
  controls for memory.
* **Density:** Evidence and memory entries are all expanded; source IDs are
  displayed as fallbacks and in source lines.
* **Mobile:** Columns stack into a long page; there is no deliberate detail
  tab transition or list collapse.
* **Required refinement:** Search/status/sort list, collapsible master column,
  detail tabs for overview/conclusions/evidence/unresolved/memory, filters on
  evidence and memory, compact list rows, technical IDs hidden by default.

### `/monitoring` and `/monitoring/:id`

* **Purpose/task:** Create, review, and control long-running monitoring
  missions.
* **Before:** List cards include type, frequency, last/next run, platform,
  model budget, and latest change. The create form occupies the page inline;
  notifications are a large panel in detail overview. Detail has tabs but
  overview already loads multiple queries and the run history is fully open.
* **Filters/sort:** No list search/filter/sort. Raw `mission_type` is shown in
  a list card. No quick status grouping.
* **Density:** Cards and change cards are tall; detail controls pause/run/
  archive have equal visibility; budget and technical tabs expose internal
  data directly after one click.
* **Mobile:** Create controls and action groups wrap; tabs intentionally scroll
  but notification content competes with the overview.
* **States:** Loading/error/empty, waiting platform/login, paused, degraded,
  and no meaningful change are represented honestly. Mutation feedback is
  mostly error/pending text.
* **Required refinement:** Compact mission rows; shared filters/sort; create
  dialog with natural-language first and collapsed advanced settings; compact
  notification icon/count and drawer; detail tabs with collapsed run rows and
  technical details.

### `/opportunities` and `/opportunities/:id`

* **Purpose/task:** Triage evidence-bound opportunities and move them through
  user-controlled validation/actions.
* **Before:** No list search/filter/sort. Three-column cards show type,
  readiness, long description, why-attention, evidence strength, source count,
  and next step. Detail has good tabs but a sticky summary with four same-level
  feedback buttons and full validation/action/outcome forms in their tabs.
* **Filters/sort:** None on the list. Technical score fields are prominent in
  cards and detail overview.
* **Density:** Large cards and all form fields are visible when the tab is
  selected, even before the owner chooses to create/edit a plan.
* **Mobile:** Cards are readable but action groups and sticky summary controls
  become multi-row; tab strip is a horizontal internal viewport.
* **States:** Empty/error/loading and evidence-insufficient states exist. Most
  mutations have pending labels, but success is not consistently announced.
* **Required refinement:** Search/type/readiness/status filters and business
  sort; compact cards; one primary “创建/继续验证”; feedback under “判断”
  menu; validation/action/outcome editors behind dialogs or collapsed panels;
  technical history and score keys grouped and translated.

### `/tools`, `/settings`, `/settings/models`, `/settings/integrations`

* **Purpose/task:** Secondary runtime/configuration surfaces.
* **Before:** Tools and Settings use a compact card grid and are lower risk.
  Model Center is intentionally dense and uses dialogs, but its tab strip and
  debug tables need mobile wrapping/viewport treatment. Integrations renders
  the API key form inline, exposes raw scope codes, and uses a trash icon for
  revoke without the existing AlertDialog confirmation.
* **Required refinement:** Keep technical density where useful, but compact
  headers, hide create forms until opened, add error/empty/success feedback,
  translate scope labels, guard dangerous revoke, and verify no page-level
  overflow.

## Shared component audit

| Component | Existing role | Gap |
| --- | --- | --- |
| `AppShell` | Sidebar, mobile rail, auth/logout, health | No collapse persistence, no mobile drawer, phase/branding copy, no tooltip for collapsed icons |
| `PageHeader` | Eyebrow/title/description/action | Description required and always tall; phase/history language is passed by every page |
| `Button` | Typed CVA variants and Radix Slot | No semantic action grouping or mutation feedback primitive; active controls need page-level audit |
| `Card` | Universal surface | Used for rows, sections, objects, and teaching content alike; creates nested-card density |
| `Dialog` | Radix modal with focus management | Good foundation; no shared picker/drawer composition |
| `AlertDialog` | Radix confirmation primitives | Present but not used for all consequential archive/revoke/abandon actions |
| `Input`/`Badge` | Basic field/status primitives | No shared search/filter/chip semantics or localized enum helper |
| Missing primitives | None | Need only components used by multiple pages: `CollapsibleSection`, `FilterBar`, `SegmentedTabs`, `SideDrawer`, `ActionMenu`, `EmptyState`, `MasterDetailLayout`, `SearchInput`, `FilterChip`, `SectionToolbar`, plus lightweight mutation feedback |

## Button audit baseline

The following active controls were found during the pre-change inspection:

| Page | Control group | Baseline classification | Finding |
| --- | --- | --- | --- |
| Shell | Navigation links, logout | `real_navigation`, `real_mutation` | Real, but mobile rail and desktop width need redesign |
| Research | create, task controls, tabs, query/trace toggles | `real_mutation`, `real_toggle`, `real_navigation` | Real; information overload and missing success feedback |
| Discoveries | candidate row, feedback buttons, continue, analyze, add-to-space, undo | `real_navigation`, `real_mutation` | Real but too many same-level feedback buttons |
| Spaces | create, space selection, add-to-space, discovery link | `real_mutation`, `real_navigation` | Real; manual ID is a bad user contract |
| Memory | task selection, source links, header links | `real_navigation`, `real_selection` | Real; no filtering/tabs/collapse |
| Monitoring | create, confirm, run, pause/resume, archive, notifications | `real_mutation`, `real_navigation` | Real; archive needs confirmation and notifications should move to drawer |
| Opportunities | opportunity links, feedback, plan/research/action/outcome mutations, tabs | `real_navigation`, `real_mutation`, `real_toggle` | Real; feedback/forms need action semantics and disclosure |
| Tools/Settings | links and dialogs, provider/model operations | `real_navigation`, `real_mutation`, `real_dialog` | Mostly real; integrations revoke needs confirmation and errors need visibility |

No decorative `<button>` was accepted as a product action in the audit. The
main violations are semantic overload (too many buttons) and technical
workflows (manual IDs), not known no-op handlers. The refinement will add a
machine-readable button-audit checklist to tests/docs and manually verify
pending → result behavior for core mutations.

## Priority order

1. AppShell, PageHeader, overflow, and shared primitives.
2. Research home/task master-detail and technical disclosure.
3. Discovery/opportunity filters, cards, action menus, and detail hierarchy.
4. Space picker and tabbed space detail.
5. Monitoring list/create/notification/detail density.
6. Memory tabs/filters and secondary Tools/Settings cleanup.
7. Fixture expansion, behavioral tests, screenshot/viewport evidence, release.
