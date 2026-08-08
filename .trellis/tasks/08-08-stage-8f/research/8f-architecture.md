# Stage 8F architecture research

## Repository findings

* 8E already has owner-scoped Monitoring and Discovery repositories, versioned
  evidence/memory concepts, and a typed Research Space item table.
* Alembic is the only supported schema change mechanism; runtime startup checks
  the head and does not auto-upgrade.
* FastAPI writes use `require_owner_session`, which supplies CSRF validation;
  Pydantic request models reject unknown fields.
* Frontend API modules use Zod schemas and React Query hooks. Pages are composed
  inside the existing AppShell and should not add a new first-class navigation
  surface unless unavoidable.

## Converged approach

Use one new 8F migration and a dedicated `OpportunityRepository` plus small
deterministic `OpportunityService`. Keep source relations explicit and keep
history append-only for opportunity versions, feedback, validation results,
actions, outcomes, and memory updates. Let existing research and discovery
repositories remain the source of their own facts; 8F only references them.

The service may aggregate existing evidence into a candidate when the source
chain meets minimum requirements. It must return `no_opportunity_identified`
or `needs_more_evidence` when it does not. A live model is optional for the
first bounded implementation; the Prompt Registry roles and Recorded Eval
cases provide governance without making local UI fixtures depend on provider
credentials.

## Rejected approaches

* A second generic knowledge graph: unnecessary for the single-owner SQLite
  product and outside 8F.
* A single opaque opportunity score: it hides evidence and counterevidence and
  conflicts with the Product Constitution.
* Automatic conversion of every Discovery Candidate: it would confuse
  discovery value with actionable opportunity and create notification noise.
* A project-management subsystem: Actions stay lightweight and owner-approved.
