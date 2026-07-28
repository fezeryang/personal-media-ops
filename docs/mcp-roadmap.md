# MCP roadmap

Stage seven does not deploy an MCP server. The next task,
`external-agent-mcp-and-notion`, will map the stable Agent Tool Service to MCP
without reading crawler JSONL or coupling to the React API.

Planned read-only tools:

```text
mediaops_search_contents
mediaops_get_content
mediaops_get_creator
mediaops_list_trends
mediaops_get_latest_brief
```

Planned write tools, disabled by default:

```text
mediaops_create_crawl_task
mediaops_create_subscription
```

Read tools will require least-privilege read scopes. Write tools require their
own `tasks:write` or `subscriptions:write` key plus an explicit confirmation
and an integration audit record. The MCP process must not receive browser
cookies, server paths, SSH authority, or unrestricted database access.

Target mapping:

```text
Agent Tool Service → REST API v1 → MCP tools → Codex
```
