import asyncio
import fcntl
import os
import re
import signal
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from app.core.config import Settings, settings
from app.crawler.adapters import CrawlerPlatformAdapter
from app.crawler.registry import CrawlerPlatformRegistry, platform_registry
from app.crawler.results import parse_task_entities
from app.models.crawler_platform import TaskMode
from app.repositories.automation import AutomationRepository
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.intelligence import IntelligenceRepository
from app.repositories.library import LibraryRepository
from app.services.automation import AutomationCoordinator
from app.services.intelligence.briefs import DeterministicBriefGenerator
from app.services.intelligence.coordinator import IntelligenceCoordinator
from app.services.intelligence.trends import TrendService

STREAM_READER_LIMIT_BYTES = 1024 * 1024
SENSITIVE_LOG_ASSIGNMENT = re.compile(
    r"(?i)\b("
    r"xsec_token|access_token|refresh_token|token|signature"
    r")\b([\"']?\s*[:=]\s*)([\"']?)([^&\s,\"'}]+)([\"']?)"
)
SENSITIVE_LOG_HEADER = re.compile(
    r"(?i)\b(cookie|authorization)\b(\s*[:=]\s*)[^\r\n]*"
)
StreamProcessOutcome = Literal[
    "completed",
    "cancelled",
    "startup_timeout",
    "login_failed",
]
StreamProcessResult = tuple[StreamProcessOutcome, str | None]


class WorkerAlreadyRunning(RuntimeError):
    pass


def redact_sensitive_log_text(value: str) -> str:
    redacted = SENSITIVE_LOG_HEADER.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        value,
    )
    return SENSITIVE_LOG_ASSIGNMENT.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]",
        redacted,
    )


class WorkerLock:
    def __init__(self, database_path: Path) -> None:
        self.lock_path = database_path.with_suffix(
            database_path.suffix + ".worker.lock"
        )
        self._handle: Any = None

    def __enter__(self) -> Self:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.lock_path.open("a+")
        try:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            self._handle.close()
            self._handle = None
            raise WorkerAlreadyRunning(
                f"another crawler worker holds {self.lock_path}"
            ) from error
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(str(os.getpid()))
        self._handle.flush()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._handle is not None:
            fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
            self._handle.close()
            self._handle = None


class CrawlerWorker:
    def __init__(
        self,
        repository: CrawlerTaskRepository,
        config: Settings,
        *,
        terminate_timeout_seconds: float = 5,
        registry: CrawlerPlatformRegistry = platform_registry,
        library_repository: LibraryRepository | None = None,
        automation_coordinator: AutomationCoordinator | None = None,
        intelligence_coordinator: IntelligenceCoordinator | None = None,
    ) -> None:
        self.repository = repository
        self.settings = config
        self.terminate_timeout_seconds = terminate_timeout_seconds
        self.registry = registry
        self.library_repository = library_repository or LibraryRepository(
            config.database_path
        )
        self.automation_coordinator = automation_coordinator or AutomationCoordinator(
            AutomationRepository(config),
            config,
            library_repository=self.library_repository,
        )
        intelligence_repository = IntelligenceRepository(config.database_path)
        self.intelligence_coordinator = (
            intelligence_coordinator
            or IntelligenceCoordinator(
                intelligence_repository,
                TrendService(intelligence_repository),
                DeterministicBriefGenerator(intelligence_repository),
            )
        )

    async def run_forever(self) -> None:
        self.registry.list_capabilities(self.settings.enabled_platforms)
        self.repository.initialize()
        with WorkerLock(self.settings.database_path):
            self.repository.fail_interrupted_tasks()
            self.automation_coordinator.reconcile_runs()
            next_automation_poll = 0.0
            while True:
                loop_time = asyncio.get_running_loop().time()
                if loop_time >= next_automation_poll:
                    self.automation_coordinator.schedule_due(
                        datetime.now(UTC)
                    )
                    self.intelligence_coordinator.schedule_due(
                        datetime.now(UTC)
                    )
                    self.automation_coordinator.reconcile_runs()
                    next_automation_poll = (
                        loop_time
                        + self.settings.automation_poll_interval_seconds
                    )
                claimed = await self.run_once()
                if not claimed:
                    await asyncio.sleep(self.settings.crawler_poll_interval_seconds)

    async def run_once(self) -> bool:
        task = self.repository.claim_next()
        if task is None:
            return False
        await self._execute(task)
        self.automation_coordinator.reconcile_runs()
        return True

    async def _execute(self, task: dict[str, Any]) -> None:
        task_id = str(task["id"])
        adapter: CrawlerPlatformAdapter | None = None
        try:
            output_dir, log_path, qrcode_path = self._validated_paths(task)
            output_dir.mkdir(parents=True, exist_ok=True)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            qrcode_path.parent.mkdir(parents=True, exist_ok=True)

            adapter = self.registry.require_mode_enabled(
                str(task["platform"]),
                str(task["crawler_type"]),
                self.settings.enabled_platforms,
            )
            command = self._build_command(task, output_dir, qrcode_path)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=self._build_environment(),
                start_new_session=True,
                limit=STREAM_READER_LIMIT_BYTES,
            )
            try:
                self.repository.set_pid(task_id, process.pid)
                stream_outcome, stream_detail = await self._stream_process(
                    task_id,
                    process,
                    log_path,
                    qrcode_path,
                    adapter,
                )
                return_code = (
                    await process.wait() if stream_outcome == "completed" else None
                )
            except Exception:
                await self._terminate_process(process)
                raise
            if stream_outcome == "cancelled":
                self.repository.complete_cancelled(task_id)
                return
            if stream_outcome == "startup_timeout":
                timeout = self._qrcode_startup_timeout(adapter)
                self.repository.complete_failure(
                    task_id,
                    f"{adapter.display_name} QR-code startup timed out after "
                    f"{timeout:g} seconds before login became ready",
                )
                return
            if stream_outcome == "login_failed":
                self.repository.complete_failure(
                    task_id,
                    stream_detail or "Platform login failed",
                )
                return

            if return_code == 0:
                mode: TaskMode = str(task["crawler_type"])
                batch = parse_task_entities(
                    adapter=adapter,
                    task_dir=output_dir,
                    mode=mode,
                    requested_count=int(task["requested_count"]),
                    requested_comment_count=int(task["requested_comment_count"]),
                    requested_sub_comment_count=int(
                        task["requested_sub_comment_count"]
                    ),
                )
                self.library_repository.ingest_task(task_id=task_id, batch=batch)
            else:
                failure = f"MediaCrawler exited with code {return_code}"
                if stream_detail:
                    failure = f"{failure}: {stream_detail}"
                self.repository.complete_failure(
                    task_id,
                    adapter.classify_failure(
                        redact_sensitive_log_text(failure)
                    ),
                )
        except Exception as error:  # noqa: BLE001 - persist worker boundary failures
            failure = redact_sensitive_log_text(
                f"Crawler execution failed: {error}"
            )
            if adapter is not None:
                failure = adapter.classify_failure(failure)
            self.repository.complete_failure(
                task_id,
                failure,
            )

    def _validated_paths(
        self,
        task: dict[str, Any],
    ) -> tuple[Path, Path, Path]:
        task_id = str(task["id"])
        expected_output = (self.settings.output_root / "tasks" / task_id).resolve()
        expected_log = (self.settings.log_root / "crawler" / f"{task_id}.log").resolve()
        expected_qrcode = (self.settings.qrcode_root / f"{task_id}.png").resolve()
        roots_and_paths = (
            (self.settings.output_root / "tasks", expected_output, task["output_dir"]),
            (self.settings.log_root / "crawler", expected_log, task["log_path"]),
            (self.settings.qrcode_root, expected_qrcode, task["qrcode_path"]),
        )
        for root, expected, stored in roots_and_paths:
            if not expected.is_relative_to(root.resolve()):
                raise ValueError("generated task path escapes its configured root")
            if Path(str(stored)).resolve() != expected:
                raise ValueError("stored task path does not match generated path")
        return expected_output, expected_log, expected_qrcode

    def _build_command(
        self,
        task: dict[str, Any],
        output_dir: Path,
        qrcode_path: Path,
    ) -> list[str]:
        adapter = self.registry.get(str(task["platform"]))
        return [
            str(self.settings.mediacrawler_python),
            str(self.settings.mediacrawler_runner),
            *adapter.build_runner_arguments(
                task=task,
                output_dir=output_dir,
                qrcode_path=qrcode_path,
            ),
        ]

    def _build_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        path_entries: list[str] = []
        if self.settings.node_binary is not None:
            path_entries.append(str(self.settings.node_binary.parent))
            environment["MEDIAOPS_NODE_BINARY"] = str(self.settings.node_binary)
        elif self.settings.node_bin_dir is not None:
            path_entries.append(str(self.settings.node_bin_dir))
        path_entries.extend(
            [
                "/usr/local/sbin",
                "/usr/local/bin",
                "/usr/sbin",
                "/usr/bin",
                "/sbin",
                "/bin",
            ]
        )
        current_path = environment.get("PATH")
        if current_path:
            path_entries.append(current_path)
        environment["PATH"] = os.pathsep.join(dict.fromkeys(path_entries))
        return environment

    def _qrcode_startup_timeout(
        self,
        adapter: CrawlerPlatformAdapter,
    ) -> float:
        return (
            adapter.qrcode_startup_timeout_seconds
            if adapter.qrcode_startup_timeout_seconds is not None
            else self.settings.douyin_qrcode_startup_timeout_seconds
        )

    async def _stream_process(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        log_path: Path,
        qrcode_path: Path,
        adapter: CrawlerPlatformAdapter,
    ) -> StreamProcessResult:
        if process.stdout is None:
            raise RuntimeError("crawler process stdout pipe is unavailable")
        waiting_for_login = False
        qrcode_seen = False
        login_ready = False
        last_output_line: str | None = None
        startup_started_at = asyncio.get_running_loop().time()
        with log_path.open("ab", buffering=0) as log_handle:
            while True:
                if self.repository.is_cancel_requested(task_id):
                    await self._terminate_process(process)
                    return "cancelled", None

                if not qrcode_seen and qrcode_path.is_file():
                    qrcode_seen = True
                    if not login_ready:
                        waiting_for_login = True
                        self.repository.set_waiting_login(task_id)

                if (
                    not qrcode_seen
                    and not login_ready
                    and asyncio.get_running_loop().time() - startup_started_at
                    >= self._qrcode_startup_timeout(adapter)
                ):
                    await self._terminate_process(process)
                    return "startup_timeout", None

                try:
                    line = await asyncio.wait_for(
                        self._read_stream_chunk(process.stdout),
                        timeout=self.settings.crawler_poll_interval_seconds,
                    )
                except TimeoutError:
                    if process.returncode is not None:
                        break
                    continue

                if line:
                    decoded_line = line.decode("utf-8", errors="replace")
                    safe_line = redact_sensitive_log_text(decoded_line)
                    log_handle.write(safe_line.encode("utf-8"))
                    stripped_line = safe_line.strip()
                    if stripped_line:
                        last_output_line = stripped_line[-1000:]
                    login_signal = adapter.classify_login_line(
                        decoded_line
                    )
                    if login_signal == "success":
                        login_ready = True
                        if waiting_for_login:
                            self.repository.set_running(task_id)
                            waiting_for_login = False
                    elif login_signal is not None:
                        await self._terminate_process(process)
                        messages = {
                            "captcha_required": (
                                f"{adapter.display_name} login requires manual "
                                "verification"
                            ),
                            "login_expired": (
                                f"{adapter.display_name} persisted login state expired"
                            ),
                            "login_timeout": (
                                f"{adapter.display_name} login timed out"
                            ),
                        }
                        return "login_failed", messages[login_signal]
                    continue
                break
        return "completed", last_output_line

    @staticmethod
    async def _read_stream_chunk(stream: asyncio.StreamReader) -> bytes:
        """Read one line, degrading to a raw chunk for oversized lines.

        ``readuntil`` keeps the buffered bytes intact when it raises
        ``LimitOverrunError``, so an oversized line is drained with ``read``
        and still lands in the log instead of aborting the task.
        """
        try:
            return await stream.readuntil(b"\n")
        except asyncio.IncompleteReadError as error:
            return error.partial
        except asyncio.LimitOverrunError as error:
            return await stream.read(max(error.consumed, 1))
        except ValueError:
            return await stream.read(STREAM_READER_LIMIT_BYTES)

    async def _terminate_process(
        self,
        process: asyncio.subprocess.Process,
    ) -> None:
        if process.returncode is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(
                process.wait(),
                timeout=self.terminate_timeout_seconds,
            )
        except TimeoutError:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
            await process.wait()


def main() -> None:
    repository = CrawlerTaskRepository(settings.database_path)
    worker = CrawlerWorker(repository, settings)
    try:
        asyncio.run(worker.run_forever())
    except WorkerAlreadyRunning as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
