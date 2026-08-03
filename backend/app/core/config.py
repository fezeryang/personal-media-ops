import math
import os
from dataclasses import dataclass
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean")


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
    model_gateway_master_key_path: Path = Path(
        "/var/lib/mediaops/secrets/model-gateway-master.key"
    )
    model_gateway_max_connections: int = 20
    model_gateway_max_keepalive_connections: int = 10
    research_primary_enabled: bool = True
    discovery_inbox_enabled: bool = True
    legacy_today_visible: bool = False
    legacy_trends_visible: bool = False
    legacy_subscriptions_visible: bool = False
    legacy_creator_watch_visible: bool = False
    manual_crawler_primary: bool = False

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
        model_gateway_max_connections = int(
            os.getenv("MEDIAOPS_MODEL_GATEWAY_MAX_CONNECTIONS", "20")
        )
        model_gateway_max_keepalive = int(
            os.getenv("MEDIAOPS_MODEL_GATEWAY_MAX_KEEPALIVE_CONNECTIONS", "10")
        )
        if not 1 <= model_gateway_max_connections <= 100:
            raise ValueError(
                "MEDIAOPS_MODEL_GATEWAY_MAX_CONNECTIONS must be between 1 and 100"
            )
        if not 0 <= model_gateway_max_keepalive <= model_gateway_max_connections:
            raise ValueError(
                "MEDIAOPS_MODEL_GATEWAY_MAX_KEEPALIVE_CONNECTIONS must be between "
                "0 and MEDIAOPS_MODEL_GATEWAY_MAX_CONNECTIONS"
            )
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
            model_gateway_master_key_path=Path(
                os.getenv(
                    "MEDIAOPS_MODEL_GATEWAY_MASTER_KEY_PATH",
                    "/var/lib/mediaops/secrets/model-gateway-master.key",
                )
            ),
            model_gateway_max_connections=model_gateway_max_connections,
            model_gateway_max_keepalive_connections=model_gateway_max_keepalive,
            research_primary_enabled=_env_bool("MEDIAOPS_RESEARCH_PRIMARY_ENABLED", True),
            discovery_inbox_enabled=_env_bool("MEDIAOPS_DISCOVERY_INBOX_ENABLED", True),
            legacy_today_visible=_env_bool("MEDIAOPS_LEGACY_TODAY_VISIBLE", False),
            legacy_trends_visible=_env_bool("MEDIAOPS_LEGACY_TRENDS_VISIBLE", False),
            legacy_subscriptions_visible=_env_bool("MEDIAOPS_LEGACY_SUBSCRIPTIONS_VISIBLE", False),
            legacy_creator_watch_visible=_env_bool("MEDIAOPS_LEGACY_CREATOR_WATCH_VISIBLE", False),
            manual_crawler_primary=_env_bool("MEDIAOPS_MANUAL_CRAWLER_PRIMARY", False),
        )


settings = Settings.from_environment()
