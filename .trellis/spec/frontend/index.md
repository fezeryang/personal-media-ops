# Frontend Development Guidelines

> Best practices for frontend development in this project.

---

## Overview

This directory records the frontend conventions implemented by the Vite
workbench.

---

## Guidelines Index

| Guide | Description | Status |
|-------|-------------|--------|
| [Directory Structure](./directory-structure.md) | Module organization and file layout | Active |
| [Component Guidelines](./component-guidelines.md) | Component patterns, props, composition | Active |
| [Hook Guidelines](./hook-guidelines.md) | Custom hooks, data fetching patterns | Active |
| [State Management](./state-management.md) | Local state, global state, server state | Active |
| [Quality Guidelines](./quality-guidelines.md) | Code standards, forbidden patterns | Active |
| [Type Safety](./type-safety.md) | Type patterns, validation and API contract | Active |
| [Intelligence Workbench](./intelligence-workbench.md) | Authenticated shell, real intelligence views, and responsive design tokens | Active |

---

## Pre-Development Checklist

1. Read `directory-structure.md` before adding a module.
2. Read `hook-guidelines.md` and `state-management.md` for API-backed features.
3. Read `type-safety.md` before changing an API schema or result field mapping.
4. Read `component-guidelines.md` and `quality-guidelines.md` before UI work.

## Quality Check

Run from `frontend/`:

```bash
npm run lint
npm run test
npm run test:coverage
npm run build
```

Then verify desktop and narrow-screen layouts against a real local FastAPI
instance or an explicitly enabled development fixture.

---

**Language**: All documentation should be written in **English**.
