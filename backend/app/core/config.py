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
        )


settings = Settings.from_environment()
