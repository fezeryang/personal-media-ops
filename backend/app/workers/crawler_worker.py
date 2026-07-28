import asyncio
import fcntl
import os
import signal
from pathlib import Path
from types import TracebackType
from typing import Any, Literal, Self

from app.core.config import Settings, settings
from app.crawler.adapters import CrawlerPlatformAdapter
from app.crawler.registry import CrawlerPlatformRegistry, platform_registry
from app.crawler.results import count_normalized_results
from app.repositories.crawler_tasks import CrawlerTaskRepository

STREAM_READER_LIMIT_BYTES = 1024 * 1024
StreamProcessOutcome = Literal[
    "completed",
    "cancelled",
    "startup_timeout",
    "login_failed",
]
StreamProcessResult = tuple[StreamProcessOutcome, str | None]


class WorkerAlreadyRunning(RuntimeError):
    pass


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
    ) -> None:
        self.repository = repository
        self.settings = config
        self.terminate_timeout_seconds = terminate_timeout_seconds
        self.registry = registry

    async def run_forever(self) -> None:
        self.registry.list_capabilities(self.settings.enabled_platforms)
        self.repository.initialize()
        with WorkerLock(self.settings.database_path):
            self.repository.fail_interrupted_tasks()
            while True:
                claimed = await self.run_once()
                if not claimed:
                    await asyncio.sleep(self.settings.crawler_poll_interval_seconds)

    async def run_once(self) -> bool:
        task = self.repository.claim_next()
        if task is None:
            return False
        await self._execute(task)
        return True

    async def _execute(self, task: dict[str, Any]) -> None:
        task_id = str(task["id"])
        try:
            output_dir, log_path, qrcode_path = self._validated_paths(task)
            output_dir.mkdir(parents=True, exist_ok=True)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            qrcode_path.parent.mkdir(parents=True, exist_ok=True)

            adapter = self.registry.require_enabled(
                str(task["platform"]),
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
                self.repository.complete_success(
                    task_id,
                    count_normalized_results(
                        adapter,
                        output_dir,
                        int(task["requested_count"]),
                    ),
                )
            else:
                self.repository.complete_failure(
                    task_id,
                    f"MediaCrawler exited with code {return_code}",
                )
        except Exception as error:  # noqa: BLE001 - persist worker boundary failures
            self.repository.complete_failure(
                task_id,
                f"Crawler execution failed: {error}",
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
                keywords=str(task["keywords"]),
                requested_count=int(task["requested_count"]),
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
                    log_handle.write(line)
                    login_signal = adapter.classify_login_line(
                        line.decode("utf-8", errors="replace")
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
        return "completed", None

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
