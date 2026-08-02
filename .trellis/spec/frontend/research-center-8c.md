# Research Center 8C

## 1. Scope / Trigger

Apply this contract when changing the Research task list/detail, research API
schemas, coverage/quality cards, budget trace, or Pause / Resume / Cancel UI.
The page must render server facts from the authenticated API and must not use
synthetic research results.

## 2. Signatures

`src/api/research.ts` owns Zod schemas and typed requests for task creation,
detail, and control actions. The detail schema includes platform coverage,
entity coverage, query lifecycle/metrics, content decisions, evidence
occurrences, categorized consumption, budget events, and step usage.

`ResearchTasksPage` renders the task summary, platform plan, entity coverage,
query queue, evidence pool, budget trace, model/fallback trace, and controls.

## 3. Contracts

- Display planned versus actual platforms and each platform's result count or
  explicit failure/deferred reason.
- Display entity evidence count, platform count, concentration ratio, and
  whether each target was reached; never call one entity a market trend.
- Display every query's lifecycle and a terminal unexecuted reason when it was
  skipped, rejected, superseded, or cancelled. Show marginal-yield metrics.
- Separate collected, adopted, not-adopted, and repost content; show adoption
  reason and occurrence count/source-chain provenance.
- Render subscription calls as token/call usage with “单次金额不适用”; render
  payg only when cost is calculated; render unknown price as “未配置”.
- Render provider instance, vendor, model, billing mode, tokens, cost, and
  fallback reason from API data. Do not infer billing from a model name.
- Pause, Resume, and Cancel use the server action and show the server's durable
  state/error; buttons must not pretend an action completed before the response.
- Layout must remain readable at 390px without horizontal overflow.

## 4. Validation & Error Matrix

| Condition | Required behavior |
|---|---|
| Missing optional 8C field from a legacy task | Parse with a safe default and label historical/unknown state |
| Zod mismatch or API failure | Show a visible error state; do not fabricate cards |
| No coverage/entity/evidence data | Show an explicit empty state |
| Unknown cost | Show “未配置” or “不可计算”, never zero |
| Control request pending | Disable the affected action and retain current state |
| Control request fails | Show normalized error and allow a safe retry |
| Narrow viewport | Wrap cards and values; preserve action reachability |

## 5. Good / Base / Bad Cases

- Good: a skipped query appears with its reason beside its score and platform,
  and a repost is visible without inflating the independent evidence count.
- Base: a pre-8C task shows its summary and an honest “暂无覆盖轨迹” state.
- Bad: hide failed platforms, turn null cost into `¥0`, or show a local mock
  finding when the API returns an error.

## 6. Tests Required

- Zod parsing for legacy and populated 8C detail payloads.
- Platform plan/result, entity ratio, query skip/marginal metrics, evidence
  adoption/repost, budget categories, subscription/payg/unknown cost, and
  fallback trace rendering.
- Pause/Resume/Cancel success and error states.
- 390px layout test plus lint, unit tests, coverage, and production build.

## 7. Wrong vs Correct

### Wrong

```tsx
const cost = detail.consumption.total_cost ?? 0;
```

### Correct

```tsx
const costLabel =
  detail.consumption.total_cost === null
    ? "未配置或不适用"
    : `¥${detail.consumption.total_cost}`;
```
