import asyncio
import fcntl
import os
import signal
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from app.core.config import Settings, settings
from app.repositories.crawler_tasks import CrawlerTaskRepository


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
    ) -> None:
        self.repository = repository
        self.settings = config
        self.terminate_timeout_seconds = terminate_timeout_seconds

    async def run_forever(self) -> None:
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

            command = self._build_command(task, output_dir, qrcode_path)
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                env=self._build_environment(),
                start_new_session=True,
            )
            self.repository.set_pid(task_id, process.pid)
            cancelled = await self._stream_process(
                task_id,
                process,
                log_path,
                qrcode_path,
            )
            if cancelled:
                self.repository.complete_cancelled(task_id)
                return

            return_code = await process.wait()
            if return_code == 0:
                self.repository.complete_success(
                    task_id,
                    self._count_jsonl_records(output_dir),
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
        return [
            str(self.settings.mediacrawler_python),
            str(self.settings.mediacrawler_runner),
            "--platform",
            "bili",
            "--crawler-type",
            "search",
            f"--keywords={task['keywords']}",
            "--login-type",
            "qrcode",
            "--requested-count",
            str(task["requested_count"]),
            "--output-dir",
            str(output_dir),
            "--qrcode-path",
            str(qrcode_path),
            "--max-concurrency-num",
            "1",
            "--enable-comments",
            "false",
            "--enable-sub-comments",
            "false",
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

    async def _stream_process(
        self,
        task_id: str,
        process: asyncio.subprocess.Process,
        log_path: Path,
        qrcode_path: Path,
    ) -> bool:
        if process.stdout is None:
            raise RuntimeError("crawler process stdout pipe is unavailable")
        waiting_for_login = False
        qrcode_seen = False
        with log_path.open("ab", buffering=0) as log_handle:
            while True:
                if self.repository.is_cancel_requested(task_id):
                    await self._terminate_process(process)
                    return True

                if not qrcode_seen and qrcode_path.is_file():
                    qrcode_seen = True
                    waiting_for_login = True
                    self.repository.set_waiting_login(task_id)

                try:
                    line = await asyncio.wait_for(
                        process.stdout.readline(),
                        timeout=self.settings.crawler_poll_interval_seconds,
                    )
                except TimeoutError:
                    if process.returncode is not None:
                        break
                    continue

                if line:
                    log_handle.write(line)
                    if waiting_for_login:
                        self.repository.set_running(task_id)
                        waiting_for_login = False
                    continue
                break
        return False

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

    @staticmethod
    def _count_jsonl_records(output_dir: Path) -> int:
        count = 0
        root = output_dir.resolve()
        for candidate in root.rglob("*.jsonl"):
            resolved = candidate.resolve()
            if not resolved.is_relative_to(root):
                raise ValueError("result path escapes task output directory")
            with resolved.open("r", encoding="utf-8", errors="replace") as handle:
                count += sum(1 for line in handle if line.strip())
        return count


def main() -> None:
    repository = CrawlerTaskRepository(settings.database_path)
    worker = CrawlerWorker(repository, settings)
    try:
        asyncio.run(worker.run_forever())
    except WorkerAlreadyRunning as error:
        raise SystemExit(str(error)) from error


if __name__ == "__main__":
    main()
