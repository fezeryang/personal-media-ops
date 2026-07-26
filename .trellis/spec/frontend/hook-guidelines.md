# Hook Guidelines

> How hooks are used in this project.

## Overview

TanStack Query owns remote state. Fetch functions remain framework-independent
under `src/api`; hooks add cache keys, polling policy, and cache updates.

## Custom Hook Patterns

Keep query keys in a single feature key factory. Mutation success handlers
update the detail and list caches, then invalidate only data that must be
re-fetched.

## Data Fetching

- Pass TanStack Query's `AbortSignal` to every query function.
- Poll active task details every 2 seconds and stop high-frequency polling in
  terminal states.
- Treat QR HTTP 404 and not-yet-created logs as explicit expected states.
- Bound logs with `tail=300` and results with backend pagination.
- Let API/network errors reach the UI; never replace them with mock data.

## Naming Conventions

Use `use<Resource>Query` and `use<Action>Mutation`. Hooks must not read or write
local storage.

## Common Mistakes

Do not put a polling `setInterval` in a page. Query observers automatically stop
when pages unmount and receive request cancellation signals.
