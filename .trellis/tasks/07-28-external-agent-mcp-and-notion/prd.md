# External Agent MCP and Notion

## Status

`deferred_product_direction_changed`.

产品优先建设内置 AI Runtime 与 Model Gateway；MCP 和 Notion 调整到后续外部集成阶段。
保留以下历史规划作为未来外部集成阶段的输入，但它不再是当前开发主线，也不得在阶段
8A 中提前实现。

## Baseline

Stage seven provides:

- `AgentToolService` stable internal DTOs;
- scoped API keys;
- read-oriented REST API v1;
- normalized content, creator, trend, brief, provenance, and subscription
  resources;
- roadmap documents for MCP and Notion.

## Proposed scope

1. MCP Server exposing read-only Media Ops tools by default.
2. External Codex invocation and least-privilege credential workflow.
3. Notion API connection and explicit target-database mapping.
4. Verified Notion Webhook receiver with replay protection.
5. Agent execution records with inputs, scopes, outcome, evidence, and errors.
6. Confirmation mechanism for task/subscription write tools.
7. Integration audit trail, revocation, bounded retries, and operational docs.

Planned MCP tools:

```text
mediaops_search_contents
mediaops_get_content
mediaops_get_creator
mediaops_list_trends
mediaops_get_latest_brief
mediaops_create_crawl_task
mediaops_create_subscription
```

Write tools require separate scopes and confirmation. External OAuth, tokens,
webhook secrets, or new service authority require explicit user action.
