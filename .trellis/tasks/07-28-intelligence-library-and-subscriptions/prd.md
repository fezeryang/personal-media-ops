# Intelligence library and subscriptions

## Status

Planning only. Do not implement until stage six is completed, production
validated, and this task is explicitly started.

## Goal

Build automation and intelligence workflows on top of the stable stage-six
library and provenance APIs without increasing crawler concurrency or
bypassing platform capability limits.

## Candidate scope

- keyword subscriptions with explicit platform/mode targets;
- bounded scheduled collection with overlap prevention;
- content, creator, and comment deduplication;
- user tags and favorites;
- content and creator metric snapshots for trend analysis;
- creator monitoring;
- daily brief generation from stored source records;
- transparent trend calculations with source provenance.

## Required discovery

- define subscription cadence, retry, pause, and retention semantics;
- decide which metrics need snapshots instead of current-value upserts;
- define timezone and daily-brief delivery boundaries;
- design SQLite-safe scheduling without Redis, Kafka, or Elasticsearch;
- define duplicate identity beyond platform source IDs;
- confirm privacy, rate, and request-volume limits per platform;
- define Agent read/write permissions separately from the read-only
  foundation.

## Non-goals

- automatic publishing;
- unbounded crawling or comments;
- proxy pools;
- multi-browser concurrency;
- a production MCP server before its authorization model is designed;
- claiming analysis that cannot be traced to stored source records.
