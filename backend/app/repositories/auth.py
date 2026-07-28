import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db import connect_database
from app.repositories.crawler_tasks import utc_now


def _parse_timestamp(value: str | None) -> datetime | None:
    if value is None:
        return None
    return datetime.fromisoformat(value).astimezone(UTC)


class AuthRepository:
    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    def owner_count(self) -> int:
        with connect_database(self.database_path) as connection:
            return int(
                connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            )

    def create_owner(self, *, username: str, password_hash: str) -> dict[str, Any]:
        now = utc_now()
        identifier = str(uuid4())
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, password_hash, is_active,
                    failed_login_count, locked_until, last_login_at,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, 1, 0, NULL, NULL, ?, ?)
                """,
                (identifier, username, password_hash, now, now),
            )
        owner = self.get_user(identifier)
        if owner is None:
            raise RuntimeError("created owner could not be read")
        return owner

    def get_user(self, user_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, is_active,
                       failed_login_count, locked_until, last_login_at,
                       created_at, updated_at
                FROM users WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_user_by_username(self, username: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, username, password_hash, is_active,
                       failed_login_count, locked_until, last_login_at,
                       created_at, updated_at
                FROM users WHERE username = ?
                """,
                (username,),
            ).fetchone()
        return dict(row) if row is not None else None

    def record_login_failure(
        self,
        *,
        user_id: str,
        failure_limit: int,
        lockout_seconds: int,
    ) -> tuple[int, str | None]:
        connection = connect_database(self.database_path)
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT failed_login_count FROM users WHERE id = ?",
                (user_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError("owner disappeared during login")
            failures = int(row["failed_login_count"]) + 1
            locked_until = None
            if failures >= failure_limit:
                locked_until = (
                    datetime.now(UTC) + timedelta(seconds=lockout_seconds)
                ).isoformat().replace("+00:00", "Z")
            connection.execute(
                """
                UPDATE users
                SET failed_login_count = ?, locked_until = ?, updated_at = ?
                WHERE id = ?
                """,
                (failures, locked_until, utc_now(), user_id),
            )
            connection.commit()
            return failures, locked_until
        finally:
            connection.close()

    def record_login_success(self, user_id: str) -> None:
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE users
                SET failed_login_count = 0, locked_until = NULL,
                    last_login_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (now, now, user_id),
            )

    def create_session(
        self,
        *,
        user_id: str,
        token_hash: str,
        csrf_token_hash: str,
        expires_at: str,
    ) -> dict[str, Any]:
        identifier = str(uuid4())
        now = utc_now()
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO sessions (
                    id, user_id, token_hash, csrf_token_hash, created_at,
                    expires_at, last_seen_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    identifier,
                    user_id,
                    token_hash,
                    csrf_token_hash,
                    now,
                    expires_at,
                    now,
                ),
            )
        session = self.get_session_by_hash(token_hash)
        if session is None:
            raise RuntimeError("created session could not be read")
        return session

    def get_session_by_hash(self, token_hash: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT s.id, s.user_id, s.token_hash, s.csrf_token_hash,
                       s.created_at, s.expires_at, s.last_seen_at, s.revoked_at,
                       u.username, u.is_active
                FROM sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                """,
                (token_hash,),
            ).fetchone()
        return dict(row) if row is not None else None

    def touch_session(self, session_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE sessions SET last_seen_at = ? WHERE id = ?",
                (utc_now(), session_id),
            )

    def rotate_csrf(self, session_id: str, csrf_token_hash: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sessions
                SET csrf_token_hash = ?, last_seen_at = ?
                WHERE id = ? AND revoked_at IS NULL
                """,
                (csrf_token_hash, utc_now(), session_id),
            )

    def revoke_session(self, session_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE id = ?
                """,
                (utc_now(), session_id),
            )

    def list_sessions(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                    SELECT id, created_at, expires_at, last_seen_at, revoked_at
                    FROM sessions
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (user_id,),
                ).fetchall()
            ]

    def revoke_user_session(self, *, session_id: str, user_id: str) -> bool:
        with connect_database(self.database_path) as connection:
            result = connection.execute(
                """
                UPDATE sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE id = ? AND user_id = ?
                """,
                (utc_now(), session_id, user_id),
            )
        return result.rowcount == 1

    def create_api_key(
        self,
        *,
        user_id: str,
        name: str,
        prefix: str,
        key_hash: str,
        scopes: Sequence[str],
        expires_at: str | None,
    ) -> dict[str, Any]:
        identifier = str(uuid4())
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO api_keys (
                    id, user_id, name, key_prefix, key_hash, scopes,
                    created_at, last_used_at, expires_at, revoked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL)
                """,
                (
                    identifier,
                    user_id,
                    name,
                    prefix,
                    key_hash,
                    json.dumps(sorted(set(scopes)), separators=(",", ":")),
                    utc_now(),
                    expires_at,
                ),
            )
        result = self.get_api_key(identifier)
        if result is None:
            raise RuntimeError("created API key could not be read")
        return result

    def get_api_key(self, key_id: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id, user_id, name, key_prefix, scopes, created_at,
                       last_used_at, expires_at, revoked_at
                FROM api_keys WHERE id = ?
                """,
                (key_id,),
            ).fetchone()
        return self._api_key_row(row)

    def get_api_key_by_hash(self, key_hash: str) -> dict[str, Any] | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT k.id, k.user_id, k.name, k.key_prefix, k.scopes,
                       k.created_at, k.last_used_at, k.expires_at, k.revoked_at,
                       u.username, u.is_active
                FROM api_keys k
                JOIN users u ON u.id = k.user_id
                WHERE k.key_hash = ?
                """,
                (key_hash,),
            ).fetchone()
        return self._api_key_row(row)

    def list_api_keys(self, user_id: str) -> list[dict[str, Any]]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, user_id, name, key_prefix, scopes, created_at,
                       last_used_at, expires_at, revoked_at
                FROM api_keys
                WHERE user_id = ?
                ORDER BY created_at DESC, id DESC
                """,
                (user_id,),
            ).fetchall()
        return [self._api_key_row(row) for row in rows if row is not None]

    @staticmethod
    def _api_key_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        try:
            parsed_scopes = json.loads(str(result["scopes"]))
        except json.JSONDecodeError as error:
            raise RuntimeError("API key contains invalid scopes") from error
        if not isinstance(parsed_scopes, list) or not all(
            isinstance(scope, str) for scope in parsed_scopes
        ):
            raise RuntimeError("API key contains invalid scopes")
        result["scopes"] = parsed_scopes
        return result

    def touch_api_key(self, key_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (utc_now(), key_id),
            )

    def revoke_api_key(self, *, key_id: str, user_id: str) -> bool:
        with connect_database(self.database_path) as connection:
            result = connection.execute(
                """
                UPDATE api_keys
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE id = ? AND user_id = ?
                """,
                (utc_now(), key_id, user_id),
            )
        return result.rowcount == 1

    @staticmethod
    def is_timestamp_active(
        *,
        expires_at: str | None,
        revoked_at: str | None,
    ) -> bool:
        if revoked_at is not None:
            return False
        expires = _parse_timestamp(expires_at)
        return expires is None or expires > datetime.now(UTC)
