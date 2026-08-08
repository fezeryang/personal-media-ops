# Opportunity & Action 8F Frontend

8F is a layer inside the existing AI Research workbench. Keep the canonical
primary navigation unchanged; route Opportunities from the AI workbench,
Discovery Inbox, and Research Spaces rather than adding an unrelated dashboard.

## Product surface

`/opportunities` lists a small number of evidence-bound cards. An opportunity
detail uses a sticky summary and tabs for overview, Evidence Pack, Validation
Plan, related Research, Actions/Outcomes, and technical history. User-facing
labels say “证据强度”, “独立来源”, “反向证据”, and “机会成熟度”; raw field
names remain in technical detail only.

The empty state must explain how more evidence can produce a candidate. The UI
must show `needs_more_evidence` and counterevidence as meaningful states. A
Content Opportunity displays audience, content gap, saturation qualification,
and evidence-bound angles; it must not call a sample “全网热点”.

## User control

Feedback does not equal validation. Validation Plans require an explicit user
confirmation before follow-up Research. Actions remain proposed until the user
approves them, and Outcome entry is available only after completion. Outcome
forms are manual records; the frontend never publishes, contacts, pays, or
submits to a third party.

## API and state

API modules use Zod response schemas and React Query hooks. Mutations invalidate
the Opportunity list/detail and Research Space queries. No `any` is allowed.
Use the existing `Card`, `Badge`, `Button`, `Input`, `PageHeader`, and
`ErrorState` primitives. Keep loading, empty, error, evidence-insufficient,
desktop, and 390px mobile states visible in local fixtures.

## Test and visual obligations

`opportunities-page.test.tsx` and the local fixture harness cover empty state,
Evidence Pack, content opportunity, validation, completed Action/Outcome, and
no fabricated result. Verify `/research`, `/discoveries`, `/spaces`, and
`/opportunities` at 1440×900, 1280×720, and 390×844 before release; do not use
production as the first UI validation environment.
