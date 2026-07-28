from __future__ import annotations

import argparse
import asyncio
import base64
import importlib
import os
import runpy
import shutil
import sys
from collections.abc import Awaitable, Callable
from io import BytesIO
from pathlib import Path
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
        choices=["search"],
    )
    parser.add_argument("--keywords", required=True)
    parser.add_argument(
        "--login-type",
        required=True,
        choices=["qrcode"],
    )
    parser.add_argument("--requested-count", required=True, type=int)
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
    if args.enable_comments:
        parser.error("--enable-comments must be false")
    if args.enable_sub_comments:
        parser.error("--enable-sub-comments must be false")
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


def install_login_state_observer(platform: str) -> None:
    module_name, class_name = LOGIN_STATE_CLIENTS[platform]
    client_module = importlib.import_module(module_name)
    client_class = getattr(client_module, class_name)
    client_class.pong = create_login_state_observer(platform, client_class.pong)


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
    config.ENABLE_GET_COMMENTS = False
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
    sys.argv = [
        str(MEDIACRAWLER_ROOT / "main.py"),
        "--platform",
        args.platform,
        "--type",
        args.crawler_type,
        "--keywords",
        args.keywords,
        "--lt",
        args.login_type,
        "--crawler_max_notes_count",
        str(args.requested_count),
        "--max_concurrency_num",
        "1",
        "--get_comment",
        "false",
        "--get_sub_comment",
        "false",
        "--enable_ip_proxy",
        "false",
        "--headless",
        "true" if args.headless else "false",
        "--save_data_option",
        "jsonl",
        "--save_data_path",
        str(args.output_dir),
    ]
    if args.platform == "dy":
        install_douyin_navigation_retry()
    if args.platform == "wb":
        install_weibo_qrcode_entry_patch()
    if args.platform == "tieba":
        install_tieba_runtime_patch()
    if args.platform == "ks":
        install_kuaishou_qrcode_entry_patch()
    runpy.run_path(
        str(MEDIACRAWLER_ROOT / "main.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main()
