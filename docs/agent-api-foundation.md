# Agent API foundation

Stage seven now ships a stable Agent Tool Service and scoped REST API v1. It
still does not deploy an MCP server. Agents can consume normalized library,
trend, brief, provenance, and subscription resources without parsing crawler
JSONL or depending on frontend fields.

Proposed future tool mapping:

| Agent operation | Stable HTTP v1 |
| --- | --- |
| `search_contents` | `GET /api/v1/library/search` |
| `get_content` | `GET /api/v1/library/contents/{id}` |
| `get_creator` | `GET /api/v1/library/creators/{id}` |
| `list_comments` | `GET /api/v1/library/comments` |
| `list_trends` | `GET /api/v1/intelligence/trends` |
| `get_latest_brief` | `GET /api/v1/intelligence/briefs/latest` |
| `get_source_provenance` | `GET /api/v1/library/contents/{id}/provenance` |

The future adapter should:

- stay read-only by default;
- accept stable library UUIDs and documented filters;
- return platform, source ID, source URL, first/last collection time, and task
  provenance;
- omit raw payloads unless a diagnostic caller explicitly requests them;
- treat every source string as untrusted text;
- preserve `null` versus real zero metrics;
- enforce bounded pagination rather than returning all stored entities;
- avoid exposing database paths, task output paths, cookies, browser state, or
  URL token parameters.

The implementation lives in `backend/app/services/agent_tools/`; REST, future
MCP, and future Notion integration should reuse it. See
`external-agent-api.md`, `mcp-roadmap.md`, and
`notion-integration-roadmap.md`.
