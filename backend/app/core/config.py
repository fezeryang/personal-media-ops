import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    frontend_origins: tuple[str, ...]

    @classmethod
    def from_environment(cls) -> "Settings":
        origins = tuple(
            origin.strip()
            for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
            if origin.strip()
        )
        return cls(frontend_origins=origins)


settings = Settings.from_environment()
