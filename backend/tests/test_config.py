import pytest

from app.core.config import Settings


def test_enabled_platforms_default_to_verified_bilibili(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MEDIAOPS_ENABLED_PLATFORMS", raising=False)

    assert Settings.from_environment().enabled_platforms == ("bili",)


def test_enabled_platforms_are_trimmed_and_deduplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "MEDIAOPS_ENABLED_PLATFORMS",
        "bili, xhs,bili,dy",
    )

    assert Settings.from_environment().enabled_platforms == (
        "bili",
        "xhs",
        "dy",
    )
