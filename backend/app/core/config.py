import math
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    frontend_origins: tuple[str, ...]
    database_path: Path
    mediacrawler_python: Path
    mediacrawler_runner: Path
    output_root: Path
    log_root: Path
    qrcode_root: Path
    node_binary: Path | None
    node_bin_dir: Path | None
    crawler_poll_interval_seconds: float
    douyin_qrcode_startup_timeout_seconds: float
    enabled_platforms: tuple[str, ...]
    secure_session_cookie: bool = False
    session_lifetime_seconds: int = 7 * 24 * 60 * 60
    login_failure_limit: int = 5
    login_lockout_seconds: int = 15 * 60
    max_owner_accounts: int = 3
    automation_poll_interval_seconds: float = 30
    ai_provider: str = "disabled"

    @classmethod
    def from_environment(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
            if origin.strip()
        )
        node_binary = os.getenv("MEDIAOPS_NODE_BINARY")
        node_bin_dir = os.getenv("MEDIAOPS_NODE_BIN_DIR")
        poll_interval = float(os.getenv("CRAWLER_POLL_INTERVAL_SECONDS", "1"))
        if poll_interval <= 0:
            raise ValueError("CRAWLER_POLL_INTERVAL_SECONDS must be greater than zero")
        douyin_qrcode_startup_timeout = float(
            os.getenv("DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS", "180")
        )
        if (
            not math.isfinite(douyin_qrcode_startup_timeout)
            or douyin_qrcode_startup_timeout <= 0
        ):
            raise ValueError(
                "DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS must be a finite number "
                "greater than zero"
            )
        enabled_platforms = tuple(
            dict.fromkeys(
                platform.strip()
                for platform in os.getenv(
                    "MEDIAOPS_ENABLED_PLATFORMS",
                    "bili",
                ).split(",")
                if platform.strip()
            )
        )
        if not enabled_platforms:
            raise ValueError("MEDIAOPS_ENABLED_PLATFORMS must not be empty")
        session_lifetime = int(
            os.getenv("MEDIAOPS_SESSION_LIFETIME_SECONDS", str(7 * 24 * 60 * 60))
        )
        login_failure_limit = int(os.getenv("MEDIAOPS_LOGIN_FAILURE_LIMIT", "5"))
        login_lockout = int(os.getenv("MEDIAOPS_LOGIN_LOCKOUT_SECONDS", "900"))
        max_owner_accounts = int(os.getenv("MEDIAOPS_MAX_OWNER_ACCOUNTS", "3"))
        automation_poll_interval = float(
            os.getenv("MEDIAOPS_AUTOMATION_POLL_INTERVAL_SECONDS", "30")
        )
        if session_lifetime <= 0:
            raise ValueError("MEDIAOPS_SESSION_LIFETIME_SECONDS must be positive")
        if login_failure_limit < 2:
            raise ValueError("MEDIAOPS_LOGIN_FAILURE_LIMIT must be at least 2")
        if login_lockout <= 0:
            raise ValueError("MEDIAOPS_LOGIN_LOCKOUT_SECONDS must be positive")
        if not 1 <= max_owner_accounts <= 10:
            raise ValueError("MEDIAOPS_MAX_OWNER_ACCOUNTS must be between 1 and 10")
        if (
            not math.isfinite(automation_poll_interval)
            or automation_poll_interval < 5
        ):
            raise ValueError(
                "MEDIAOPS_AUTOMATION_POLL_INTERVAL_SECONDS must be at least 5"
            )
        ai_provider = os.getenv("MEDIAOPS_AI_PROVIDER", "disabled").strip()
        if ai_provider != "disabled":
            raise ValueError("MEDIAOPS_AI_PROVIDER must remain disabled")
        return cls(
            frontend_origins=origins,
            database_path=Path(
                os.getenv("MEDIAOPS_DATABASE_PATH", "/var/lib/mediaops/mediaops.db")
            ),
            mediacrawler_python=Path(
                os.getenv(
                    "MEDIACRAWLER_PYTHON",
                    "/opt/mediacrawler/.venv/bin/python",
                )
            ),
            mediacrawler_runner=Path(
                os.getenv(
                    "MEDIACRAWLER_RUNNER",
                    "/var/lib/mediaops/bin/run_mediacrawler.py",
                )
            ),
            output_root=Path(
                os.getenv(
                    "MEDIAOPS_OUTPUT_ROOT",
                    "/var/lib/mediaops/crawler-output",
                )
            ),
            log_root=Path(os.getenv("MEDIAOPS_LOG_ROOT", "/var/log/mediaops")),
            qrcode_root=Path(
                os.getenv(
                    "MEDIAOPS_QRCODE_ROOT",
                    "/var/lib/mediaops/qrcodes",
                )
            ),
            node_binary=Path(node_binary) if node_binary else None,
            node_bin_dir=Path(node_bin_dir) if node_bin_dir else None,
            crawler_poll_interval_seconds=poll_interval,
            douyin_qrcode_startup_timeout_seconds=(douyin_qrcode_startup_timeout),
            enabled_platforms=enabled_platforms,
            secure_session_cookie=(
                os.getenv("MEDIAOPS_SECURE_SESSION_COOKIE", "true").casefold()
                not in {"0", "false", "no"}
            ),
            session_lifetime_seconds=session_lifetime,
            login_failure_limit=login_failure_limit,
            login_lockout_seconds=login_lockout,
            max_owner_accounts=max_owner_accounts,
            automation_poll_interval_seconds=automation_poll_interval,
            ai_provider=ai_provider,
        )


settings = Settings.from_environment()
