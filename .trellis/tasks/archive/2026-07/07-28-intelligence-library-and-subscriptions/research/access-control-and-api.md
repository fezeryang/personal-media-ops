# Access control and Agent API research

## Sources

- FastAPI response-cookie reference and advanced response-cookie guide:
  <https://fastapi.tiangolo.com/reference/response/> and
  <https://fastapi.tiangolo.com/advanced/response-cookies/>.
- FastAPI security reference for `APIKeyHeader`/`APIKeyCookie` and dependency
  integration with OpenAPI:
  <https://fastapi.tiangolo.com/reference/security/>.
- FastAPI current password-hashing tutorial, which uses
  `pwdlib.PasswordHash.recommended()` and Argon2:
  <https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/>.
- Repository contracts:
  `backend/app/main.py`, `backend/app/models/`, `backend/app/api/`,
  `frontend/src/api/client.ts`, and `docs/api-contract.md`.

## Compared approaches

### Signed stateless JWT in local browser storage

- Requires a signing secret and rotation/revocation strategy.
- Browser storage would violate the explicit no-localStorage requirement.
- Immediate logout/revocation is harder and offers no benefit for one owner.

### Signed JWT in an HttpOnly cookie

- Avoids localStorage but still needs a production signing secret and a
  revocation store for the required immediate logout/API administration.
- Adds token claims/rotation complexity without removing database lookups.

### Opaque server-side session (selected)

- A random token is sent only in an HttpOnly/Secure/SameSite cookie and a hash
  is persisted with the user, expiry, revocation, and last-seen timestamps.
- Immediate logout/revocation is a single SQLite update.
- No signing key or new production secret is required.
- A separate synchronizer CSRF value is stored as a hash on the same session;
  the frontend keeps its plain value in memory and sends it only on unsafe
  same-origin requests.

## Password and login decision

- Add `pwdlib[argon2]` and call `PasswordHash.recommended()`, which currently
  produces Argon2id hashes.
- Run a dummy Argon2 verification when the username does not exist to reduce
  account-existence timing differences.
- Persist a bounded failure counter and `locked_until`, reset both after a
  successful login, and return a uniform `401 invalid_credentials`.
- The CLI uses `getpass` twice and accepts no command-line password option.

## API-key decision

- Format: `pmo_<8-char-prefix>_<random-secret>`.
- Persist the prefix, SHA-256 hash of the entire high-entropy key, name, JSON
  scopes, created/last-used/expiry/revocation timestamps, and owner ID.
- Return the full key only from create. Listing never selects the hash or full
  value; logs identify only the prefix.
- Use `X-API-Key` through FastAPI `APIKeyHeader` so the OpenAPI security scheme
  is explicit. Browser sessions and external keys remain different paths.

## Route boundary

- Anonymous: `/api/health`, login, and session-status/bootstrap behavior.
- Owner session: all frontend reads/writes and API-key administration.
- API key: only routes that declare one or more documented scopes.
- Session-backed unsafe methods additionally require same-origin
  `Origin`/`Referer` validation and `X-CSRF-Token`.
- Agent v1 returns a stable envelope/error schema and omits raw payloads,
  filesystem paths, log paths, Cookies, tokens, and PIDs.
