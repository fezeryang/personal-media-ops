from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.repositories.crawler_tasks import CrawlerTaskRepository


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
    )


@pytest.fixture
def repository(test_settings: Settings) -> CrawlerTaskRepository:
    repo = CrawlerTaskRepository(test_settings.database_path)
    repo.initialize()
    return repo


@pytest.fixture
def client(test_settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(test_settings)) as test_client:
        yield test_client
