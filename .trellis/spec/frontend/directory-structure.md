# Directory Structure

> How frontend code is organized in this project.

## Overview

The Vite application is feature-first. Shared transport, primitives, and page
shell code are separated from crawler-specific components and data rules.

## Directory Layout

```text
src/
├── api/                       # Fetch client, Zod API schemas, endpoint functions
├── components/
│   └── ui/                    # Reusable shadcn-style primitives
├── features/
│   └── crawler/
│       ├── components/        # Crawler-specific UI
│       ├── hooks/             # TanStack Query orchestration
│       └── lib/               # Pure status/result normalization
├── lib/                       # Cross-feature utilities
├── pages/                     # Route-level composition
├── test/                      # Shared Vitest setup
├── app.tsx                    # Route tree
├── main.tsx                   # Providers and browser bootstrap
└── styles.css                 # Tailwind theme and global base styles
```

## Module Organization

Endpoint calls belong in `src/api`, not components. Pure crawler transformations
belong in `features/crawler/lib`; server-state hooks belong in
`features/crawler/hooks`; route pages compose those pieces without duplicating
transport logic.

## Naming Conventions

- Files and directories use kebab-case.
- React components and exported component names use PascalCase.
- Hooks begin with `use`; query hooks end in `Query` and mutations end in
  `Mutation`.
- Tests are colocated as `*.test.ts` or `*.test.tsx`.

## Examples

- `src/api/crawler.ts` owns the crawler HTTP contract.
- `src/features/crawler/hooks/use-crawler-queries.ts` owns polling and cache
  updates.
- `src/features/crawler/lib/result-fields.ts` safely normalizes unknown JSONL
  record fields.
