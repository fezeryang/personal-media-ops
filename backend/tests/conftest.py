from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.crawler_tasks import CrawlerTaskRepository
from tests.alembic_utils import run_alembic_command


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
        enabled_platforms=("bili", "xhs", "dy"),
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
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
