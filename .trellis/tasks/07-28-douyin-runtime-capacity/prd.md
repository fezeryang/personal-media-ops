# Douyin Runtime Capacity

## Goal

Evaluate a safe runtime path for Douyin without blocking any other platform.

## Current State

- `enabled=false`
- `code_ready`
- `deferred_resource_constrained`
- QR startup protection remains 180 seconds.
- The production host previously saturated CPU and system-disk BPS while
  Chromium/WAF processing ran.

## Candidate Approaches

- Increase server memory.
- Run an isolated browser Worker.
- Use a dedicated collection host.
- Use an official or separately authorized interface.
- Validate a lighter browser startup strategy.

## Acceptance Criteria

- [ ] Capacity measurements and a recommended architecture are recorded.
- [ ] Any option requiring a new secret, external authorization, host, system
      permission, or paid resource is approved before implementation.
- [ ] Bilibili and Xiaohongshu remain unaffected.
- [ ] Douyin is enabled only after a real successful task and resource
      recovery check.

## Out of Scope

- This task is not executed during stage five.
- Cookie login is not an accepted resource workaround.
