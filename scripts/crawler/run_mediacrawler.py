from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import importlib
import json
import os
import re
import runpy
import shutil
import sys
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import UUID

MEDIACRAWLER_ROOT = Path("/opt/mediacrawler")
DEFAULT_OUTPUT_ROOT = Path("/var/lib/mediaops/crawler-output")
DEFAULT_QRCODE_ROOT = Path("/var/lib/mediaops/qrcodes")
XVFB_WRAPPED_ENVIRONMENT_MARKER = "MEDIAOPS_XVFB_WRAPPED"
DOUYIN_NAVIGATION_ERROR = "Execution context was destroyed"
DOUYIN_CLIENT_RETRY_ATTEMPTS = 3
DOUYIN_LOGIN_DIALOG_SELECTOR = '#login-panel-new, [id^="login-full-panel-"]'
DOUYIN_LOGIN_ENTRY_SELECTOR = "xpath=//*[normalize-space(.)='登录']"
DOUYIN_LOGIN_ENTRY_SCAN_ATTEMPTS = 40
DOUYIN_LOGIN_ENTRY_SCAN_DELAY_SECONDS = 0.5
DOUYIN_PROCESS_NICE_INCREMENT = 10
WEIBO_QRCODE_SELECTOR = "xpath=//img[@class='w-full h-full']"
WEIBO_QRCODE_ENTRY_SELECTOR = "xpath=//*[normalize-space(.)='扫码登录']"
WEIBO_QRCODE_ENTRY_SCAN_ATTEMPTS = 20
WEIBO_QRCODE_ENTRY_SCAN_DELAY_SECONDS = 0.5
BAIDU_INDEX_URL = "https://www.baidu.com/"
TIEBA_INDEX_URL = "https://tieba.baidu.com/"
TIEBA_SECURITY_VERIFICATION_TITLE = "百度安全验证"
TIEBA_QRCODE_SELECTOR = "xpath=//img[@class='tang-pass-qrcode-img']"
TIEBA_LOGIN_ENTRY_SELECTOR = "div.user-or-login, li.u_login"
TIEBA_LOGIN_ENTRY_SCAN_ATTEMPTS = 20
TIEBA_LOGIN_ENTRY_SCAN_DELAY_SECONDS = 0.5
KUAISHOU_QRCODE_SELECTOR = "xpath=//div[@class='qrcode-img']//img"
KUAISHOU_LOGIN_ENTRY_SELECTOR = "xpath=//p[text()='登录']"
KUAISHOU_LOGIN_ENTRY_SCAN_ATTEMPTS = 20
KUAISHOU_LOGIN_ENTRY_SCAN_DELAY_SECONDS = 0.5
LOGIN_STATE_CLIENTS = {
    "bili": ("media_platform.bilibili.client", "BilibiliClient"),
    "xhs": ("media_platform.xhs.client", "XiaoHongShuClient"),
    "dy": ("media_platform.douyin.client", "DouYinClient"),
    "zhihu": ("media_platform.zhihu.client", "ZhiHuClient"),
    "wb": ("media_platform.weibo.client", "WeiboClient"),
    "tieba": ("media_platform.tieba.client", "BaiduTieBaClient"),
    "ks": ("media_platform.kuaishou.client", "KuaiShouClient"),
}
XHS_AUTH_COOKIE_NAMES = frozenset(
    {
        "id_token",
        "sec_poison_id",
        "web_session",
        "websectiga",
        "xsecappid",
    }
)
XHS_LOGIN_STATE_PROBE_TIMEOUT_SECONDS = 2.0
NATIVE_CRAWLER_TYPES = {"search", "detail", "creator"}
PLATFORM_STORAGE_DIRECTORIES = {
    "bili": "bili",
    "xhs": "xhs",
    "dy": "douyin",
    "zhihu": "zhihu",
    "wb": "weibo",
    "tieba": "tieba",
    "ks": "kuaishou",
}


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"true", "yes", "y", "1"}:
        return True
    if normalized in {"false", "no", "n", "0"}:
        return False
    raise argparse.ArgumentTypeError(f"invalid boolean value: {value!r}")


def _configured_root(environment_name: str, default: Path) -> Path:
    return Path(os.getenv(environment_name, str(default))).expanduser().resolve()


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Personal Media Ops MediaCrawler runner"
    )
    parser.add_argument(
        "--platform",
        required=True,
        choices=["bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks"],
    )
    parser.add_argument(
        "--crawler-type",
        required=True,
        choices=["search", "detail", "creator", "comments", "sub_comments"],
    )
    parser.add_argument("--keywords")
    parser.add_argument("--target-id", action="append", default=[])
    parser.add_argument("--target-url", action="append", default=[])
    parser.add_argument("--creator-id", action="append", default=[])
    parser.add_argument("--creator-url", action="append", default=[])
    parser.add_argument("--parent-content-id")
    parser.add_argument("--parent-comment-id")
    parser.add_argument(
        "--login-type",
        required=True,
        choices=["qrcode"],
    )
    parser.add_argument("--requested-count", required=True, type=int)
    parser.add_argument(
        "--requested-comment-count",
        type=int,
        default=0,
    )
    parser.add_argument(
        "--requested-sub-comment-count",
        type=int,
        default=0,
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--qrcode-path", required=True, type=Path)
    parser.add_argument("--max-concurrency-num", required=True, type=int)
    parser.add_argument("--enable-comments", required=True, type=parse_bool)
    parser.add_argument("--enable-sub-comments", required=True, type=parse_bool)
    # Deployment installs this runner copy (runner-sync) several stages before
    # the Worker restarts (finalize), so a previous-release Worker can call a
    # newly installed runner without this argument. Defaulting to the historical
    # hardcoded headless mode keeps that window working instead of failing every
    # task with an argparse usage error; the Worker always passes it explicitly.
    parser.add_argument("--headless", type=parse_bool, default=True)
    args = parser.parse_args()

    if not 1 <= args.requested_count <= 20:
        parser.error("--requested-count must be between 1 and 20")
    if args.max_concurrency_num != 1:
        parser.error("--max-concurrency-num must be 1")
    if not 0 <= args.requested_comment_count <= 10:
        parser.error("--requested-comment-count must be between 0 and 10")
    if not 0 <= args.requested_sub_comment_count <= 5:
        parser.error("--requested-sub-comment-count must be between 0 and 5")
    if args.enable_comments != (args.crawler_type == "comments"):
        parser.error(
            "--enable-comments must be true only for comments mode"
        )
    if args.enable_sub_comments:
        parser.error("--enable-sub-comments must be false")
    content_targets = [
        *args.target_id,
        *args.target_url,
        *([args.parent_content_id] if args.parent_content_id else []),
    ]
    creator_targets = [*args.creator_id, *args.creator_url]
    if args.crawler_type == "search":
        if not args.keywords or content_targets or creator_targets:
            parser.error("search mode requires only --keywords")
    elif args.crawler_type == "detail":
        if not (args.target_id or args.target_url):
            parser.error("detail mode requires --target-id or --target-url")
        if len(args.target_id) + len(args.target_url) > args.requested_count:
            parser.error(
                "detail mode target count must not exceed --requested-count"
            )
    elif args.crawler_type == "creator":
        if not creator_targets:
            parser.error("creator mode requires --creator-id or --creator-url")
        if len(creator_targets) > args.requested_count:
            parser.error(
                "creator mode target count must not exceed --requested-count"
            )
    elif args.crawler_type == "comments":
        if len(content_targets) != 1 or not 1 <= args.requested_comment_count <= 10:
            parser.error(
                "comments mode requires one content target and a comment "
                "count from 1 to 10"
            )
    elif (
        len(content_targets) != 1
        or not args.parent_comment_id
        or not 1 <= args.requested_sub_comment_count <= 5
    ):
        parser.error(
            "sub_comments mode requires one content target, "
            "--parent-comment-id, and a sub-comment count from 1 to 5"
        )
    for target in (
        *args.target_id,
        *args.target_url,
        *args.creator_id,
        *args.creator_url,
    ):
        if not target.strip() or not target.isprintable() or len(target) > 2000:
            parser.error("task targets must be printable and at most 2000 characters")
    for identifier in (
        *args.target_id,
        *args.creator_id,
        *([args.parent_content_id] if args.parent_content_id else []),
    ):
        if identifier.casefold().startswith(("http://", "https://")):
            parser.error("HTTP targets must use a URL argument")
    args.output_dir = args.output_dir.expanduser().resolve()
    args.qrcode_path = args.qrcode_path.expanduser().resolve()
    output_tasks_root = (
        _configured_root("MEDIAOPS_OUTPUT_ROOT", DEFAULT_OUTPUT_ROOT) / "tasks"
    ).resolve()
    qrcode_root = _configured_root(
        "MEDIAOPS_QRCODE_ROOT",
        DEFAULT_QRCODE_ROOT,
    )

    if not args.output_dir.is_relative_to(output_tasks_root):
        parser.error("--output-dir must be inside MEDIAOPS_OUTPUT_ROOT/tasks")
    if args.qrcode_path.parent != qrcode_root:
        parser.error("--qrcode-path must be directly inside MEDIAOPS_QRCODE_ROOT")
    if args.qrcode_path.suffix.lower() != ".png":
        parser.error("--qrcode-path must use the .png extension")
    if args.output_dir.name != args.qrcode_path.stem:
        parser.error("task output and QR code paths must use the same task ID")
    try:
        UUID(args.output_dir.name)
    except ValueError:
        parser.error("task output and QR code paths must use a UUID task ID")

    return args


def ensure_virtual_display(headless: bool) -> None:
    """Re-exec under ``xvfb-run`` when a headful browser has no display.

    Douyin serves a captcha interstitial to headless browsers, so that
    platform must run headful. On a server there is no X display, so the
    whole process is replaced by ``xvfb-run`` before any MediaCrawler import
    or output mutation happens. ``MEDIAOPS_XVFB_WRAPPED`` marks the wrapped
    process so the re-exec can never loop.
    """
    if headless:
        return
    if os.environ.get("DISPLAY", "").strip():
        return
    if os.environ.get(XVFB_WRAPPED_ENVIRONMENT_MARKER):
        raise SystemExit(
            "xvfb-run did not provide DISPLAY for headful browsing"
        )

    xvfb_run = shutil.which("xvfb-run")
    if xvfb_run is None:
        raise SystemExit(
            "headful browsing needs a virtual display but xvfb-run was not "
            "found; install xvfb on this host before enabling this platform"
        )

    os.environ[XVFB_WRAPPED_ENVIRONMENT_MARKER] = "1"
    os.execv(xvfb_run, ["xvfb-run", "-a", sys.executable, *sys.argv])


def lower_platform_process_priority(platform: str) -> None:
    """Keep Douyin's WAF proof-of-work from starving API and SSH processes."""
    if platform != "dy":
        return
    try:
        niceness = os.nice(DOUYIN_PROCESS_NICE_INCREMENT)
    except OSError as error:
        raise SystemExit(
            "unable to lower Douyin process priority before browser startup"
        ) from error
    print(
        f"[MediaOps] Douyin browser process niceness: {niceness}",
        flush=True,
    )


def configure_node_runtime() -> None:
    node_binary_value = os.getenv("MEDIAOPS_NODE_BINARY")
    if not node_binary_value:
        return

    node_binary = Path(node_binary_value).expanduser().resolve()
    if not node_binary.is_file():
        raise SystemExit(f"MEDIAOPS_NODE_BINARY does not exist: {node_binary}")

    current_path = os.environ.get("PATH", "")
    node_bin_dir = str(node_binary.parent)
    os.environ["PATH"] = (
        f"{node_bin_dir}{os.pathsep}{current_path}" if current_path else node_bin_dir
    )


async def create_douyin_client_with_navigation_retry(
    crawler: object,
    httpx_proxy: object,
    original_create_client: Callable[[object, object], Awaitable[object]],
    retryable_error: type[BaseException],
    *,
    retry_attempts: int = DOUYIN_CLIENT_RETRY_ATTEMPTS,
    retry_delay_seconds: float = 0.5,
) -> object:
    """Retry the narrow post-navigation user-agent race in Douyin startup."""
    for attempt in range(1, retry_attempts + 1):
        try:
            return await original_create_client(crawler, httpx_proxy)
        except retryable_error as error:
            if (
                DOUYIN_NAVIGATION_ERROR not in str(error)
                or attempt >= retry_attempts
            ):
                raise
            context_page = getattr(crawler, "context_page", None)
            if context_page is None:
                raise RuntimeError(
                    "Douyin crawler has no context page for navigation retry"
                ) from error
            print(
                "[MediaOps] Douyin page navigation interrupted client "
                f"initialization; retrying ({attempt}/{retry_attempts - 1})",
                flush=True,
            )
            await context_page.wait_for_load_state(
                "domcontentloaded",
                timeout=15_000,
            )
            if retry_delay_seconds > 0:
                await asyncio.sleep(retry_delay_seconds)
    raise AssertionError("unreachable Douyin client retry state")


async def open_douyin_login_dialog(
    login: object,
    retryable_error: type[BaseException],
    *,
    dialog_timeout_ms: int = 10_000,
    click_timeout_ms: int = 5_000,
    entry_scan_attempts: int = DOUYIN_LOGIN_ENTRY_SCAN_ATTEMPTS,
    entry_scan_delay_seconds: float = DOUYIN_LOGIN_ENTRY_SCAN_DELAY_SECONDS,
) -> None:
    """Open Douyin login without depending on the entry element's HTML tag."""
    context_page = getattr(login, "context_page", None)
    if context_page is None:
        raise RuntimeError("Douyin login has no context page")

    try:
        await context_page.wait_for_selector(
            DOUYIN_LOGIN_DIALOG_SELECTOR,
            state="visible",
            timeout=dialog_timeout_ms,
        )
        return
    except retryable_error as initial_error:
        last_error: BaseException = initial_error

    login_entries = context_page.locator(DOUYIN_LOGIN_ENTRY_SELECTOR)
    for scan_attempt in range(entry_scan_attempts):
        visible_entry_seen = False
        try:
            entry_count = await login_entries.count()
        except retryable_error as error:
            last_error = error
            entry_count = 0

        for index in range(entry_count):
            entry = login_entries.nth(index)
            try:
                if not await entry.is_visible():
                    continue
                visible_entry_seen = True
                await entry.click(timeout=click_timeout_ms)
                await context_page.wait_for_selector(
                    DOUYIN_LOGIN_DIALOG_SELECTOR,
                    state="visible",
                    timeout=dialog_timeout_ms,
                )
                print(
                    "[MediaOps] Opened Douyin login dialog through a visible "
                    "exact-text login entry",
                    flush=True,
                )
                return
            except retryable_error as error:
                last_error = error

        if visible_entry_seen:
            break
        if (
            scan_attempt + 1 < entry_scan_attempts
            and entry_scan_delay_seconds > 0
        ):
            await asyncio.sleep(entry_scan_delay_seconds)

    raise RuntimeError(
        "Douyin login entry was not visible or did not open the login dialog"
    ) from last_error


def install_douyin_navigation_retry() -> None:
    """Patch reviewed Douyin integration seams, never MediaCrawler source."""
    from media_platform.douyin.core import DouYinCrawler
    from media_platform.douyin.login import DouYinLogin
    from playwright.async_api import Error as PlaywrightError

    original_create_client = DouYinCrawler.create_douyin_client

    async def create_client_with_retry(
        crawler: object,
        httpx_proxy: object,
    ) -> object:
        return await create_douyin_client_with_navigation_retry(
            crawler,
            httpx_proxy,
            original_create_client,
            PlaywrightError,
        )

    async def popup_login_dialog(login: object) -> None:
        await open_douyin_login_dialog(login, PlaywrightError)

    DouYinCrawler.create_douyin_client = create_client_with_retry
    DouYinLogin.popup_login_dialog = popup_login_dialog


async def open_qrcode_entry(
    context_page: object,
    retryable_error: type[BaseException],
    *,
    platform_name: str,
    qrcode_selector: str,
    login_entry_selector: str,
    initial_timeout_ms: int = 1_000,
    qrcode_timeout_ms: int = 10_000,
    click_timeout_ms: int = 5_000,
    entry_scan_attempts: int,
    entry_scan_delay_seconds: float,
    click_entry: Callable[[object, int], Awaitable[None]] | None = None,
) -> None:
    """Expose a platform QR code through one bounded, exact entry selector."""
    try:
        await context_page.wait_for_selector(
            qrcode_selector,
            state="visible",
            timeout=initial_timeout_ms,
        )
        return
    except retryable_error as initial_error:
        last_error: BaseException = initial_error

    login_entries = context_page.locator(login_entry_selector)
    for scan_attempt in range(entry_scan_attempts):
        try:
            entry_count = await login_entries.count()
        except retryable_error as error:
            last_error = error
            entry_count = 0

        for index in range(entry_count):
            entry = login_entries.nth(index)
            try:
                if not await entry.is_visible():
                    continue
                if click_entry is None:
                    await entry.click(timeout=click_timeout_ms)
                else:
                    await click_entry(entry, click_timeout_ms)
                await context_page.wait_for_selector(
                    qrcode_selector,
                    state="visible",
                    timeout=qrcode_timeout_ms,
                )
                print(
                    f"[MediaOps] Opened {platform_name} QR-code login through "
                    "a visible reviewed entry",
                    flush=True,
                )
                return
            except retryable_error as error:
                last_error = error

        if (
            scan_attempt + 1 < entry_scan_attempts
            and entry_scan_delay_seconds > 0
        ):
            await asyncio.sleep(entry_scan_delay_seconds)

    raise RuntimeError(
        f"{platform_name} QR-code login entry was not visible or did not "
        "expose a QR code"
    ) from last_error


async def open_weibo_qrcode_entry(
    context_page: object,
    retryable_error: type[BaseException],
    *,
    qrcode_selector: str = WEIBO_QRCODE_SELECTOR,
    initial_timeout_ms: int = 1_000,
    qrcode_timeout_ms: int = 10_000,
    click_timeout_ms: int = 5_000,
    entry_scan_attempts: int = WEIBO_QRCODE_ENTRY_SCAN_ATTEMPTS,
    entry_scan_delay_seconds: float = WEIBO_QRCODE_ENTRY_SCAN_DELAY_SECONDS,
) -> None:
    """Expose Weibo's QR code when its mobile-UA login page hides it."""
    await open_qrcode_entry(
        context_page,
        retryable_error,
        platform_name="Weibo",
        qrcode_selector=qrcode_selector,
        login_entry_selector=WEIBO_QRCODE_ENTRY_SELECTOR,
        initial_timeout_ms=initial_timeout_ms,
        qrcode_timeout_ms=qrcode_timeout_ms,
        click_timeout_ms=click_timeout_ms,
        entry_scan_attempts=entry_scan_attempts,
        entry_scan_delay_seconds=entry_scan_delay_seconds,
    )


def install_weibo_qrcode_entry_patch() -> None:
    """Patch the reviewed Weibo QR-login seam, never MediaCrawler source."""
    from playwright.async_api import Error as PlaywrightError
    from tools import utils as crawler_utils

    original_find_login_qrcode = crawler_utils.find_login_qrcode

    async def find_login_qrcode_with_entry(
        context_page: object,
        selector: str,
    ) -> str:
        await open_weibo_qrcode_entry(
            context_page,
            PlaywrightError,
            qrcode_selector=selector,
        )
        return await original_find_login_qrcode(context_page, selector)

    crawler_utils.find_login_qrcode = find_login_qrcode_with_entry


async def navigate_tieba_with_https(
    crawler: object,
    original_navigation: Callable[[object], Awaitable[None]],
) -> None:
    """Recover the upstream HTTP Tieba link before login or collection."""
    await original_navigation(crawler)
    context_page = getattr(crawler, "context_page", None)
    if context_page is None:
        raise RuntimeError("Tieba crawler has no context page")

    current_title = await context_page.title()
    needs_https_recovery = (
        str(getattr(context_page, "url", "")).startswith("http://")
        or TIEBA_SECURITY_VERIFICATION_TITLE in current_title
    )
    if not needs_https_recovery:
        return

    print(
        "[MediaOps] Recovering Tieba navigation through the HTTPS homepage",
        flush=True,
    )
    await context_page.goto(
        TIEBA_INDEX_URL,
        wait_until="domcontentloaded",
        timeout=30_000,
        referer=BAIDU_INDEX_URL,
    )
    recovered_title = await context_page.title()
    if TIEBA_SECURITY_VERIFICATION_TITLE in recovered_title:
        print(
            "[MediaOps] captcha required: Tieba security verification "
            "persisted after HTTPS recovery",
            flush=True,
        )
        raise RuntimeError(
            "Tieba security verification persisted after HTTPS recovery"
        )


async def open_tieba_qrcode_entry(
    context_page: object,
    retryable_error: type[BaseException],
    *,
    qrcode_selector: str = TIEBA_QRCODE_SELECTOR,
    initial_timeout_ms: int = 1_000,
    qrcode_timeout_ms: int = 10_000,
    click_timeout_ms: int = 5_000,
    entry_scan_attempts: int = TIEBA_LOGIN_ENTRY_SCAN_ATTEMPTS,
    entry_scan_delay_seconds: float = TIEBA_LOGIN_ENTRY_SCAN_DELAY_SECONDS,
) -> None:
    """Open the current or legacy Tieba login entry before upstream waits."""
    await open_qrcode_entry(
        context_page,
        retryable_error,
        platform_name="Tieba",
        qrcode_selector=qrcode_selector,
        login_entry_selector=TIEBA_LOGIN_ENTRY_SELECTOR,
        initial_timeout_ms=initial_timeout_ms,
        qrcode_timeout_ms=qrcode_timeout_ms,
        click_timeout_ms=click_timeout_ms,
        entry_scan_attempts=entry_scan_attempts,
        entry_scan_delay_seconds=entry_scan_delay_seconds,
    )


def install_tieba_runtime_patch() -> None:
    """Patch reviewed Tieba navigation/login seams, never upstream source."""
    from media_platform.tieba.core import TieBaCrawler
    from playwright.async_api import Error as PlaywrightError
    from tools import utils as crawler_utils

    original_navigation = TieBaCrawler._navigate_to_tieba_via_baidu
    original_find_login_qrcode = crawler_utils.find_login_qrcode

    async def navigate_with_https(crawler: object) -> None:
        await navigate_tieba_with_https(crawler, original_navigation)

    async def find_login_qrcode_with_entry(
        context_page: object,
        selector: str,
    ) -> str:
        await open_tieba_qrcode_entry(
            context_page,
            PlaywrightError,
            qrcode_selector=selector,
        )
        return await original_find_login_qrcode(context_page, selector)

    TieBaCrawler._navigate_to_tieba_via_baidu = navigate_with_https
    crawler_utils.find_login_qrcode = find_login_qrcode_with_entry


async def _click_kuaishou_login_entry(
    entry: object,
    timeout_ms: int,
) -> None:
    """Dispatch the exact login entry after a transparent overlay intercept."""
    async with asyncio.timeout(timeout_ms / 1_000):
        await entry.evaluate("element => element.click()")


async def open_kuaishou_qrcode_entry(
    context_page: object,
    retryable_error: type[BaseException],
    *,
    qrcode_selector: str = KUAISHOU_QRCODE_SELECTOR,
    initial_timeout_ms: int = 1_000,
    qrcode_timeout_ms: int = 10_000,
    click_timeout_ms: int = 5_000,
    entry_scan_attempts: int = KUAISHOU_LOGIN_ENTRY_SCAN_ATTEMPTS,
    entry_scan_delay_seconds: float = KUAISHOU_LOGIN_ENTRY_SCAN_DELAY_SECONDS,
) -> None:
    """Expose Kuaishou's QR code despite its transparent click interceptor."""
    await open_qrcode_entry(
        context_page,
        retryable_error,
        platform_name="Kuaishou",
        qrcode_selector=qrcode_selector,
        login_entry_selector=KUAISHOU_LOGIN_ENTRY_SELECTOR,
        initial_timeout_ms=initial_timeout_ms,
        qrcode_timeout_ms=qrcode_timeout_ms,
        click_timeout_ms=click_timeout_ms,
        entry_scan_attempts=entry_scan_attempts,
        entry_scan_delay_seconds=entry_scan_delay_seconds,
        click_entry=_click_kuaishou_login_entry,
    )


class KuaishouOpenedLoginEntry:
    """Keep upstream's redundant click from landing on the page overlay."""

    def __init__(self, locator: object) -> None:
        self._locator = locator

    async def click(self, *args: object, **kwargs: object) -> None:
        return None

    def __getattr__(self, name: str) -> object:
        return getattr(self._locator, name)


class KuaishouLoginPage:
    """Delegate the Page API except for the already-opened login entry."""

    def __init__(self, page: object) -> None:
        self._page = page

    def locator(self, selector: str, *args: object, **kwargs: object) -> object:
        locator = self._page.locator(selector, *args, **kwargs)
        if selector == KUAISHOU_LOGIN_ENTRY_SELECTOR:
            return KuaishouOpenedLoginEntry(locator)
        return locator

    def __getattr__(self, name: str) -> object:
        return getattr(self._page, name)


def install_kuaishou_qrcode_entry_patch() -> None:
    """Patch the reviewed Kuaishou QR-login seam, never upstream source."""
    from media_platform.kuaishou.login import KuaishouLogin
    from playwright.async_api import Error as PlaywrightError

    original_login_by_qrcode = KuaishouLogin.login_by_qrcode

    async def login_by_qrcode_after_opening_entry(login: object) -> None:
        context_page = getattr(login, "context_page", None)
        if context_page is None:
            raise RuntimeError("Kuaishou login has no context page")
        await open_kuaishou_qrcode_entry(context_page, PlaywrightError)
        login.context_page = KuaishouLoginPage(context_page)
        try:
            await original_login_by_qrcode(login)
        finally:
            login.context_page = context_page

    KuaishouLogin.login_by_qrcode = login_by_qrcode_after_opening_entry


async def search_kuaishou_with_result_guard(
    client: object,
    keyword: str,
    pcursor: str,
    search_session_id: str,
    original_search: Callable[..., Awaitable[object]],
) -> object:
    """Reject upstream search-contract drift instead of producing false success."""
    response = await original_search(
        client,
        keyword,
        pcursor,
        search_session_id,
    )
    search_result = (
        response.get("visionSearchPhoto") if isinstance(response, dict) else None
    )
    feeds = (
        search_result.get("feeds")
        if isinstance(search_result, dict)
        else None
    )
    if (
        not isinstance(search_result, dict)
        or search_result.get("result") != 1
        or not isinstance(feeds, list)
        or not feeds
    ):
        result_code = (
            search_result.get("result")
            if isinstance(search_result, dict)
            else None
        )
        feed_count = len(feeds) if isinstance(feeds, list) else 0
        print(
            "[MediaOps] Kuaishou upstream search contract unavailable: "
            f"result={result_code!r}, feeds={feed_count}",
            flush=True,
        )
        raise RuntimeError(
            "Kuaishou upstream search returned no usable results"
        )
    return response


def install_kuaishou_search_guard() -> None:
    """Fail closed when the pinned Kuaishou GraphQL search contract drifts."""
    from media_platform.kuaishou.client import KuaiShouClient

    original_search = KuaiShouClient.search_info_by_keyword

    async def guarded_search(
        client: object,
        keyword: str,
        pcursor: str,
        search_session_id: str = "",
    ) -> object:
        return await search_kuaishou_with_result_guard(
            client,
            keyword,
            pcursor,
            search_session_id,
            original_search,
        )

    KuaiShouClient.search_info_by_keyword = guarded_search


def create_login_state_observer(
    platform: str,
    original_probe: Callable[..., Awaitable[bool]],
) -> Callable[..., Awaitable[bool]]:
    async def observed_probe(client: object, *args: object, **kwargs: object) -> bool:
        ready = await original_probe(client, *args, **kwargs)
        if ready:
            print(
                f"[MediaOps] Existing login state ready: {platform}",
                flush=True,
            )
        return ready

    return observed_probe


def xhs_auth_cookie_fingerprint(cookies: object) -> str:
    """Hash XHS auth-cookie metadata without retaining or logging values."""
    if not isinstance(cookies, list):
        return ""
    entries: list[str] = []
    for cookie in cookies:
        if not isinstance(cookie, dict):
            continue
        name = cookie.get("name")
        if not isinstance(name, str) or name not in XHS_AUTH_COOKIE_NAMES:
            continue
        domain = cookie.get("domain")
        path = cookie.get("path")
        value = cookie.get("value")
        if not all(isinstance(item, str) for item in (domain, path, value)):
            continue
        entries.append(f"{name}\x00{domain}\x00{path}\x00{value}")
    digest = hashlib.sha256()
    for entry in sorted(entries):
        digest.update(entry.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


async def _xhs_browser_auth_cookie_fingerprint(browser_context: object) -> str:
    cookies = await browser_context.cookies()
    return xhs_auth_cookie_fingerprint(cookies)


def install_xhs_login_state_patch() -> None:
    """Accept XHS auth-cookie rotation after QR secondary verification.

    The pinned upstream login helper only treats a changed ``web_session`` or
    one exact profile selector as success. XHS can rotate another auth cookie
    after a QR scan plus phone verification while leaving that selector
    unavailable in the headless page. Keep the upstream single-attempt probe,
    then add a bounded, value-free cookie-fingerprint check.
    """
    from media_platform.xhs.login import XiaoHongShuLogin

    if getattr(XiaoHongShuLogin, "_mediaops_login_state_patch", False):
        return

    upstream_check = XiaoHongShuLogin.check_login_state
    single_attempt = getattr(upstream_check, "__wrapped__", upstream_check)

    async def check_login_state(
        login: object,
        no_logged_in_session: str,
    ) -> bool:
        baseline = getattr(login, "_mediaops_xhs_auth_cookie_fingerprint", None)
        if baseline is None:
            baseline = await _xhs_browser_auth_cookie_fingerprint(
                login.browser_context
            )
            login._mediaops_xhs_auth_cookie_fingerprint = baseline

        for _ in range(600):
            current = await _xhs_browser_auth_cookie_fingerprint(
                login.browser_context
            )
            if current and current != baseline:
                print(
                    "[MediaOps] XHS login successful after auth cookie rotation",
                    flush=True,
                )
                return True

            try:
                upstream_ready = await asyncio.wait_for(
                    single_attempt(login, no_logged_in_session),
                    timeout=XHS_LOGIN_STATE_PROBE_TIMEOUT_SECONDS,
                )
            except Exception as probe_error:  # noqa: BLE001
                # The upstream probe includes an unbounded page-content read on
                # some XHS verification pages. Cookie rotation remains the
                # authoritative signal for this QR flow, so a probe failure
                # must not prevent the next bounded rotation check.
                upstream_ready = False
                del probe_error
            if upstream_ready:
                return True

            current = await _xhs_browser_auth_cookie_fingerprint(
                login.browser_context
            )
            if current and current != baseline:
                print(
                    "[MediaOps] XHS login successful after auth cookie rotation",
                    flush=True,
                )
                return True
            await asyncio.sleep(1)

        print(
            "[MediaOps] XHS login timeout while waiting for QR verification",
            flush=True,
        )
        raise RuntimeError("XHS QR login timed out")

    XiaoHongShuLogin.check_login_state = check_login_state
    XiaoHongShuLogin._mediaops_login_state_patch = True


def install_login_state_observer(platform: str) -> None:
    module_name, class_name = LOGIN_STATE_CLIENTS[platform]
    client_module = importlib.import_module(module_name)
    client_class = getattr(client_module, class_name)
    client_class.pong = create_login_state_observer(platform, client_class.pong)


def _json_object(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        value = value.model_dump(exclude_unset=True)
    if not isinstance(value, dict):
        raise TypeError("creator profile response is not an object")
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    parsed = json.loads(serialized)
    if not isinstance(parsed, dict):
        raise TypeError("creator profile response is not JSON-compatible")
    return parsed


def _creator_target_identity(args: argparse.Namespace, target: str) -> str:
    if target in args.creator_id:
        return target
    parsed = urlparse(target)
    query = parse_qs(parsed.query)
    if args.platform == "tieba" and query.get("id"):
        return query["id"][0]
    path_identity = parsed.path.rstrip("/").split("/")[-1]
    return path_identity or target


def _nested_profile_value(
    profile: dict[str, object],
    *paths: tuple[str, ...],
) -> object | None:
    for path in paths:
        current: object = profile
        for part in path:
            if not isinstance(current, dict) or part not in current:
                break
            current = current[part]
        else:
            if current is not None and current != "":
                return current
    return None


def _interaction_metric(
    profile: dict[str, object],
    *names: str,
) -> object | None:
    interactions = _nested_profile_value(
        profile,
        ("interactions",),
        ("interaction_info",),
    )
    if not isinstance(interactions, list):
        return None
    normalized_names = {name.casefold() for name in names}
    for item in interactions:
        if not isinstance(item, dict):
            continue
        metric_name = str(
            item.get("type")
            or item.get("name")
            or item.get("key")
            or ""
        ).casefold()
        if metric_name not in normalized_names:
            continue
        value = item.get("count")
        if value is None:
            value = item.get("value")
        if value is not None and value != "":
            return value
    return None


def sanitize_creator_profile(
    args: argparse.Namespace,
    *,
    target: str,
    profile: object,
) -> dict[str, object]:
    """Keep only MediaCrawler teaching edition privacy-safe creator fields."""
    from tools.user_hash import anonymize_user_id, mask_nickname

    raw = _json_object(profile)
    source_creator_id = _nested_profile_value(raw, ("creator_hash",))
    if source_creator_id is None:
        source_creator_id = anonymize_user_id(
            _creator_target_identity(args, target)
        )
    else:
        source_creator_id = str(source_creator_id)
    if not source_creator_id:
        raise RuntimeError("creator profile has no privacy-safe identity")

    nickname = _nested_profile_value(
        raw,
        ("user_nickname",),
        ("nickname",),
        ("name",),
        ("screen_name",),
        ("user_name",),
        ("basicInfo", "nickname"),
        ("basic_info", "nickname"),
        ("profile", "user_name"),
    )
    followers = _nested_profile_value(
        raw,
        ("fans",),
        ("follower_count",),
        ("followers_count",),
        ("ownerCount", "fan"),
        ("owner_count", "fan"),
    )
    if followers is None:
        followers = _interaction_metric(raw, "fans", "followers")
    following = _nested_profile_value(
        raw,
        ("follows",),
        ("following_count",),
        ("follow_count",),
        ("ownerCount", "follow"),
        ("owner_count", "follow"),
    )
    if following is None:
        following = _interaction_metric(raw, "follows", "following")
    content_count = _nested_profile_value(
        raw,
        ("content_count",),
        ("notes",),
        ("statuses_count",),
        ("ownerCount", "photo"),
        ("owner_count", "photo"),
    )

    sanitized: dict[str, object] = {
        "_mediaops_source_creator_id": source_creator_id,
        "creator_hash": source_creator_id,
    }
    if nickname is not None:
        sanitized["user_nickname"] = mask_nickname(nickname)
    if followers is not None:
        sanitized["fans"] = followers
    if following is not None:
        sanitized["follows"] = following
    if content_count is not None:
        sanitized["content_count"] = content_count

    for field in (
        "anwser_count",
        "video_count",
        "question_count",
        "article_count",
        "column_count",
        "get_voteup_count",
        "registration_duration",
    ):
        value = raw.get(field)
        if value is not None and value != "":
            sanitized[field] = value
    return sanitized


def _creator_output_path(args: argparse.Namespace) -> Path:
    storage_directory = PLATFORM_STORAGE_DIRECTORIES[args.platform]
    jsonl_root = args.output_dir / storage_directory / "jsonl"
    jsonl_root.mkdir(parents=True, exist_ok=True)
    date = datetime.now(UTC).strftime("%Y-%m-%d")
    return jsonl_root / f"creator_creators_{date}.jsonl"


def capture_creator_profile(
    args: argparse.Namespace,
    *,
    target: str,
    profile: object,
) -> None:
    payload = sanitize_creator_profile(
        args,
        target=target,
        profile=profile,
    )
    with _creator_output_path(args).open("a", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def install_creator_mode_patch(args: argparse.Namespace) -> None:
    """Collect one bounded public profile per requested creator target."""
    if args.crawler_type != "creator":
        return
    targets = [*args.creator_id, *args.creator_url]

    if args.platform == "bili":
        from media_platform.bilibili.core import BilibiliCrawler

        async def get_creator_profile_only(crawler: object, creator_id: int) -> None:
            profile = await crawler.bili_client.get_creator_info(creator_id)
            capture_creator_profile(args, target=str(creator_id), profile=profile)

        BilibiliCrawler.get_creator_videos = get_creator_profile_only
        return

    if args.platform == "xhs":
        from media_platform.xhs.core import XiaoHongShuCrawler
        from media_platform.xhs.help import parse_creator_info_from_url

        async def get_xhs_creator_profiles(crawler: object) -> None:
            for target in targets:
                creator = parse_creator_info_from_url(target)
                profile = await crawler.xhs_client.get_creator_info(
                    user_id=creator.user_id,
                    xsec_token=creator.xsec_token,
                    xsec_source=creator.xsec_source,
                )
                capture_creator_profile(args, target=target, profile=profile)

        XiaoHongShuCrawler.get_creators_and_notes = get_xhs_creator_profiles
        return

    if args.platform == "zhihu":
        from media_platform.zhihu.core import ZhihuCrawler

        async def get_zhihu_creator_profiles(crawler: object) -> None:
            for target in targets:
                token = urlparse(target).path.rstrip("/").split("/")[-1]
                profile = await crawler.zhihu_client.get_creator_info(
                    url_token=token
                )
                if profile is None:
                    raise RuntimeError("Zhihu creator profile was not found")
                capture_creator_profile(args, target=target, profile=profile)

        ZhihuCrawler.get_creators_and_notes = get_zhihu_creator_profiles
        return

    if args.platform == "wb":
        from media_platform.weibo.core import WeiboCrawler

        async def get_weibo_creator_profiles(crawler: object) -> None:
            for target in targets:
                creator_id = _creator_target_identity(args, target)
                response = await crawler.wb_client.get_creator_info_by_id(
                    creator_id=creator_id
                )
                profile = response.get("userInfo") if isinstance(response, dict) else None
                if not profile:
                    raise RuntimeError("Weibo creator profile was not found")
                capture_creator_profile(args, target=target, profile=profile)

        WeiboCrawler.get_creators_and_notes = get_weibo_creator_profiles
        return

    if args.platform == "tieba":
        from media_platform.tieba.core import TieBaCrawler

        async def get_tieba_creator_profiles(crawler: object) -> None:
            for target in targets:
                creator_url = (
                    target
                    if target in args.creator_url
                    else f"https://tieba.baidu.com/home/main?id={target}"
                )
                profile = await crawler.tieba_client.get_creator_info_by_url(
                    creator_url=creator_url
                )
                if profile is None:
                    raise RuntimeError("Tieba creator profile was not found")
                capture_creator_profile(args, target=target, profile=profile)

        TieBaCrawler.get_creators_and_notes = get_tieba_creator_profiles
        return

    if args.platform == "ks":
        from media_platform.kuaishou.core import KuaishouCrawler

        async def get_kuaishou_creator_profiles(crawler: object) -> None:
            for target in targets:
                creator_id = _creator_target_identity(args, target)
                profile = await crawler.ks_client.get_creator_info(
                    user_id=creator_id
                )
                if not profile:
                    raise RuntimeError("Kuaishou creator profile was not found")
                capture_creator_profile(args, target=target, profile=profile)

        KuaishouCrawler.get_creators_and_videos = get_kuaishou_creator_profiles


def _content_target(args: argparse.Namespace) -> str:
    targets = [
        *args.target_id,
        *args.target_url,
        *([args.parent_content_id] if args.parent_content_id else []),
    ]
    if len(targets) != 1:
        raise RuntimeError("standalone comment mode requires one content target")
    return targets[0]


def bilibili_video_identity(target: str) -> tuple[int, str]:
    parsed = urlparse(target)
    candidate = parsed.path.rstrip("/").split("/")[-1] if parsed.netloc else target
    if candidate.startswith("BV") and re.fullmatch(r"BV[a-zA-Z0-9]+", candidate):
        return 0, candidate
    aid_text = candidate.removeprefix("av")
    if aid_text.isdigit() and int(aid_text) > 0:
        return int(aid_text), ""
    raise ValueError("Bilibili content target must contain an AV or BV ID")


def install_bilibili_av_target_patch(args: argparse.Namespace) -> None:
    """Teach the pinned BV-only detail parser to use public AV IDs safely."""
    if args.platform != "bili" or args.crawler_type not in {"detail", "comments"}:
        return

    import media_platform.bilibili.core as bilibili_core
    from model.m_bilibili import VideoUrlInfo

    original_get_video_info_task = (
        bilibili_core.BilibiliCrawler.get_video_info_task
    )

    def parse_video_target(target: str) -> object:
        aid, bvid = bilibili_video_identity(target)
        return VideoUrlInfo(video_id=bvid or str(aid))

    async def get_video_info_task(
        crawler: object,
        aid: int,
        bvid: str,
        semaphore: asyncio.Semaphore,
    ) -> object:
        if not aid and bvid.isdigit():
            aid, bvid = int(bvid), ""
        return await original_get_video_info_task(
            crawler,
            aid,
            bvid,
            semaphore,
        )

    bilibili_core.parse_video_info_from_url = parse_video_target
    bilibili_core.BilibiliCrawler.get_video_info_task = get_video_info_task


def upstream_content_targets(args: argparse.Namespace) -> list[str]:
    targets = [
        *args.target_id,
        *args.target_url,
        *([args.parent_content_id] if args.parent_content_id else []),
    ]
    if args.platform == "bili":
        normalized: list[str] = []
        for target in targets:
            if target in args.target_url:
                normalized.append(target)
                continue
            video_id = target if target.startswith(("av", "BV")) else f"av{target}"
            normalized.append(f"https://www.bilibili.com/video/{video_id}")
        return normalized
    if args.platform != "wb":
        return targets
    normalized: list[str] = []
    for target in targets:
        if target in args.target_url:
            note_id = urlparse(target).path.rstrip("/").split("/")[-1]
            if not note_id:
                raise RuntimeError("Weibo target URL does not contain a note ID")
            normalized.append(note_id)
        else:
            normalized.append(target)
    return normalized


def install_sub_comment_mode_patch(args: argparse.Namespace) -> None:
    """Use only bounded direct client APIs for standalone sub-comments."""
    if args.crawler_type != "sub_comments":
        return
    target = _content_target(args)
    parent_comment_id = args.parent_comment_id
    maximum = args.requested_sub_comment_count
    if parent_comment_id is None:
        raise RuntimeError("sub-comment mode is missing its parent comment ID")

    if args.platform == "bili":
        from media_platform.bilibili.core import BilibiliCrawler
        from media_platform.bilibili.field import CommentOrderType
        from media_platform.bilibili.help import parse_video_info_from_url
        from store import bilibili as bilibili_store

        async def get_bilibili_sub_comments(
            crawler: object,
            _: object,
        ) -> None:
            aid, bvid = bilibili_video_identity(target)
            if not aid:
                detail = await crawler.bili_client.get_video_info(
                    aid=None,
                    bvid=parse_video_info_from_url(bvid).video_id,
                )
                view = detail.get("View") if isinstance(detail, dict) else None
                aid = int(view.get("aid", 0)) if isinstance(view, dict) else 0
                if not aid:
                    raise RuntimeError("Bilibili content AV ID was not found")
            video_id = str(aid)
            result = await crawler.bili_client.get_video_level_two_comments(
                video_id,
                int(parent_comment_id),
                1,
                maximum,
                CommentOrderType.DEFAULT,
            )
            comments = result.get("replies", []) if isinstance(result, dict) else []
            await bilibili_store.batch_update_bilibili_video_comments(
                video_id,
                comments[:maximum],
            )

        BilibiliCrawler.get_specified_videos = get_bilibili_sub_comments
        return

    if args.platform == "xhs":
        from media_platform.xhs.core import XiaoHongShuCrawler
        from media_platform.xhs.help import parse_note_info_from_note_url
        from store import xhs as xhs_store

        async def get_xhs_sub_comments(crawler: object) -> None:
            note = parse_note_info_from_note_url(target)
            result = await crawler.xhs_client.get_note_sub_comments(
                note.note_id,
                parent_comment_id,
                note.xsec_token,
                num=maximum,
            )
            comments = result.get("comments", []) if isinstance(result, dict) else []
            await xhs_store.batch_update_xhs_note_comments(
                note.note_id,
                comments[:maximum],
            )

        XiaoHongShuCrawler.get_specified_notes = get_xhs_sub_comments
        return

    if args.platform == "zhihu":
        from media_platform.zhihu.core import ZhihuCrawler
        from store import zhihu as zhihu_store

        async def get_zhihu_sub_comments(crawler: object) -> None:
            content = await crawler.get_note_detail(
                full_note_url=target,
                semaphore=asyncio.Semaphore(1),
            )
            if content is None:
                raise RuntimeError("Zhihu content context was not found")
            result = await crawler.zhihu_client.get_child_comments(
                parent_comment_id,
                limit=maximum,
            )
            comments = crawler.zhihu_client._extractor.extract_comments(
                content,
                result.get("data", []) if isinstance(result, dict) else [],
            )
            await zhihu_store.batch_update_zhihu_note_comments(
                comments[:maximum]
            )

        ZhihuCrawler.get_specified_notes = get_zhihu_sub_comments
        return

    if args.platform == "ks":
        from media_platform.kuaishou.core import KuaishouCrawler
        from media_platform.kuaishou.help import parse_video_info_from_url
        from store import kuaishou as kuaishou_store

        async def get_kuaishou_sub_comments(crawler: object) -> None:
            video_id = parse_video_info_from_url(target).video_id
            result = await crawler.ks_client.get_video_sub_comments(
                video_id,
                int(parent_comment_id),
            )
            comments = (
                result.get("subCommentsV2", []) if isinstance(result, dict) else []
            )
            await kuaishou_store.batch_update_ks_video_comments(
                video_id,
                comments[:maximum],
            )

        KuaishouCrawler.get_specified_videos = get_kuaishou_sub_comments
        return

    raise RuntimeError(
        f"standalone sub-comments are unavailable for platform {args.platform}"
    )


def main() -> None:
    args = parse_arguments()
    ensure_virtual_display(args.headless)
    lower_platform_process_priority(args.platform)
    if not MEDIACRAWLER_ROOT.is_dir():
        raise SystemExit(f"MediaCrawler root does not exist: {MEDIACRAWLER_ROOT}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.qrcode_path.parent.mkdir(parents=True, exist_ok=True)
    args.qrcode_path.unlink(missing_ok=True)
    configure_node_runtime()

    os.chdir(MEDIACRAWLER_ROOT)
    sys.path.insert(0, str(MEDIACRAWLER_ROOT))

    import config

    config.ENABLE_CDP_MODE = False
    config.CDP_CONNECT_EXISTING = False
    config.HEADLESS = args.headless
    config.CDP_HEADLESS = args.headless
    config.MAX_CONCURRENCY_NUM = 1
    config.CRAWLER_MAX_NOTES_COUNT = args.requested_count
    config.CRAWLER_MAX_COMMENTS_COUNT_SINGLENOTES = (
        args.requested_comment_count
    )
    config.ENABLE_GET_COMMENTS = args.crawler_type == "comments"
    config.ENABLE_GET_SUB_COMMENTS = False
    config.ENABLE_IP_PROXY = False
    if hasattr(config, "ENABLE_GET_MEDIAS"):
        config.ENABLE_GET_MEDIAS = False
    if hasattr(config, "ENABLE_GET_MEIDAS"):
        config.ENABLE_GET_MEIDAS = False
    config.SAVE_DATA_OPTION = "jsonl"
    config.SAVE_DATA_PATH = str(args.output_dir)

    from PIL import Image, ImageDraw
    from tools import utils as crawler_utils

    def save_qrcode(qr_code: str) -> None:
        encoded = qr_code.split(",", 1)[1] if "," in qr_code else qr_code
        image_bytes = base64.b64decode(encoded)
        image = Image.open(BytesIO(image_bytes)).convert("RGB")
        width, height = image.size
        bordered = Image.new(
            "RGB",
            (width + 20, height + 20),
            color=(255, 255, 255),
        )
        bordered.paste(image, (10, 10))
        draw = ImageDraw.Draw(bordered)
        draw.rectangle(
            (0, 0, width + 19, height + 19),
            outline=(0, 0, 0),
            width=1,
        )

        temporary_path = args.qrcode_path.with_suffix(".png.tmp")
        bordered.save(temporary_path, format="PNG")
        os.replace(temporary_path, args.qrcode_path)
        print(
            f"[MediaOps] QR code saved: {args.qrcode_path}",
            flush=True,
        )

    crawler_utils.show_qrcode = save_qrcode
    install_login_state_observer(args.platform)
    if args.platform == "xhs":
        install_xhs_login_state_patch()
    upstream_type = (
        args.crawler_type
        if args.crawler_type in NATIVE_CRAWLER_TYPES
        else "detail"
    )
    sys.argv = [
        str(MEDIACRAWLER_ROOT / "main.py"),
        "--platform",
        args.platform,
        "--type",
        upstream_type,
        "--lt",
        args.login_type,
        "--crawler_max_notes_count",
        str(args.requested_count),
        "--max_concurrency_num",
        "1",
        "--get_comment",
        "true" if args.crawler_type == "comments" else "false",
        "--get_sub_comment",
        "false",
        "--max_comments_count_singlenotes",
        str(args.requested_comment_count),
        "--enable_ip_proxy",
        "false",
        "--headless",
        "true" if args.headless else "false",
        "--save_data_option",
        "jsonl",
        "--save_data_path",
        str(args.output_dir),
    ]
    if args.keywords:
        sys.argv.extend(["--keywords", args.keywords])
    content_targets = upstream_content_targets(args)
    if content_targets:
        sys.argv.extend(["--specified_id", ",".join(content_targets)])
    creator_targets = [*args.creator_id, *args.creator_url]
    if creator_targets:
        sys.argv.extend(["--creator_id", ",".join(creator_targets)])
        if args.platform == "zhihu":
            config.ZHIHU_CREATOR_URL_LIST = creator_targets
    if args.platform == "dy":
        install_douyin_navigation_retry()
    if args.platform == "wb":
        install_weibo_qrcode_entry_patch()
    if args.platform == "tieba":
        install_tieba_runtime_patch()
    if args.platform == "ks":
        install_kuaishou_qrcode_entry_patch()
        if args.crawler_type == "search":
            install_kuaishou_search_guard()
    install_bilibili_av_target_patch(args)
    install_creator_mode_patch(args)
    install_sub_comment_mode_patch(args)
    runpy.run_path(
        str(MEDIACRAWLER_ROOT / "main.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
