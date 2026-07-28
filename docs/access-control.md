# Access control

Personal Media Ops uses application-layer, single-owner access control. It does
not offer public registration and does not depend on Cloudflare Access for its
primary authorization boundary.

## Owner initialization

After the database is migrated to the current Alembic head, create the owner
from an interactive terminal:

```bash
cd backend
uv run python -m app.cli create-owner --username owner
```

The command reads the password twice with `getpass`; there is no password CLI
argument or environment-variable fallback. Passwords require at least 12
characters and are stored as Argon2id hashes through `pwdlib`. The default
account limit is three and can be reduced with
`MEDIAOPS_MAX_OWNER_ACCOUNTS`.

## Browser sessions and CSRF

`POST /api/auth/login` returns a CSRF token and sets an opaque session token in
the `mediaops_session` cookie. The database stores SHA-256 hashes of the
cryptographically random session and CSRF tokens, never the tokens themselves.
Production cookies are `HttpOnly`, `Secure`, `SameSite=Strict`, and scoped to
`/`. The React application keeps the CSRF token in memory, never
`localStorage`.

Unsafe browser requests require all of:

1. an active, non-expired session;
2. an allowed same-origin `Origin` or `Referer`;
3. the current `X-CSRF-Token`.

`GET /api/auth/session` restores the session and rotates its CSRF token.
`POST /api/auth/logout` revokes the database session before deleting the
cookie. `GET /api/auth/sessions` lists the owner's sessions without returning
token material, and `DELETE /api/auth/sessions/{id}` revokes another session.
Five failed password attempts lock the owner account for 15 minutes by
default. Invalid credentials share the same generic error message.

## API keys

External callers authenticate with `X-API-Key`. A key has the shape
`pmo_<prefix>_<secret>`. Only the SHA-256 hash and eight-character prefix are
stored. The full key is returned once at creation and cannot be read again.
Keys have names, created/last-used/expiry timestamps, revocation, and these
scopes:

```text
library:read
intelligence:read
tasks:read
tasks:write
subscriptions:read
subscriptions:write
admin
```

`admin` satisfies all scopes. Browser sessions and external keys are separate
paths: owner-only operations such as key creation require a browser session.
Logs and normal API responses must never contain full keys, passwords, session
tokens, or CSRF tokens.

## Endpoint boundary

`/api/health`, `/api/auth/login`, and `/api/auth/session` remain anonymous.
All crawler, library, organization, subscription, watchlist, intelligence, and
v1 Agent endpoints require a session or matching API-key scope. Existing
systemd, Nginx localhost health checks, and the release helper continue to use
the public health endpoint.
