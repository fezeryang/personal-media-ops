import asyncio
import sys
from pathlib import Path

import pytest

from app.core.config import Settings
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.workers.crawler_worker import CrawlerWorker, WorkerAlreadyRunning, WorkerLock


def worker_settings(base: Settings, runner: Path) -> Settings:
    return Settings(
        frontend_origins=base.frontend_origins,
        database_path=base.database_path,
        mediacrawler_python=Path(sys.executable),
        mediacrawler_runner=runner,
        output_root=base.output_root,
        log_root=base.log_root,
        qrcode_root=base.qrcode_root,
        node_binary=None,
        node_bin_dir=base.node_bin_dir,
        crawler_poll_interval_seconds=0.02,
        enabled_platforms=base.enabled_platforms,
    )


def seed_task(
    repository: CrawlerTaskRepository,
    settings: Settings,
    keywords: str = "AI Agent",
    platform: str = "bili",
    requested_count: int = 2,
) -> dict[str, object]:
    task_id = repository.new_id()
    return repository.create(
        task_id=task_id,
        platform=platform,
        crawler_type="search",
        keywords=keywords,
        login_type="qrcode",
        requested_count=requested_count,
        output_dir=str(settings.output_root / "tasks" / task_id),
        log_path=str(settings.log_root / "crawler" / f"{task_id}.log"),
        qrcode_path=str(settings.qrcode_root / f"{task_id}.png"),
    )


def test_worker_updates_success_and_actual_count(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "success_runner.py"
    runner.write_text(
        """
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
args, _ = parser.parse_known_args()
output = Path(args.output_dir)
store_names = {"bili": "bilibili", "xhs": "xhs", "dy": "douyin"}
result_dir = output / store_names[args.platform] / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    '{"video_id": "1"}\\n{"video_id": "2"}\\n{"video_id": "3"}\\n',
    encoding="utf-8",
)
print("crawler completed", flush=True)
""".strip(),
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings)

    asyncio.run(CrawlerWorker(repository, settings).run_once())

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "succeeded"
    assert stored["actual_count"] == 2
    assert stored["pid"] is not None
    assert stored["finished_at"] is not None


def test_worker_records_nonzero_exit(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "failure_runner.py"
    runner.write_text(
        "import sys\nprint('runner failed', flush=True)\nsys.exit(7)\n",
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings)

    asyncio.run(CrawlerWorker(repository, settings).run_once())

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert "7" in str(stored["error_message"])


def test_worker_reports_waiting_login_then_resumes(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "login_runner.py"
    runner.write_text(
        """
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--qrcode-path", required=True)
parser.add_argument("--output-dir", required=True)
args, _ = parser.parse_known_args()
qrcode = Path(args.qrcode_path)
qrcode.parent.mkdir(parents=True, exist_ok=True)
qrcode.write_bytes(b"fake png")
print("QR code ready", flush=True)
continue_file = Path(args.output_dir) / "continue"
for _ in range(100):
    if continue_file.exists():
        break
    time.sleep(0.05)
print("Login successful then wait for redirect", flush=True)
""".strip(),
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings)

    async def run_and_observe() -> None:
        worker_task = asyncio.create_task(
            CrawlerWorker(repository, settings).run_once()
        )
        for _ in range(100):
            stored = repository.get(str(task["id"]))
            if stored and stored["status"] == "waiting_login":
                break
            await asyncio.sleep(0.01)
        else:
            pytest.fail("worker never exposed waiting_login")
        await asyncio.sleep(0.05)
        still_waiting = repository.get(str(task["id"]))
        assert still_waiting is not None
        assert still_waiting["status"] == "waiting_login"
        (settings.output_root / "tasks" / str(task["id"]) / "continue").touch()
        await worker_task

    asyncio.run(run_and_observe())

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "succeeded"


def test_worker_cancels_running_process(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "slow_runner.py"
    runner.write_text(
        """
import time
print("started", flush=True)
while True:
    time.sleep(0.1)
""".strip(),
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings)
    worker = CrawlerWorker(repository, settings, terminate_timeout_seconds=0.2)

    async def run_and_cancel() -> None:
        worker_task = asyncio.create_task(worker.run_once())
        for _ in range(100):
            stored = repository.get(str(task["id"]))
            if stored and stored["pid"]:
                break
            await asyncio.sleep(0.01)
        repository.request_cancel(str(task["id"]))
        await asyncio.wait_for(worker_task, timeout=3)

    asyncio.run(run_and_cancel())

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "cancelled"
    assert stored["cancel_requested"] is True


def test_second_worker_lock_is_rejected(test_settings: Settings) -> None:
    first = WorkerLock(test_settings.database_path)
    second = WorkerLock(test_settings.database_path)

    with first, pytest.raises(WorkerAlreadyRunning), second:
        pass


@pytest.mark.parametrize("platform", ["bili", "xhs", "dy"])
def test_worker_command_uses_only_fixed_executables_and_service_flags(
    test_settings: Settings,
    repository: CrawlerTaskRepository,
    platform: str,
) -> None:
    task = seed_task(
        repository,
        test_settings,
        keywords="--not-an-option",
        platform=platform,
    )
    worker = CrawlerWorker(repository, test_settings)
    output_dir = test_settings.output_root / "tasks" / str(task["id"])
    qrcode_path = test_settings.qrcode_root / f"{task['id']}.png"

    command = worker._build_command(task, output_dir, qrcode_path)

    assert command[:2] == [
        str(test_settings.mediacrawler_python),
        str(test_settings.mediacrawler_runner),
    ]
    assert command[command.index("--platform") + 1] == platform
    assert "--keywords=--not-an-option" in command
    assert command[command.index("--max-concurrency-num") + 1] == "1"
    assert command[command.index("--enable-comments") + 1] == "false"
    assert command[command.index("--enable-sub-comments") + 1] == "false"
    assert "--enable-proxy" not in command
