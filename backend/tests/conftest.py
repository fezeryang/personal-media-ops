from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.auth import AuthRepository
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.security.passwords import hash_password
from tests.alembic_utils import run_alembic_command

TEST_OWNER_USERNAME = "test-owner"
TEST_OWNER_PASSWORD = "test-owner-password"


def authenticate_test_client(
    client: TestClient,
    settings: Settings,
) -> None:
    AuthRepository(settings.database_path).create_owner(
        username=TEST_OWNER_USERNAME,
        password_hash=hash_password(TEST_OWNER_PASSWORD),
    )
    login = client.post(
        "/api/auth/login",
        json={
            "username": TEST_OWNER_USERNAME,
            "password": TEST_OWNER_PASSWORD,
        },
        headers={"Origin": "http://testserver"},
    )
    assert login.status_code == 200
    client.headers.update(
        {
            "Origin": "http://testserver",
            "X-CSRF-Token": login.json()["csrf_token"],
        }
    )


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        frontend_origins=(),
        database_path=tmp_path / "mediaops.db",
        mediacrawler_python=Path("/fixed/python"),
        mediacrawler_runner=Path("/fixed/run_mediacrawler.py"),
        output_root=tmp_path / "output",
        log_root=tmp_path / "logs",
        qrcode_root=tmp_path / "qrcodes",
        node_binary=None,
        node_bin_dir=tmp_path / "node-bin",
        crawler_poll_interval_seconds=0.02,
        douyin_qrcode_startup_timeout_seconds=180,
        enabled_platforms=("bili", "xhs"),
        model_gateway_master_key_path=tmp_path / "secrets" / "model-gateway.key",
    )


@pytest.fixture
def repository(test_settings: Settings) -> CrawlerTaskRepository:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    repo = CrawlerTaskRepository(test_settings.database_path)
    repo.initialize()
    return repo


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    test_settings.model_gateway_master_key_path.parent.mkdir(mode=0o700)
    test_settings.model_gateway_master_key_path.write_bytes(b"t" * 32)
    test_settings.model_gateway_master_key_path.chmod(0o600)
    with TestClient(create_app(test_settings)) as test_client:
        authenticate_test_client(test_client, test_settings)
        yield test_client


@pytest.fixture
def owner_id(client: TestClient) -> str:
    owner = AuthRepository(
        client.app.state.settings.database_path
    ).get_user_by_username(TEST_OWNER_USERNAME)
    assert owner is not None
    return str(owner["id"])
