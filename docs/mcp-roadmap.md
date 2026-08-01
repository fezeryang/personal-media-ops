# MCP roadmap

MCP is deferred after the product direction change on 2026-08-01. The product
is prioritizing its built-in AI Runtime and unified Model Gateway in stage 8A.
The historical `external-agent-mcp-and-notion` plan remains preserved but is
not the active development line. A later external-integration phase may map the
stable Agent Tool Service to MCP without reading crawler JSONL or coupling to
the React API.

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
