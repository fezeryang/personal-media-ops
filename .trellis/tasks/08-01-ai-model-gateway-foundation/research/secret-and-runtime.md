# Secret and runtime research

## AES-GCM

The official `pyca/cryptography` AESGCM documentation supports 128-, 192-, and
256-bit keys, recommends unique 96-bit nonces, appends a 128-bit authentication
tag to ciphertext, authenticates optional associated data, and raises
`InvalidTag` if ciphertext, nonce, associated data, or key is wrong.

Stage 8A will use:

- a random 32-byte (AES-256) master key;
- a random 12-byte nonce for every provider-secret write;
- associated data containing a stable format/version, provider ID, and
  `key_version`;
- binary ciphertext and nonce in SQLite;
- fail-closed decryption with no distinction exposed between tampering and the
  wrong master key.

The master key path is operational state outside Git and SQLite. The database
backup deliberately excludes it, as required. Loss of the key makes provider
credentials unrecoverable but does not corrupt other product data; the owner
can replace stored API keys after a forward repair.

## Production key creation

The production data root is owned by `mediaops`, so root is not expected to be
required. A reviewed script can:

1. require the fixed `/var/lib/mediaops/secrets` and fixed key path;
2. create the directory with `0700` if absent;
3. create exactly 32 random bytes under `umask 077` only when the file is
   absent;
4. set/verify file mode `0600` and directory mode `0700`;
5. print only path-independent status and permission facts, never bytes,
   digests, base64, or other derived secret material.

It must abort on an existing non-regular file, unexpected ownership, wrong
length, or inability to enforce permissions. It must never overwrite an
existing key. If production ownership prevents the operation, that is the
explicit pause boundary for a narrowly reviewed root-helper addition.

## Async runtime

- Use one official `httpx.AsyncClient` for the FastAPI application lifespan
  with explicit `Limits`, connect/read/write/pool timeouts, redirects disabled,
  and environment proxy inheritance disabled for predictable server behavior.
- Per-provider `asyncio.Semaphore` instances enforce database-configured
  concurrency without changing crawler concurrency.
- Provider adapters accept an async client/transport and decrypted credential;
  they know no database or FastAPI response types.
- Streaming uses the response context manager so disconnect, cancellation,
  parsing error, and normal completion all close the socket.
- Gateway catches and records provider failures but re-raises
  `asyncio.CancelledError`; cancellation is not silently retried.
- Retry sleeps are bounded and cancellation-aware. No infinite retry or
  cross-provider loop exists.

## Repository observations

- The backend currently declares `httpx2` in the dev group, and the current
  FastAPI/Starlette TestClient explicitly expects that development transport.
  Stage 8A retains it for tests and adds official `httpx` as a separate
  production dependency for the gateway; application code imports only
  `httpx`.
- Existing repositories use direct parameterized SQLite access and UTC ISO
  strings. The AI repository should follow that convention instead of adding
  an ORM layer.
- Existing owner security dependencies enforce Session on reads and
  Origin+CSRF on writes. Reuse them so Model Center does not gain a parallel
  authorization scheme.
- Existing deployment is marker-based and migration-gated. Key initialization
  becomes a marker-tracked, non-overwriting stage before service activation;
  the database backup continues to include SQLite only.
