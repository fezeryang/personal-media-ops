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
| [AI Model Center](./ai-model-center.md) | Provider/model forms, route editing, usage semantics, and bounded gateway diagnostics | Active |
| [Research Center 8C](./research-center-8c.md) | Platform coverage, evidence decisions, budget trace, and durable controls | Active |
| [Research Center 8D-0](./research-center-8d0.md) | Intent understanding card, information utility, discovery candidates, memory, and alignment | Active |
| [AI Research Workbench 8D-1/2/3/4/5](./research-workbench-8d.md) | Discovery Inbox, research spaces, memory/evidence, tabbed research detail, and canonical navigation | Active |
| [Monitoring Mission Frontend 8E](./monitoring-8e.md) | Two-step monitoring creation, fixed mission detail tabs, Inbox integration, and responsive states | Active |

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
