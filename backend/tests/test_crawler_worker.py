import asyncio
import os
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.config import Settings
from app.crawler.adapters import DouyinAdapter
from app.crawler.registry import CrawlerPlatformRegistry, platform_registry
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.library import LibraryRepository
from app.workers.crawler_worker import (
    STREAM_READER_LIMIT_BYTES,
    CrawlerWorker,
    WorkerAlreadyRunning,
    WorkerLock,
    redact_sensitive_log_text,
)


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
        douyin_qrcode_startup_timeout_seconds=(
            base.douyin_qrcode_startup_timeout_seconds
        ),
        crawler_login_timeout_seconds=base.crawler_login_timeout_seconds,
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


class RuntimeEnabledDouyinAdapter(DouyinAdapter):
    def __init__(self) -> None:
        super().__init__()
        object.__setattr__(
            self,
            "mode_statuses",
            {**self.mode_statuses, "search": "code_ready"},
        )


def registry_with_douyin_search_enabled() -> CrawlerPlatformRegistry:
    adapters = []
    for platform in ("bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks"):
        adapter = (
            RuntimeEnabledDouyinAdapter()
            if platform == "dy"
            else platform_registry.get(platform)
        )
        adapters.append(adapter)
    return CrawlerPlatformRegistry(adapters)


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


def test_worker_uses_mapping_count_from_ingestion_result(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "research_success_runner.py"
    runner.write_text(
        """
from pathlib import Path

result_dir = Path(__import__("sys").argv[__import__("sys").argv.index("--output-dir") + 1])
result_dir = result_dir / "bilibili" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    '{"video_id": "1"}\\n',
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings, requested_count=1)
    library = LibraryRepository(settings.database_path)
    research = Mock()
    worker = CrawlerWorker(
        repository,
        settings,
        library_repository=library,
        research_repository=research,
    )

    asyncio.run(worker.run_once())

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "succeeded"
    research.record_crawl_completion.assert_called_once_with(
        str(task["id"]),
        succeeded=True,
        new_content_count=1,
        existing_content_count=0,
        updated_content_count=0,
        result_count=1,
    )


def test_worker_redacts_sensitive_assignments_from_subprocess_logs(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "sensitive_log_runner.py"
    runner.write_text(
        """
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
args, _ = parser.parse_known_args()
result_dir = Path(args.output_dir) / "bilibili" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    '{"video_id": "1"}\\n',
    encoding="utf-8",
)
print(
    "url=https://example.test/?xsec_token=private-value&xsec_source=feed "
    "cookie:browser-secret",
    flush=True,
)
""".strip(),
        encoding="utf-8",
    )
    settings = worker_settings(test_settings, runner)
    task = seed_task(repository, settings, requested_count=1)

    asyncio.run(CrawlerWorker(repository, settings).run_once())

    log = (
        settings.log_root / "crawler" / f"{task['id']}.log"
    ).read_text(encoding="utf-8")
    assert "private-value" not in log
    assert "browser-secret" not in log
    assert "xsec_token=[REDACTED]" in log
    assert "cookie:[REDACTED]" in log


def test_sensitive_log_redaction_preserves_non_sensitive_text() -> None:
    assert redact_sensitive_log_text(
        "Existing login ready; xsec_source=feed"
    ) == "Existing login ready; xsec_source=feed"
    assert redact_sensitive_log_text(
        "cookie='first=one; second=two'"
    ) == "cookie=[REDACTED]"
    assert "private-value" not in redact_sensitive_log_text(
        "Search response: {'xsec_token': 'private-value'}"
    )
    assert "private-value" not in redact_sensitive_log_text(
        'Search response: {"access_token": "private-value"}'
    )


def test_worker_survives_stdout_line_beyond_stream_limit(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    # Beyond twice the stream limit: draining must iterate through the
    # reader's flow-control pause/resume, not just a single oversized chunk.
    oversized_length = 2 * STREAM_READER_LIMIT_BYTES + 4096
    runner = tmp_path / "oversized_runner.py"
    runner.write_text(
        f"""
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
args, _ = parser.parse_known_args()
output = Path(args.output_dir)
result_dir = output / "bilibili" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    '{{"video_id": "1"}}\\n{{"video_id": "2"}}\\n{{"video_id": "3"}}\\n',
    encoding="utf-8",
)
print("x" * {oversized_length}, flush=True)
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
    log_data = (settings.log_root / "crawler" / f"{task['id']}.log").read_bytes()
    # Exact count: a faulty drain that loses or duplicates buffered bytes
    # must fail, not just one that truncates.
    assert log_data.count(b"x") == oversized_length
    assert b"crawler completed" in log_data


def test_worker_terminates_subprocess_when_streaming_raises(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
    monkeypatch: pytest.MonkeyPatch,
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

    async def exploding_stream(
        self: CrawlerWorker,
        *args: object,
        **kwargs: object,
    ) -> bool:
        raise RuntimeError("stream boom")

    terminated_pids: list[int] = []
    original_terminate = CrawlerWorker._terminate_process

    async def recording_terminate(
        self: CrawlerWorker,
        process: asyncio.subprocess.Process,
    ) -> None:
        terminated_pids.append(process.pid)
        await original_terminate(self, process)

    monkeypatch.setattr(CrawlerWorker, "_stream_process", exploding_stream)
    monkeypatch.setattr(CrawlerWorker, "_terminate_process", recording_terminate)
    worker = CrawlerWorker(repository, settings, terminate_timeout_seconds=0.5)

    asyncio.run(asyncio.wait_for(worker.run_once(), timeout=5))

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert "stream boom" in str(stored["error_message"])
    assert terminated_pids == [stored["pid"]]
    with pytest.raises(ProcessLookupError):
        os.kill(int(stored["pid"]), 0)


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
    assert "runner failed" in str(stored["error_message"])


def test_worker_reports_waiting_login_then_resumes(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "login_runner.py"
    runner.write_text(
        """
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--qrcode-path", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
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
result_dir = Path(args.output_dir) / "bilibili" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    json.dumps({"video_id": "1"}) + "\\n",
    encoding="utf-8",
)
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


def test_worker_times_out_after_qrcode_when_platform_verification_stalls(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "stalled_login_runner.py"
    runner.write_text(
        """
import argparse
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--qrcode-path", required=True)
args, _ = parser.parse_known_args()
qrcode = Path(args.qrcode_path)
qrcode.parent.mkdir(parents=True, exist_ok=True)
qrcode.write_bytes(b"fake png")
print("QR code ready", flush=True)
while True:
    time.sleep(0.1)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        crawler_login_timeout_seconds=0.05,
    )
    task = seed_task(repository, settings)

    asyncio.run(
        asyncio.wait_for(
            CrawlerWorker(
                repository,
                settings,
                terminate_timeout_seconds=0.2,
            ).run_once(),
            timeout=3,
        )
    )

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert "login timed out after 0.05 seconds" in str(stored["error_message"])
    assert "platform verification" in str(stored["error_message"])
    with pytest.raises(ProcessLookupError):
        os.kill(int(stored["pid"]), 0)


def test_worker_times_out_douyin_before_qrcode_is_ready(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "silent_runner.py"
    runner.write_text(
        """
import time
while True:
    time.sleep(0.1)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        douyin_qrcode_startup_timeout_seconds=0.05,
        enabled_platforms=("bili", "xhs", "dy"),
    )
    task = seed_task(repository, settings, platform="dy")
    worker = CrawlerWorker(
        repository,
        settings,
        terminate_timeout_seconds=0.2,
        registry=registry_with_douyin_search_enabled(),
    )

    asyncio.run(asyncio.wait_for(worker.run_once(), timeout=3))

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert "QR-code startup timed out after 0.05 seconds" in str(
        stored["error_message"]
    )
    with pytest.raises(ProcessLookupError):
        os.kill(int(stored["pid"]), 0)


def test_worker_stops_douyin_startup_timeout_after_qrcode_is_ready(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "delayed_login_runner.py"
    runner.write_text(
        """
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--qrcode-path", required=True)
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
args, _ = parser.parse_known_args()
qrcode = Path(args.qrcode_path)
qrcode.parent.mkdir(parents=True, exist_ok=True)
qrcode.write_bytes(b"fake png")
time.sleep(0.3)
print("Login successful then wait for redirect", flush=True)
result_dir = Path(args.output_dir) / "douyin" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    json.dumps({"aweme_id": "1"}) + "\\n",
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        douyin_qrcode_startup_timeout_seconds=0.2,
        enabled_platforms=("bili", "xhs", "dy"),
    )
    task = seed_task(repository, settings, platform="dy")

    asyncio.run(
        asyncio.wait_for(
            CrawlerWorker(
                repository,
                settings,
                registry=registry_with_douyin_search_enabled(),
            ).run_once(),
            timeout=3,
        )
    )

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "succeeded"


def test_worker_stops_startup_timeout_after_persisted_login_is_detected(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "persisted_login_runner.py"
    runner.write_text(
        """
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
args, _ = parser.parse_known_args()
print("[MediaOps] Existing login state ready: dy", flush=True)
time.sleep(0.3)
result_dir = Path(args.output_dir) / "douyin" / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    json.dumps({"aweme_id": "1"}) + "\\n",
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        douyin_qrcode_startup_timeout_seconds=0.2,
        enabled_platforms=("bili", "xhs", "dy"),
    )
    task = seed_task(repository, settings, platform="dy")

    asyncio.run(
        asyncio.wait_for(
            CrawlerWorker(
                repository,
                settings,
                registry=registry_with_douyin_search_enabled(),
            ).run_once(),
            timeout=3,
        )
    )

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "succeeded"


def test_worker_terminates_when_login_requires_manual_captcha(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
) -> None:
    runner = tmp_path / "captcha_runner.py"
    runner.write_text(
        """
import time
print("平台需要验证码后继续", flush=True)
while True:
    time.sleep(0.1)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        enabled_platforms=("bili", "xhs", "zhihu"),
    )
    task = seed_task(repository, settings, platform="zhihu")

    asyncio.run(
        asyncio.wait_for(
            CrawlerWorker(
                repository,
                settings,
                terminate_timeout_seconds=0.2,
            ).run_once(),
            timeout=3,
        )
    )

    stored = repository.get(str(task["id"]))
    assert stored is not None
    assert stored["status"] == "failed"
    assert "manual verification" in str(stored["error_message"])
    with pytest.raises(ProcessLookupError):
        os.kill(int(stored["pid"]), 0)


@pytest.mark.parametrize("platform", ["bili", "xhs"])
def test_worker_does_not_apply_douyin_startup_timeout_to_other_platforms(
    tmp_path: Path,
    test_settings: Settings,
    repository: CrawlerTaskRepository,
    platform: str,
) -> None:
    runner = tmp_path / f"{platform}_slow_start_runner.py"
    runner.write_text(
        """
import argparse
import json
import time
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--output-dir", required=True)
parser.add_argument("--platform", required=True)
args, _ = parser.parse_known_args()
time.sleep(0.1)
store_names = {"bili": "bilibili", "xhs": "xhs"}
id_names = {"bili": "video_id", "xhs": "note_id"}
result_dir = Path(args.output_dir) / store_names[args.platform] / "jsonl"
result_dir.mkdir(parents=True, exist_ok=True)
(result_dir / "search_contents_test.jsonl").write_text(
    json.dumps({id_names[args.platform]: "1"}) + "\\n",
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    settings = replace(
        worker_settings(test_settings, runner),
        douyin_qrcode_startup_timeout_seconds=0.05,
    )
    task = seed_task(repository, settings, platform=platform)

    asyncio.run(
        asyncio.wait_for(CrawlerWorker(repository, settings).run_once(), timeout=3)
    )

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


@pytest.mark.parametrize(
    "platform", ["bili", "xhs", "zhihu", "wb", "tieba"]
)
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


@pytest.mark.parametrize("platform", ["dy", "ks"])
def test_worker_command_rejects_deferred_search_modes(
    test_settings: Settings,
    repository: CrawlerTaskRepository,
    platform: str,
) -> None:
    task = seed_task(repository, test_settings, platform=platform)
    worker = CrawlerWorker(repository, test_settings)

    with pytest.raises(ValueError, match="unavailable"):
        worker._build_command(
            task,
            test_settings.output_root / "tasks" / str(task["id"]),
            test_settings.qrcode_root / f"{task['id']}.png",
        )
