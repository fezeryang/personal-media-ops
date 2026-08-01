# AI Model Center

## Scenario: Manage or diagnose Model Gateway configuration

### 1. Scope / Trigger

Apply when changing `/ai/models`, its Zod API schemas, provider/model forms,
route controls, usage views, or bounded debug request UI.

### 2. Signatures

`src/api/ai.ts` owns typed functions for provider templates/CRUD/test/refresh,
model CRUD, route read/write, usage/health reads, and debug generation/SSE.
`AiModelCenterPage` is routed at `/ai/models` in the authenticated shell.

### 3. Contracts

- Validate every JSON/SSE event with Zod; propagate normalized API errors.
- API Key is `type=password`, sent only when non-empty, and always starts blank
  on edit. Render only `credentials_configured` after save.
- Provider refresh results are candidates; importing opens a model form whose
  `enabled` value is false.
- Abilities are tri-state (`true`, `false`, `null`), not protocol-derived.
- Routes list only enabled models on enabled providers.
- Usage/cost/health render real API data or an explicit empty/unknown state.
- Debug accepts one short message and renders actual provider/model, latency,
  tokens, and fallback. Abort releases the SSE reader.

### 4. Validation & Error Matrix

| Condition | UI behavior |
| --- | --- |
| Secret already configured | blank key input plus “keep existing” guidance |
| Refresh returns candidates | show candidates; create nothing automatically |
| No invocations | “还没有模型调用记录”; no chart |
| Missing price | “未配置”; never zero |
| Zod contract mismatch | normalized 502-style error state |
| Provider/debug failure | visible error; no mock response |
| Stream aborted/unmounted | cancel fetch and release reader |

### 5. Good / Base / Bad Cases

- Good: an owner imports one candidate, reviews abilities, then enables it.
- Base: an empty installation shows provider/model/usage empty states.
- Bad: refill a saved key, auto-enable a discovered model, synthesize cost or
  capability badges, or turn the debug panel into a fake chat product.

### 6. Tests Required

- API request shapes, secret omission, candidate default, route payload, and
  fragmented SSE parsing.
- Provider list/add/edit/test, blank edit key, model ability edit, candidate
  confirmation, route save, usage empty/populated, debug result/error.
- Authenticated navigation and 390 px overflow/reflow reachability.
- Full `npm run lint`, `npm run test`, and `npm run build`.

### 7. Wrong vs Correct

#### Wrong

```tsx
<Input value={provider.api_key} />
```

#### Correct

```tsx
<Input type="password" autoComplete="new-password" value={draft.api_key} />
```
