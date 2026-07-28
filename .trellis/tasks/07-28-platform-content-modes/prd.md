# Platform Content Modes

## Goal

After stage-five keyword search, implement a truthful capability matrix for:

```text
platform × search
platform × detail
platform × creator
platform × comments
platform × sub-comments
```

## Requirements

- Mark every combination independently as `not_implemented`, `code_ready`,
  `enabled`, `production_verified`, or `deferred`.
- Implement and verify modes platform by platform.
- Keep comments and sub-comments disabled by default, including after code
  completion; allow only small explicit operator validation.
- Do not infer support for one mode from success in another mode.

## Acceptance Criteria

- [ ] The API exposes the detailed matrix.
- [ ] The frontend renders the matrix truthfully.
- [ ] Each implemented combination has isolated tests and real validation
      evidence before `production_verified`.

## Out of Scope

- This task starts only after stage-five search rollout is complete.
