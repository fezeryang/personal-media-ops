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


def test_douyin_qrcode_startup_timeout_defaults_to_three_minutes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS", raising=False)

    assert Settings.from_environment().douyin_qrcode_startup_timeout_seconds == 180


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf"])
def test_douyin_qrcode_startup_timeout_must_be_finite_and_positive(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS", value)

    with pytest.raises(
        ValueError,
        match=(
            "DOUYIN_QRCODE_STARTUP_TIMEOUT_SECONDS must be a finite number "
            "greater than zero"
        ),
    ):
        Settings.from_environment()
