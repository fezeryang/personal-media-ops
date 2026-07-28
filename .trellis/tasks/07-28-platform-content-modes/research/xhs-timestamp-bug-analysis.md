# Bug Analysis: Xiaohongshu millisecond timestamp broke library ingestion

## 1. Root Cause Category

- **Category**: E - Implicit Assumption, with a cross-layer contract gap.
- **Specific Cause**: Adapter normalization accepted every numeric timestamp as
  Unix seconds, while Xiaohongshu emits milliseconds. The library repository
  correctly expected seconds and `datetime.fromtimestamp` rejected the
  resulting year 57413. Existing tests had encoded the upstream millisecond
  value as the expected normalized value, so the assumption survived the first
  implementation.

## 2. Why Fixes Failed

1. The initial unit tests checked field extraction but did not test the
   Adapter-to-persistence time contract.
2. The pre-production suite used synthetic second-based library entities, so
   it did not exercise a real Xiaohongshu millisecond payload through the
   repository.

## 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
| --- | --- | --- | --- |
| P0 | Architecture | Normalize all numeric platform timestamps to bounded Unix seconds in the shared Adapter helper | DONE |
| P0 | Test coverage | Cover seconds, milliseconds, microseconds, nanoseconds, and the supported upper bound | DONE |
| P0 | Platform regression | Assert the Xiaohongshu fixture persists a seconds value | DONE |
| P1 | Documentation | Record the timestamp unit contract in the crawler platform spec | DONE |
| P1 | Production validation | Re-run the failed Xiaohongshu search and confirm library provenance | TODO |

## 4. Systematic Expansion

- **Similar Issues**: Every content and comment Adapter shares the timestamp
  helper, so a central fix protects all seven platforms and all entity modes.
- **Design Improvement**: The normalized model owns one epoch unit; platform
  unit differences never cross the Adapter boundary.
- **Process Improvement**: Production mode verification must confirm entity
  persistence and provenance, not only a crawler exit code and JSONL count.

## 5. Knowledge Capture

- [x] Updated `.trellis/spec/backend/crawler-platforms.md`.
- [x] Added cross-platform numeric timestamp regression cases.
- [x] Retained the failed production task as evidence.
- [ ] Record the successful Xiaohongshu retry task in the stage-six report.

This repository does not contain the Trellis generator source directory
`src/templates/markdown/spec/`, so there is no local template copy to sync.
