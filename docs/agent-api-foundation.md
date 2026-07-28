# Agent API foundation

Stage six does not ship an MCP server. It establishes stable, read-only
library resources that a later Agent or MCP adapter can call without parsing
crawler JSONL or depending on frontend fields.

Proposed future tool mapping:

| Agent operation | Current HTTP foundation |
| --- | --- |
| `search_contents` | `GET /api/library/contents` |
| `get_content` | `GET /api/library/contents/{id}` |
| `get_creator` | `GET /api/library/creators/{id}` |
| `list_comments` | `GET /api/library/comments` |
| `get_source_provenance` | content/creator detail `tasks` plus source fields |

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

Subscriptions, scheduled collection, tags, favorites, metric snapshots,
creator monitoring, daily briefs, and trend analysis belong to
`intelligence-library-and-subscriptions`. They are not implemented by this
foundation.
