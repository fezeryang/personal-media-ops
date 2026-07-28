# Bug Analysis: production-only Bilibili and Kuaishou mode seams

## 1. Root Cause Category

- **Category**: B - Cross-Layer Contract and D - Test Coverage Gap.
- **Specific Cause**: Bilibili search persisted public AV identities while the
  pinned detail parser accepted BV only. Kuaishou runtime patches imported
  `KuaiShouCrawler`, while the pinned upstream class is
  `KuaishouCrawler`. Unit fixtures had validated arguments and pure helpers but
  had not imported these exact production seams.

## 2. Why Fixes Failed

1. Synthetic detail tests used a BV-shaped target and did not reuse a real
   search result's AV ID.
2. Kuaishou sanitizer tests never installed the creator/sub-comment runtime
   patch, so Python's case-sensitive import was not exercised.

## 3. Prevention Mechanisms

| Priority | Mechanism | Specific Action | Status |
| --- | --- | --- | --- |
| P0 | Architecture | Resolve Bilibili AV/BV identity in one Runner helper and keep API/Worker platform-neutral | DONE |
| P0 | Test coverage | Exercise numeric AV, AV URL, BV, BV URL, and the patched `aid` call | DONE |
| P0 | Test coverage | Assert the exact pinned Kuaishou crawler class used by both runtime patches | DONE |
| P1 | Production validation | Re-run Bilibili numeric detail and Kuaishou creator after deployment | DONE |
| P1 | Documentation | Record both fixed upstream seams in the crawler contract | DONE |

## 4. Systematic Expansion

- **Similar Issues**: Every Runner patch that imports an upstream class or
  converts a stored source identity must be checked against the pinned commit.
- **Design Improvement**: Source ID/URL conversion stays in Runner helpers;
  mode requests and Worker orchestration remain platform-neutral.
- **Process Improvement**: Real mode validation must start from IDs and URLs
  produced by a prior real task, not only hand-authored fixtures.

## 5. Knowledge Capture

- [x] Updated `.trellis/spec/backend/crawler-platforms.md`.
- [x] Added Runner unit tests for AV/BV identity and exact class naming.
- [x] Retained failed production tasks as evidence.
- [x] Record the successful Bilibili retry and accurate Kuaishou creator
  deferral in the stage-six report.

This repository does not contain `src/templates/markdown/spec/`, so there is no
local Trellis generator template to synchronize.
