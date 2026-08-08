# Frontend Product UX Refinement

## Goal

Converge the current authenticated Personal Media Ops workbench so daily use
starts with a clear purpose, current state, and next action. The work is a
frontend information-architecture and interaction refinement across the
existing 8D, 8E, and 8F surfaces. It does not add a product phase, business
module, runtime behavior, AI prompt behavior, monitoring algorithm, or
opportunity algorithm.

## Scope confirmed from the user request

The core routes in scope are `/research`, `/discoveries`,
`/discoveries/:id`, `/spaces`, `/spaces/:id`, `/memory`, `/monitoring`,
`/monitoring/:id`, `/opportunities`, `/opportunities/:id`, `/tools`,
`/settings`, `/settings/models`, and `/settings/integrations`. Legacy routes
and redirects remain compatible.

The refinement must establish:

* summary-first headers and progressive disclosure;
* a collapsible desktop sidebar with a persisted preference;
* a mobile top bar and accessible navigation drawer instead of a page-wide
  navigation rail;
* no document-level horizontal overflow at the required desktop and mobile
  viewports;
* shared filter, tabs, collapsible-section, drawer/action-menu, empty-state,
  and master-detail patterns where at least two real pages use them;
* compact list density, searchable/filterable/sortable list surfaces, and
  collapsible master columns for research, discoveries, spaces, and memory;
* user-friendly research-space material picking without manual object IDs in
  the normal workflow;
* tabs for detail surfaces and collapsed advanced/technical content;
* Chinese user-facing labels for enum/status fields, with IDs and raw fields
  kept in technical details only;
* real mutation loading, success, and error feedback;
* a complete visible-button audit with no fake, decorative, or unfinished
  actions exposed as active controls;
* local fixtures that exercise long lists, empty/loading/error/blocked states,
  and long Chinese content.

## Existing constraints

* Keep the existing React, Tailwind, Radix Dialog, TanStack Query, and Zod
  stack. Do not add a large UI framework or toast dependency.
* Keep API contracts stable. A minimal read-only lookup endpoint is allowed
  only if the material picker cannot be built from existing list/detail data.
* Do not change the research/monitoring/opportunity runtime semantics or
  crawler concurrency.
* Do not expose owner session material, cookies, or production data to local
  fixtures.
* Preserve the six canonical primary navigation entries plus monitoring:
  AI 研究, 发现收件箱, 研究空间, 记忆与证据, 监控任务, 工具中心, 设置.
* Preserve all existing legacy redirects.

## Acceptance criteria

* [ ] The audit is recorded in `docs/frontend-ux-audit.md`.
* [ ] The shell has desktop collapsed/expanded states, persisted locally,
  with accessible labels and active navigation state.
* [ ] Mobile navigation is a focus-managed drawer that closes on navigation
  and Escape; no primary navigation is implemented as page-level horizontal
  scrolling.
* [ ] The required routes have compact headers, summary-first defaults, and
  progressive disclosure for advanced, raw, historical, budget, and technical
  information.
* [ ] Research, discoveries, monitoring, opportunities, spaces, and memory
  lists expose search/filter/sort controls appropriate to the surface and
  support collapsed list columns on desktop.
* [ ] The research-space picker lets an owner search and choose existing
  materials without typing an ID; the API contract remains bounded and typed.
* [ ] Discovery and opportunity feedback actions have one primary action and
  secondary actions behind an action menu; meaningful destructive state changes
  use the existing Radix confirmation primitive.
* [ ] Every visible mutation communicates pending and the resulting success or
  error; no visible active button is a no-op.
* [ ] User-facing pages do not show phase labels, raw IDs, internal enum names,
  or snake_case fields outside technical details.
* [ ] Local fixtures cover 20–50 item lists, long titles/text, empty/loading/
  error/blocked states, and mobile filter/drawer behavior.
* [ ] Browser checks verify 1440×900, 1280×720, 1024×768, and 390×844; at
  390px `document.documentElement.scrollWidth <=
  document.documentElement.clientWidth` for every core route.
* [ ] Backend pytest, frontend lint/test/build, migration checks, shell checks,
  `scripts/test/local-gate.sh`, release candidate preparation, production
  deployment, production smoke, and the final Owner product review are
  recorded with their actual status.

## Out of scope

* New 8G or other product phases, new primary navigation modules, or new
  business capabilities.
* Backend architecture changes, AI prompt changes, monitoring algorithms,
  opportunity scoring, crawler runtime behavior, or automatic publishing.
* Replacing the existing visual language with a new color system or large
  visual redesign.
* Deleting legacy routes, production data, browser login state, or databases.

## Technical approach

Start with the existing shell/primitives and introduce only shared components
used by multiple real pages. Keep server state in TanStack Query and transient
drawer/filter/tab state local to the page or URL. Use Radix Dialog for mobile
navigation, pickers, and confirmations. Add a bounded typed lookup API only
if current list/detail contracts cannot supply the research-space picker.

The implementation order is:

1. audit and shared UX primitives;
2. shell, header, mobile navigation, and overflow guard;
3. list filters and collapsible master-detail patterns;
4. research/discovery/space/memory/monitoring/opportunity detail disclosure;
5. secondary surfaces, fixtures, button audit, tests, screenshots, and release.

## Decision (ADR-lite)

**Context:** The current product already contains the intended business
capabilities, but the UI presents too many equally weighted sections,
technical fields, and actions at once.

**Decision:** Use a small shared interaction vocabulary—summary header,
filter bar, segmented tabs, collapsible section, drawer/action menu, empty
state, and collapsible master-detail—then apply it consistently to existing
routes. Keep full information available behind explicit controls.

**Consequences:** The work improves daily scanability without changing the
underlying business contracts. The main risks are route-level regressions,
mobile overflow, and hidden-but-still-needed evidence; local fixtures and
behavioral tests must cover these before release.

## Technical notes

* Audit source: `docs/frontend-ux-audit.md`.
* Frontend contracts: `.trellis/spec/frontend/research-workbench-8d.md`,
  `.trellis/spec/frontend/monitoring-8e.md`,
  `.trellis/spec/frontend/opportunity-action-8f.md`,
  `.trellis/spec/frontend/component-guidelines.md`,
  `.trellis/spec/frontend/quality-guidelines.md`.
* Existing shared primitives: `frontend/src/components/ui/`.
* Existing local fixture routes: `/__local/fixtures` and
  `/__local/opportunities`.
