# State Management

> How state is managed in this project.

## Overview

Use TanStack Query for server state, component state for transient controls, and
React Router for resource identity.

## State Categories

- Server state: health, task lists/details, logs, QR blobs, result pages.
- URL state: active route and `taskId`.
- Local state: filters, search text, result offset, dialog visibility, log
  refresh/scroll toggles, image failure state.
- Derived state: dashboard metrics, engine label, active/terminal checks.

## When to Use Global State

Do not add a global client store unless state must be shared outside the route
tree and cannot be derived from Query or URL state. The current application has
no global client store.

## Server State

The shared `QueryClient` defines retry behavior. Feature hooks own query keys
and status-dependent intervals. Create/cancel mutations update both list and
detail caches.

## Common Mistakes

Never persist QR data, Cookie material, logs, or crawler results in local
storage. Do not copy Query data into component state merely to render it.
