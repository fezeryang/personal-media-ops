# Deterministic intelligence engine

Stage seven intelligence is rule-based and evidence-linked. Production does
not call an external model: `MEDIAOPS_AI_PROVIDER=disabled`.

## Metric snapshots

Every successful library ingestion preserves current content and creator
metrics in:

```text
content_metric_snapshots
creator_metric_snapshots
```

Missing source fields remain `null` and never overwrite a known value.
Identical snapshots for the same entity within 15 minutes are deduplicated.
Detail APIs load bounded history on demand and return absolute
`delta_from_previous` values. SQLite indexes are `(entity_id, captured_at)`.

## Trend formula (`rules-v1`)

For each real source keyword or subscription query, the engine compares a
current window to the immediately preceding equal window:

```text
volume_score         = clamp(current_volume × 10)
velocity_score       = clamp(max(current - previous, 0) / max(previous, 3) × 50)
cross_platform_score = clamp(platform_count / 3 × 100)
engagement_score     = clamp(max(metric_growth_ratio, 0) × 50)

score = 0.35 × volume
      + 0.30 × velocity
      + 0.20 × cross_platform
      + 0.15 × engagement
```

Every component is bounded to 0–100 and the result is deterministic. A signal
is `detected` only when the current window has at least three contents and the
current plus previous windows have at least five. Otherwise it is
`insufficient_data`, regardless of its numerical score. The signal stores
participating platforms, content IDs, formula version, component scores,
explanation, volumes, and threshold evidence.

## Brief generation

`BriefGenerator` is the extension contract.
`DeterministicBriefGenerator` is the production implementation.
`AIEnhancedBriefGenerator` exists only as a disabled seam and raises while the
provider is disabled.

A brief records one owner/timezone/window and versioned regeneration. Without
`regenerate=true`, the same window conflicts; regeneration supersedes the old
ready version and creates the next version. Sections can include:

- newly discovered contents from `first_collected_at`;
- calculated trend results;
- high-interaction contents ranked by available current metrics;
- watched-creator successful activity;
- favorited contents;
- recorded failed/partial subscription runs as data gaps.

Each item is explicitly typed `fact`, `calculation`, `rule`,
`insufficient_data`, or `unknown`, links content/trend evidence, and includes
source URLs where applicable. “No recorded failure” does not imply deferred
platforms were collected.
