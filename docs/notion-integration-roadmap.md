# Notion integration roadmap

Notion is not connected in stage seven. No OAuth app, token, database ID,
webhook, or synthetic synchronization UI is installed.

The next task, `external-agent-mcp-and-notion`, may add:

1. an explicitly authorized Notion OAuth/token flow;
2. a user-selected target database and reviewed property mapping;
3. idempotent export of briefs, saved contents, tags, and provenance links;
4. webhook verification, replay protection, and bounded retries;
5. an integration audit log and per-action result;
6. confirmation for writes back into Personal Media Ops.

The default direction should be read-only from Media Ops to Notion. Notion
must receive normalized fields and source links, not raw payload, credentials,
internal paths, or browser state. Revoking the grant must stop all future
syncs without deleting local intelligence data.

Target mapping:

```text
Agent Tool Service → REST API v1 → Notion API / Webhook
```
