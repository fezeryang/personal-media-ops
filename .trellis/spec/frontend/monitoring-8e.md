# Monitoring Mission Frontend 8E

## Contract

The primary navigation label is `监控任务`, with routes `/monitoring` and
`/monitoring/:missionId`. Creation is a two-step flow: natural-language goal,
then an AI understanding card, then explicit Owner confirmation. Advanced
scope and budget controls stay collapsed by default.

The detail page uses the fixed tabs `概览`, `重要变化`, `运行记录`, `已知基线`,
`监控范围`, `预算`, and `技术详情`. The overview must answer what is being
monitored, what changed, whether it matters, platform state, and the next
recommended action. Monitoring changes link to the existing Discovery Inbox;
they must not create a second inbox.

API responses are parsed through Zod schemas in `src/api/monitoring.ts` and
queried/mutated through TanStack Query hooks. Loading, empty, API error,
waiting-login, paused, and no-meaningful-change states must be visible and
must not be represented by mock success data.

The required visual checks are 1440×900, 1280×720, and 390×844. The mobile
layout must have no horizontal overflow and must keep mission status, the
primary run/pause action, and the latest meaningful change reachable.

## Security and usability boundary

Prompt activation/rollback controls are explicit administrative actions and
must not be exposed as ordinary AI automation. No browser cookies, local
storage session backdoors, external push channel, or automatic mission
creation is allowed.

## Prompt Governance Replay

The AI Model Center's `Prompt 治理` panel may show the active and candidate
versions and offer `运行 <prompt_key> · Recorded Eval <version>` for each. The
Prompt key is part of the visible button label because all nine role cards can
contain the same version number. The action calls
the bounded `/api/ai/evals/replay` contract and renders the returned run ID,
case count, and status summary; it must not accept arbitrary recorded content
or start a live model/platform task. Query data is invalidated after a
successful replay so the fixed Eval cases show their latest result.

Activation and rollback remain separate, explicit Owner/CSRF-protected
actions with confirmation. This is a review surface, not a Prompt IDE: normal
users do not edit system Prompts, and no candidate is activated merely because
its Recorded Eval request succeeded.
