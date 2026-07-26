# Component Guidelines

> How components are built in this project.

## Overview

Components are typed functions. Pages compose feature components; shared UI
primitives wrap Radix where modal focus management or confirmation semantics
matter.

## Component Structure

Keep transport and data normalization out of render functions. Components
consume query hooks and normalized view models. Extract a subcomponent when it
owns state or cleanup, such as the QR object URL lifecycle.

## Props Conventions

Use named `interface` props for feature components and React DOM attribute
types for primitives. Never use `any`; use `unknown` at untrusted boundaries.

## Styling Patterns

Use Tailwind utility classes and theme tokens from `src/styles.css`. Use `cn`
when variants or conditional classes are required. Do not add one-off inline
style objects for normal layout or color work.

## Accessibility

- Every icon-only control has an accessible label.
- Inputs have labels; errors use `role="alert"`.
- Dialogs use Radix primitives.
- External links use a new tab only with `rel="noopener noreferrer"`.
- Logs and result content are rendered as text, never injected HTML.

## Common Mistakes

- A desktop table is not considered narrow-screen support. Provide a mobile
  card representation when key columns would move off-screen.
- Do not display backend filesystem paths or process IDs in user-facing task
  metadata.
