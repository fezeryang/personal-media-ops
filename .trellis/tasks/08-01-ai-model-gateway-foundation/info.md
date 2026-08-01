# Stage 8A technical design

## Data flow

```text
AI Model Center
  -> owner Session / Origin / CSRF API
  -> AIRepository + ProviderSecretCipher
  -> SQLite configuration and encrypted credentials

Debug / future AI feature
  -> ModelGateway resolves immutable route snapshot
  -> model/provider enabled and capability validation
  -> just-in-time secret decryption
  -> per-provider semaphore
  -> AnthropicCompatibleProvider or OpenAICompatibleProvider
  -> normalized response/stream
  -> invocation attempt + usage/cost snapshot
```

## Implemented backend modules

- `app/models/ai.py`: all internal and API DTOs.
- `app/repositories/ai.py`: configuration, health, invocation, and aggregate
  queries; no plaintext secret accessor.
- `app/security/provider_secrets.py`: AESGCM and master-key loader.
- `app/services/ai/providers/base.py`: provider interface, error mapping, SSE
  primitives.
- `app/services/ai/providers/anthropic.py` and `openai.py`: pure protocol
  conversion and HTTP calls.
- `app/services/ai/model_gateway.py`: route, retry/fallback, concurrency,
  invocation, and cost orchestration.
- `app/api/ai.py`: owner-only administration and debug API.

## Implemented frontend modules

- `src/api/ai.ts`: Zod contracts and API/SSE client.
- `src/pages/ai-model-center-page.tsx`: providers, independently selected
  capability tests, models, routes, usage, and bounded debug surface.

## Schema and deletion rules

- Foreign keys from secrets/models/health to provider use cascade only for
  records without history.
- Routes and invocations use restrictive references. API preflight provides a
  readable 409 before SQLite enforces it.
- One route row per role; route replacement is transactional.
- Invocation rows represent actual upstream attempts. A correlation ID groups
  retries and fallback. Prompts/outputs are never columns.

## Rollout order

1. Verify local quality gates and scan the worktree.
2. Push the reviewed commit; resolve exact `origin/main` target.
3. Run deployment dry-run with `--allow-migrations`.
4. Back up SQLite and record path/SHA-256.
5. Create/verify the non-overwriting host master key without printing it.
6. Build/test on the server, migrate to 0010, and activate via the restricted
   helper.
7. Verify migration, integrity, preserved counts, services, localhost/public
   composite health, frontend route, empty Model Center, secret response
   absence, and zero active crawler tasks.
8. Pause for the owner to enter one provider key in the web UI.
9. Resume real text/stream/tool verification, route setup, invocation audit,
   and final leakage scan.

## Rollback

Prefer Git revert or forward fix. The migration creates new isolated tables;
its reviewed downgrade may drop them only when explicitly invoked, but
production rollback should not downgrade or restore SQLite automatically.
Retain the pre-migration backup. Master-key deletion/replacement is never an
automatic rollback action.
