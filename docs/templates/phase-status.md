# 阶段状态报告模板

> 状态必须按维度记录；不要用一个没有上下文的 `blocked` 覆盖其他已通过结果。

## Phase

```text
phase: <例如 8D>
task: <Trellis task name>
acceptance_scope: <本次实际范围>
last_updated: <UTC timestamp>
```

## Engineering and delivery status

```text
implementation_status: not_started
local_test_status: not_started
local_visual_status: not_started
release_candidate_status: not_started
deployment_status: not_started
production_smoke_status: not_started
production_business_status: not_started
user_product_review_status: not_started
```

Allowed values:

```text
not_started | in_progress | passed | failed | pending | not_applicable |
blocked_by_user_auth | blocked_by_platform | deployment_transport_failed |
awaiting_user_review
```

## Evidence

```text
implementation_evidence:
local_test_evidence:
local_visual_evidence:
release_commit:
release_candidate_manifest:
previous_production_commit:
backup_path_and_sha256:
deployment_evidence:
production_smoke_evidence:
production_business_evidence:
user_review_evidence:
```

## Review notes

```text
database_changed: yes | no
backend_changed: yes | no
frontend_changed: yes | no
worker_changed: yes | no
deployment_changed: yes | no
remaining_work:
user_action_required:
transport_or_platform_limits:
rollback_caution:
```

## Current 8D checkpoint example

```text
implementation_status: complete
local_test_status: passed
local_visual_status: awaiting_user_review
release_candidate_status: pending
deployment_status: deployment_transport_failed
production_smoke_status: pending
production_business_status: pending
user_product_review_status: awaiting_user_review
```

The example is a format illustration. Replace it with evidence from the active task; do not
copy it as a claim.
