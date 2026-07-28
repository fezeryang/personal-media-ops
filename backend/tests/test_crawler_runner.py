import asyncio
import importlib.util
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType

import pytest

RUNNER_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "crawler" / "run_mediacrawler.py"
)
TASK_ID = "28a58041-9be7-4b39-9dea-2493fe10c249"


def load_runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mediaops_runner", RUNNER_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner_arguments(
    output_root: Path,
    qrcode_root: Path,
    platform: str,
    headless: str = "true",
) -> list[str]:
    return [
        str(RUNNER_PATH),
        "--platform",
        platform,
        "--crawler-type",
        "search",
        "--keywords=--literal-keyword",
        "--login-type",
        "qrcode",
        "--requested-count",
        "5",
        "--output-dir",
        str(output_root / "tasks" / TASK_ID),
        "--qrcode-path",
        str(qrcode_root / f"{TASK_ID}.png"),
        "--max-concurrency-num",
        "1",
        "--enable-comments",
        "false",
        "--enable-sub-comments",
        "false",
        "--headless",
        headless,
    ]


@pytest.mark.parametrize(
    "platform", ["bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks"]
)
def test_runner_accepts_only_registered_platform_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
) -> None:
    output_root = tmp_path / "output"
    qrcode_root = tmp_path / "qrcodes"
    monkeypatch.setenv("MEDIAOPS_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("MEDIAOPS_QRCODE_ROOT", str(qrcode_root))
    monkeypatch.setattr(
        sys,
        "argv",
        runner_arguments(output_root, qrcode_root, platform),
    )

    arguments = load_runner().parse_arguments()

    assert arguments.platform == platform
    assert arguments.keywords == "--literal-keyword"
    assert arguments.max_concurrency_num == 1
    assert arguments.enable_comments is False
    assert arguments.enable_sub_comments is False
    assert arguments.headless is True


@pytest.mark.parametrize(
    ("value", "expected"),
    [("true", True), ("false", False)],
)
def test_runner_parses_headless_browser_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    expected: bool,
) -> None:
    output_root = tmp_path / "output"
    qrcode_root = tmp_path / "qrcodes"
    monkeypatch.setenv("MEDIAOPS_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("MEDIAOPS_QRCODE_ROOT", str(qrcode_root))
    monkeypatch.setattr(
        sys,
        "argv",
        runner_arguments(output_root, qrcode_root, "dy", headless=value),
    )

    assert load_runner().parse_arguments().headless is expected


def test_runner_defaults_to_headless_for_previous_release_workers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Deployment installs this runner before the Worker restarts.

    A previous-release Worker calls the newly installed runner without
    ``--headless``; that must keep the historical headless behaviour instead
    of failing the task with an argparse usage error.
    """
    output_root = tmp_path / "output"
    qrcode_root = tmp_path / "qrcodes"
    arguments = runner_arguments(output_root, qrcode_root, "dy")
    del arguments[arguments.index("--headless") : arguments.index("--headless") + 2]
    monkeypatch.setenv("MEDIAOPS_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("MEDIAOPS_QRCODE_ROOT", str(qrcode_root))
    monkeypatch.setattr(sys, "argv", arguments)

    assert load_runner().parse_arguments().headless is True


@pytest.mark.parametrize(
    ("flag", "value"),
    [
        ("--requested-count", "21"),
        ("--max-concurrency-num", "2"),
        ("--enable-comments", "true"),
        ("--enable-sub-comments", "true"),
    ],
)
def test_runner_rejects_unsafe_runtime_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    value: str,
) -> None:
    output_root = tmp_path / "output"
    qrcode_root = tmp_path / "qrcodes"
    arguments = runner_arguments(output_root, qrcode_root, "bili")
    arguments[arguments.index(flag) + 1] = value
    monkeypatch.setenv("MEDIAOPS_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("MEDIAOPS_QRCODE_ROOT", str(qrcode_root))
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit):
        load_runner().parse_arguments()


def test_runner_rejects_paths_outside_configured_roots(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_root = tmp_path / "output"
    qrcode_root = tmp_path / "qrcodes"
    arguments = runner_arguments(output_root, qrcode_root, "bili")
    arguments[arguments.index("--output-dir") + 1] = str(
        tmp_path / "outside" / "task-id"
    )
    monkeypatch.setenv("MEDIAOPS_OUTPUT_ROOT", str(output_root))
    monkeypatch.setenv("MEDIAOPS_QRCODE_ROOT", str(qrcode_root))
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit):
        load_runner().parse_arguments()


def _record_execv(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, list[str]]]:
    calls: list[tuple[str, list[str]]] = []

    def fake_execv(path: str, arguments: list[str]) -> None:
        calls.append((path, list(arguments)))

    monkeypatch.setattr(os, "execv", fake_execv)
    return calls


def test_runner_reexecs_headful_run_under_xvfb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_runner()
    monkeypatch.delenv("DISPLAY", raising=False)
    # setenv (not delenv) so monkeypatch always restores the marker this test
    # makes the runner write into the real process environment.
    monkeypatch.setenv(runner.XVFB_WRAPPED_ENVIRONMENT_MARKER, "")
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(sys, "argv", [str(RUNNER_PATH), "--platform", "dy"])
    calls = _record_execv(monkeypatch)

    runner.ensure_virtual_display(False)

    assert calls == [
        (
            "/usr/bin/xvfb-run",
            ["xvfb-run", "-a", sys.executable, str(RUNNER_PATH), "--platform", "dy"],
        )
    ]
    assert os.environ[runner.XVFB_WRAPPED_ENVIRONMENT_MARKER] == "1"


@pytest.mark.parametrize(
    ("headless", "display", "wrapped"),
    [
        (True, None, None),
        (False, ":99", None),
    ],
)
def test_runner_skips_xvfb_reexec_when_not_needed(
    monkeypatch: pytest.MonkeyPatch,
    headless: bool,
    display: str | None,
    wrapped: str | None,
) -> None:
    runner = load_runner()
    for name, value in (
        ("DISPLAY", display),
        (runner.XVFB_WRAPPED_ENVIRONMENT_MARKER, wrapped),
    ):
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    calls = _record_execv(monkeypatch)

    runner.ensure_virtual_display(headless)

    assert calls == []


def test_runner_fails_when_xvfb_wrapper_did_not_establish_display(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_runner()
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.setenv(runner.XVFB_WRAPPED_ENVIRONMENT_MARKER, "1")
    calls = _record_execv(monkeypatch)

    with pytest.raises(SystemExit, match="did not provide DISPLAY"):
        runner.ensure_virtual_display(False)

    assert calls == []


def test_runner_fails_headful_run_without_xvfb(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_runner()
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv(runner.XVFB_WRAPPED_ENVIRONMENT_MARKER, raising=False)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    calls = _record_execv(monkeypatch)

    with pytest.raises(SystemExit, match="xvfb-run"):
        runner.ensure_virtual_display(False)

    assert calls == []


@pytest.mark.parametrize(
    ("platform", "expected_calls"),
    [
        ("dy", [10]),
        ("bili", []),
        ("xhs", []),
        ("zhihu", []),
        ("wb", []),
        ("tieba", []),
        ("ks", []),
    ],
)
def test_runner_lowers_only_douyin_process_priority(
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    expected_calls: list[int],
) -> None:
    runner = load_runner()
    calls: list[int] = []

    def fake_nice(increment: int) -> int:
        calls.append(increment)
        return 10

    monkeypatch.setattr(os, "nice", fake_nice)

    runner.lower_platform_process_priority(platform)

    assert calls == expected_calls


def test_runner_fails_clearly_when_douyin_priority_cannot_be_lowered(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = load_runner()

    def fail_nice(increment: int) -> int:
        raise OSError("not supported")

    monkeypatch.setattr(os, "nice", fail_nice)

    with pytest.raises(SystemExit, match="process priority"):
        runner.lower_platform_process_priority("dy")


class FakeDouyinNavigationError(Exception):
    pass


class FakeDouyinLoginEntry:
    def __init__(self, *, visible: bool, click_error: Exception | None = None) -> None:
        self.visible = visible
        self.click_error = click_error
        self.click_calls: list[int] = []

    async def is_visible(self) -> bool:
        return self.visible

    async def click(self, *, timeout: int) -> None:
        self.click_calls.append(timeout)
        if self.click_error is not None:
            raise self.click_error


class FakeDouyinLoginEntries:
    def __init__(
        self,
        entries: list[FakeDouyinLoginEntry],
        *,
        empty_scans: int = 0,
    ) -> None:
        self.entries = entries
        self.empty_scans = empty_scans
        self.count_calls = 0

    async def count(self) -> int:
        self.count_calls += 1
        if self.empty_scans > 0:
            self.empty_scans -= 1
            return 0
        return len(self.entries)

    def nth(self, index: int) -> FakeDouyinLoginEntry:
        return self.entries[index]


class FakeDouyinLoginPage:
    def __init__(
        self,
        *,
        dialog_visible: bool,
        entries: list[FakeDouyinLoginEntry],
        empty_entry_scans: int = 0,
    ) -> None:
        self.dialog_visible = dialog_visible
        self.entries = FakeDouyinLoginEntries(
            entries,
            empty_scans=empty_entry_scans,
        )
        self.wait_calls: list[tuple[str, str, int]] = []
        self.locator_calls: list[str] = []

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str,
        timeout: int,
    ) -> None:
        self.wait_calls.append((selector, state, timeout))
        if not self.dialog_visible:
            raise FakeDouyinNavigationError("Timeout waiting for login dialog")

    def locator(self, selector: str) -> FakeDouyinLoginEntries:
        self.locator_calls.append(selector)
        return self.entries


class FakeDouyinLogin:
    def __init__(self, page: FakeDouyinLoginPage) -> None:
        self.context_page = page


def test_runner_accepts_legacy_and_current_douyin_login_dialogs() -> None:
    runner = load_runner()

    assert runner.DOUYIN_LOGIN_DIALOG_SELECTOR == (
        '#login-panel-new, [id^="login-full-panel-"]'
    )


def test_runner_keeps_auto_opened_douyin_login_dialog() -> None:
    runner = load_runner()
    page = FakeDouyinLoginPage(dialog_visible=True, entries=[])

    asyncio.run(
        runner.open_douyin_login_dialog(
            FakeDouyinLogin(page),
            FakeDouyinNavigationError,
        )
    )

    assert page.wait_calls == [
        (runner.DOUYIN_LOGIN_DIALOG_SELECTOR, "visible", 10_000)
    ]
    assert page.locator_calls == []


def test_runner_clicks_visible_douyin_login_entry_when_tag_changes() -> None:
    runner = load_runner()
    hidden_entry = FakeDouyinLoginEntry(visible=False)
    visible_entry = FakeDouyinLoginEntry(visible=True)
    page = FakeDouyinLoginPage(
        dialog_visible=False,
        entries=[hidden_entry, visible_entry],
    )

    async def show_dialog_after_click(*, timeout: int) -> None:
        visible_entry.click_calls.append(timeout)
        page.dialog_visible = True

    visible_entry.click = show_dialog_after_click  # type: ignore[method-assign]

    asyncio.run(
        runner.open_douyin_login_dialog(
            FakeDouyinLogin(page),
            FakeDouyinNavigationError,
        )
    )

    assert page.locator_calls == [runner.DOUYIN_LOGIN_ENTRY_SELECTOR]
    assert hidden_entry.click_calls == []
    assert visible_entry.click_calls == [5_000]
    assert page.wait_calls == [
        (runner.DOUYIN_LOGIN_DIALOG_SELECTOR, "visible", 10_000),
        (runner.DOUYIN_LOGIN_DIALOG_SELECTOR, "visible", 10_000),
    ]


def test_runner_fails_clearly_when_douyin_login_entry_is_absent() -> None:
    runner = load_runner()
    page = FakeDouyinLoginPage(dialog_visible=False, entries=[])

    with pytest.raises(RuntimeError, match="login entry"):
        asyncio.run(
            runner.open_douyin_login_dialog(
                FakeDouyinLogin(page),
                FakeDouyinNavigationError,
                entry_scan_attempts=1,
                entry_scan_delay_seconds=0,
            )
        )


def test_runner_waits_for_douyin_login_entry_during_waf_reload() -> None:
    runner = load_runner()
    visible_entry = FakeDouyinLoginEntry(visible=True)
    page = FakeDouyinLoginPage(
        dialog_visible=False,
        entries=[visible_entry],
        empty_entry_scans=1,
    )

    async def show_dialog_after_click(*, timeout: int) -> None:
        visible_entry.click_calls.append(timeout)
        page.dialog_visible = True

    visible_entry.click = show_dialog_after_click  # type: ignore[method-assign]

    asyncio.run(
        runner.open_douyin_login_dialog(
            FakeDouyinLogin(page),
            FakeDouyinNavigationError,
            entry_scan_attempts=2,
            entry_scan_delay_seconds=0,
        )
    )

    assert page.entries.count_calls == 2
    assert visible_entry.click_calls == [5_000]


class FakeDouyinPage:
    def __init__(self) -> None:
        self.load_state_calls: list[tuple[str, int]] = []

    async def wait_for_load_state(self, state: str, *, timeout: int) -> None:
        self.load_state_calls.append((state, timeout))


class FakeDouyinCrawler:
    def __init__(self) -> None:
        self.context_page = FakeDouyinPage()


def test_runner_retries_douyin_client_creation_after_navigation_race() -> None:
    runner = load_runner()
    crawler = FakeDouyinCrawler()
    calls = 0

    async def create_client(crawler_value: object, proxy: object) -> object:
        nonlocal calls
        calls += 1
        assert crawler_value is crawler
        assert proxy == "fixed-proxy"
        if calls < 3:
            raise FakeDouyinNavigationError(
                "Page.evaluate: Execution context was destroyed, "
                "most likely because of a navigation"
            )
        return "client"

    result = asyncio.run(
        runner.create_douyin_client_with_navigation_retry(
            crawler,
            "fixed-proxy",
            create_client,
            FakeDouyinNavigationError,
            retry_delay_seconds=0,
        )
    )

    assert result == "client"
    assert calls == 3
    assert crawler.context_page.load_state_calls == [
        ("domcontentloaded", 15_000),
        ("domcontentloaded", 15_000),
    ]


def test_runner_does_not_retry_unrelated_douyin_playwright_error() -> None:
    runner = load_runner()
    crawler = FakeDouyinCrawler()
    calls = 0

    async def create_client(crawler_value: object, proxy: object) -> object:
        nonlocal calls
        calls += 1
        raise FakeDouyinNavigationError("Page.evaluate: Target closed")

    with pytest.raises(FakeDouyinNavigationError, match="Target closed"):
        asyncio.run(
            runner.create_douyin_client_with_navigation_retry(
                crawler,
                None,
                create_client,
                FakeDouyinNavigationError,
                retry_delay_seconds=0,
            )
        )

    assert calls == 1
    assert crawler.context_page.load_state_calls == []


def test_runner_stops_after_bounded_douyin_navigation_retries() -> None:
    runner = load_runner()
    crawler = FakeDouyinCrawler()
    calls = 0

    async def create_client(crawler_value: object, proxy: object) -> object:
        nonlocal calls
        calls += 1
        raise FakeDouyinNavigationError(
            "Page.evaluate: Execution context was destroyed"
        )

    with pytest.raises(FakeDouyinNavigationError, match="Execution context"):
        asyncio.run(
            runner.create_douyin_client_with_navigation_retry(
                crawler,
                None,
                create_client,
                FakeDouyinNavigationError,
                retry_delay_seconds=0,
            )
        )

    assert calls == 3
    assert crawler.context_page.load_state_calls == [
        ("domcontentloaded", 15_000),
        ("domcontentloaded", 15_000),
    ]


class FakeWeiboPlaywrightError(Exception):
    pass


class FakeWeiboLoginEntry:
    def __init__(self, *, visible: bool) -> None:
        self.visible = visible
        self.click_calls: list[int] = []
        self.on_click: object | None = None

    async def is_visible(self) -> bool:
        return self.visible

    async def click(self, *, timeout: int) -> None:
        self.click_calls.append(timeout)
        if callable(self.on_click):
            self.on_click()


class FakeWeiboLoginEntries:
    def __init__(self, entries: list[FakeWeiboLoginEntry]) -> None:
        self.entries = entries

    async def count(self) -> int:
        return len(self.entries)

    def nth(self, index: int) -> FakeWeiboLoginEntry:
        return self.entries[index]


class FakeWeiboLoginPage:
    def __init__(
        self,
        *,
        qrcode_visible: bool,
        entries: list[FakeWeiboLoginEntry],
    ) -> None:
        self.qrcode_visible = qrcode_visible
        self.entries = FakeWeiboLoginEntries(entries)
        self.wait_calls: list[tuple[str, str, int]] = []
        self.locator_calls: list[str] = []

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str,
        timeout: int,
    ) -> None:
        self.wait_calls.append((selector, state, timeout))
        if not self.qrcode_visible:
            raise FakeWeiboPlaywrightError("Timeout waiting for Weibo QR code")

    def locator(self, selector: str) -> FakeWeiboLoginEntries:
        self.locator_calls.append(selector)
        return self.entries


def test_runner_keeps_visible_weibo_qrcode_without_clicking() -> None:
    runner = load_runner()
    page = FakeWeiboLoginPage(qrcode_visible=True, entries=[])

    asyncio.run(
        runner.open_weibo_qrcode_entry(
            page,
            FakeWeiboPlaywrightError,
        )
    )

    assert page.wait_calls == [
        (runner.WEIBO_QRCODE_SELECTOR, "visible", 1_000)
    ]
    assert page.locator_calls == []


def test_runner_opens_weibo_qrcode_from_exact_visible_entry() -> None:
    runner = load_runner()
    hidden_entry = FakeWeiboLoginEntry(visible=False)
    visible_entry = FakeWeiboLoginEntry(visible=True)
    page = FakeWeiboLoginPage(
        qrcode_visible=False,
        entries=[hidden_entry, visible_entry],
    )
    visible_entry.on_click = lambda: setattr(page, "qrcode_visible", True)

    asyncio.run(
        runner.open_weibo_qrcode_entry(
            page,
            FakeWeiboPlaywrightError,
        )
    )

    assert page.locator_calls == [runner.WEIBO_QRCODE_ENTRY_SELECTOR]
    assert hidden_entry.click_calls == []
    assert visible_entry.click_calls == [5_000]
    assert page.wait_calls == [
        (runner.WEIBO_QRCODE_SELECTOR, "visible", 1_000),
        (runner.WEIBO_QRCODE_SELECTOR, "visible", 10_000),
    ]


def test_runner_fails_clearly_when_weibo_qrcode_entry_is_absent() -> None:
    runner = load_runner()
    page = FakeWeiboLoginPage(qrcode_visible=False, entries=[])

    with pytest.raises(RuntimeError, match="Weibo QR-code login entry"):
        asyncio.run(
            runner.open_weibo_qrcode_entry(
                page,
                FakeWeiboPlaywrightError,
                entry_scan_attempts=1,
                entry_scan_delay_seconds=0,
            )
        )


def test_runner_reports_existing_login_state_without_exposing_cookies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    runner = load_runner()

    async def pong(client: object) -> bool:
        return True

    observed = runner.create_login_state_observer("zhihu", pong)

    assert asyncio.run(observed(object())) is True
    output = capsys.readouterr().out
    assert output == "[MediaOps] Existing login state ready: zhihu\n"
    assert "cookie" not in output.casefold()


def test_runner_forces_mediacrawler_safety_flags() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert '"--get_comment",\n        "false"' in source
    assert '"--get_sub_comment",\n        "false"' in source
    assert '"--enable_ip_proxy",\n        "false"' in source
    assert '"--max_concurrency_num",\n        "1"' in source
    assert "config.ENABLE_IP_PROXY = False" in source
    assert "config.HEADLESS = args.headless" in source
    assert "config.CDP_HEADLESS = args.headless" in source
    assert '"--headless",\n        "true" if args.headless else "false"' in source
    assert (
        'if args.platform == "dy":\n        install_douyin_navigation_retry()'
        in source
    )
    assert (
        'if args.platform == "wb":\n        install_weibo_qrcode_entry_patch()'
        in source
    )
    assert "install_login_state_observer(args.platform)" in source
