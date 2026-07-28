import pytest
from fastapi.testclient import TestClient

from app import cli
from app.main import create_app
from app.repositories.auth import AuthRepository
from app.security.passwords import hash_password, verify_password
from tests.alembic_utils import run_alembic_command

OWNER_USERNAME = "owner"
OWNER_PASSWORD = "correct horse battery staple"


def _create_owner(client: TestClient) -> None:
    repository = AuthRepository(client.app.state.settings.database_path)
    repository.create_owner(
        username=OWNER_USERNAME,
        password_hash=hash_password(OWNER_PASSWORD),
    )


def _login(client: TestClient) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
        headers={"Origin": "http://testserver"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == OWNER_USERNAME
    assert payload["csrf_token"]
    assert "mediaops_session=" in response.headers["set-cookie"]
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    return str(payload["csrf_token"])


def test_password_hash_uses_argon2id_and_verifies() -> None:
    encoded = hash_password(OWNER_PASSWORD)

    assert encoded.startswith("$argon2id$")
    assert OWNER_PASSWORD not in encoded
    assert verify_password(OWNER_PASSWORD, encoded) is True
    assert verify_password("wrong password", encoded) is False


def test_create_owner_cli_reads_password_interactively_and_hashes_it(
    test_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    monkeypatch.setattr(cli, "settings", test_settings)
    answers = iter([OWNER_PASSWORD, OWNER_PASSWORD])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _: next(answers))

    assert cli.create_owner(OWNER_USERNAME) == 0
    owner = AuthRepository(test_settings.database_path).get_user_by_username(
        OWNER_USERNAME
    )
    assert owner is not None
    assert verify_password(OWNER_PASSWORD, str(owner["password_hash"]))
    assert OWNER_PASSWORD.encode() not in test_settings.database_path.read_bytes()


def test_protected_api_requires_authentication(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with TestClient(create_app(test_settings)) as client:
        response = client.get("/api/library/stats")

    assert response.status_code == 401
    assert response.json()["detail"] == "Authentication required"


def test_login_session_csrf_and_logout(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with TestClient(create_app(test_settings)) as client:
        _create_owner(client)
        csrf_token = _login(client)

        session = client.get("/api/auth/session")
        assert session.status_code == 200
        assert session.json()["authenticated"] is True
        assert session.json()["csrf_token"]
        csrf_token = str(session.json()["csrf_token"])

        missing_csrf = client.post(
            "/api/crawler/tasks",
            json={
                "platform": "bili",
                "mode": "search",
                "keywords": "AI Agent",
                "requested_count": 1,
            },
            headers={"Origin": "http://testserver"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["detail"] == "CSRF validation failed"

        created = client.post(
            "/api/crawler/tasks",
            json={
                "platform": "bili",
                "mode": "search",
                "keywords": "AI Agent",
                "requested_count": 1,
            },
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf_token,
            },
        )
        assert created.status_code == 201

        logout = client.post(
            "/api/auth/logout",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": csrf_token,
            },
        )
        assert logout.status_code == 204
        assert client.get("/api/library/stats").status_code == 401
        assert client.get("/api/auth/session").json() == {
            "authenticated": False,
            "user": None,
            "csrf_token": None,
        }


def test_owner_can_list_and_revoke_another_session(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with (
        TestClient(create_app(test_settings)) as first,
        TestClient(create_app(test_settings)) as second,
    ):
        _create_owner(first)
        first_csrf = _login(first)
        _login(second)
        sessions = first.get("/api/auth/sessions")
        assert sessions.status_code == 200
        other = next(
            item for item in sessions.json() if item["current"] is False
        )

        revoked = first.delete(
            f"/api/auth/sessions/{other['id']}",
            headers={
                "Origin": "http://testserver",
                "X-CSRF-Token": first_csrf,
            },
        )
        assert revoked.status_code == 204
        assert second.get("/api/library/stats").status_code == 401


def test_login_failure_limit_is_persisted(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with TestClient(create_app(test_settings)) as first_client:
        _create_owner(first_client)
        for _ in range(test_settings.login_failure_limit):
            response = first_client.post(
                "/api/auth/login",
                json={"username": OWNER_USERNAME, "password": "wrong"},
                headers={"Origin": "http://testserver"},
            )
        assert response.status_code == 429

    with TestClient(create_app(test_settings)) as restarted_client:
        still_locked = restarted_client.post(
            "/api/auth/login",
            json={"username": OWNER_USERNAME, "password": OWNER_PASSWORD},
            headers={"Origin": "http://testserver"},
        )
        assert still_locked.status_code == 429
        assert still_locked.headers["retry-after"]


def test_api_key_scope_one_time_display_and_revocation(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with TestClient(create_app(test_settings)) as client:
        _create_owner(client)
        csrf_token = _login(client)
        headers = {
            "Origin": "http://testserver",
            "X-CSRF-Token": csrf_token,
        }

        created = client.post(
            "/api/auth/api-keys",
            json={
                "name": "read-only test",
                "scopes": ["library:read", "intelligence:read"],
            },
            headers=headers,
        )
        assert created.status_code == 201
        created_payload = created.json()
        full_key = created_payload.pop("api_key")
        assert full_key.startswith(
            f"pmo_{created_payload['key']['prefix']}_"
        )

        listed = client.get("/api/auth/api-keys")
        assert listed.status_code == 200
        assert "api_key" not in listed.text
        assert full_key not in listed.text
        assert "key_hash" not in listed.text

        api_headers = {"X-API-Key": full_key}
        assert client.get("/api/library/stats", headers=api_headers).status_code == 200
        assert (
            client.get("/api/crawler/tasks", headers=api_headers).status_code
            == 403
        )

        revoked = client.delete(
            f"/api/auth/api-keys/{created_payload['key']['id']}",
            headers=headers,
        )
        assert revoked.status_code == 204
        assert (
            client.get("/api/library/stats", headers=api_headers).status_code
            == 401
        )
