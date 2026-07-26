# Bug Analysis: FastAPI Tests Hung in the Managed Sandbox

## 1. Root Cause Category

- **Category**: E — Implicit assumption
- **Specific cause**: The managed execution sandbox blocked the asyncio
  cross-thread self-pipe wakeup used by AnyIO for synchronous FastAPI routes.
  Application code and dependencies were healthy; the same minimal
  `call_soon_threadsafe()` probe passed outside the sandbox.

## 2. Why Earlier Fixes Failed

1. Replacing Starlette `TestClient`: changed the HTTP client but still reached
   the same AnyIO worker-thread boundary.
2. Reinstalling/pinning AnyIO and greenlet: altered dependencies without
   testing the lower-level event-loop wakeup assumption.
3. Isolating Alembic imports: reduced coupling but did not address the
   environment-level wakeup failure.

## 3. Prevention Mechanisms

| Priority | Mechanism | Specific action | Status |
| --- | --- | --- | --- |
| P0 | Diagnostic | Run a minimal `call_soon_threadsafe()` probe | Done |
| P0 | Verification | Compare the probe inside/outside the sandbox | Done |
| P1 | Architecture | Keep standard FastAPI `TestClient` | Done |
| P1 | Documentation | Record the sandbox diagnostic in backend specs | Done |
| P1 | Test coverage | Run unchanged full pytest outside the sandbox | Done |

## 4. Systematic Expansion

- **Similar issues**: Any test using AnyIO worker threads can show the same
  false deadlock.
- **Design improvement**: Keep migrations explicit and runtime checks
  lightweight, but do not invent custom clients for environment failures.
- **Process improvement**: Reduce a hang to a runtime primitive before changing
  application or dependency layers.

## 5. Knowledge Capture

- [x] Updated backend quality guidelines.
- [x] Updated the cross-layer thinking guide.
- [x] Restored the standard FastAPI test client.
- [x] Verified focused and full suites outside the restricted sandbox.
