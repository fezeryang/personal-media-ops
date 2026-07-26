import importlib.util
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
    ]


@pytest.mark.parametrize("platform", ["bili", "xhs", "dy"])
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


def test_runner_forces_mediacrawler_safety_flags() -> None:
    source = RUNNER_PATH.read_text(encoding="utf-8")

    assert '"--get_comment",\n        "false"' in source
    assert '"--get_sub_comment",\n        "false"' in source
    assert '"--enable_ip_proxy",\n        "false"' in source
    assert '"--max_concurrency_num",\n        "1"' in source
    assert "config.ENABLE_IP_PROXY = False" in source
