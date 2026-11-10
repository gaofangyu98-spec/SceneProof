"""生成运行记录和 Mock 提供器测试。"""

from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sceneproof.cli import main
from sceneproof.ledger import (
    ManifestError,
    RunLedgerError,
    execute_run,
    load_manifest,
)
from sceneproof.media import probe_media
from sceneproof.models import GenerationManifest, ProviderRecord, RunStatus
from sceneproof.providers.base import ProviderError


class RecordingProvider:
    """测试用提供器，写入一个可校验的文本产物。"""

    def generate(
        self,
        manifest: GenerationManifest,
        artifact_dir: Path,
    ) -> ProviderRecord:
        (artifact_dir / "result.txt").write_text(manifest.script, encoding="utf-8")
        return ProviderRecord(
            name="recording",
            version="1.0.0",
            model=manifest.provider.model,
            model_version=manifest.provider.model_version,
        )


class FailingProvider:
    """测试用失败提供器。"""

    def generate(
        self,
        manifest: GenerationManifest,
        artifact_dir: Path,
    ) -> ProviderRecord:
        (artifact_dir / "partial.txt").write_text("partial", encoding="utf-8")
        raise ProviderError("模拟提供器失败")


def manifest_payload() -> dict[str, object]:
    return {
        "case_id": "ledger-test",
        "title": "运行记录测试",
        "script": "测试脚本",
        "scene_count": 1,
        "aspect_ratio": "16:9",
        "duration_seconds": 1.0,
        "language": "zh-CN",
        "provider": {
            "name": "recording",
            "version": "1.0.0",
            "model": "test-model",
            "model_version": "1",
            "seed": 7,
        },
    }


def build_manifest() -> GenerationManifest:
    return GenerationManifest.model_validate(manifest_payload())


def test_execute_run_writes_manifest_run_record_and_artifact(tmp_path: Path) -> None:
    started_at = datetime(2026, 11, 10, 10, 0, tzinfo=UTC)
    times = iter((started_at, started_at + timedelta(seconds=1.25)))

    outcome = execute_run(
        build_manifest(),
        tmp_path / "runs",
        RecordingProvider(),
        run_id="run-001",
        clock=lambda: next(times),
    )

    assert outcome.record.status is RunStatus.COMPLETED
    assert outcome.record.duration_ms == 1250
    assert outcome.record.provider.name == "recording"
    assert len(outcome.record.artifacts) == 1

    artifact = outcome.record.artifacts[0]
    assert artifact.path == "result.txt"
    assert artifact.sha256 == hashlib.sha256("测试脚本".encode()).hexdigest()

    run_payload = json.loads((outcome.directory / "run.json").read_text(encoding="utf-8"))
    manifest_payload_saved = json.loads(
        (outcome.directory / "manifest.json").read_text(encoding="utf-8")
    )
    assert run_payload["run_id"] == "run-001"
    assert run_payload["status"] == "completed"
    assert manifest_payload_saved["case_id"] == "ledger-test"


def test_execute_run_rejects_duplicate_run_id(tmp_path: Path) -> None:
    manifest = build_manifest()
    output_root = tmp_path / "runs"
    execute_run(manifest, output_root, RecordingProvider(), run_id="duplicate")

    with pytest.raises(RunLedgerError, match="已经存在"):
        execute_run(manifest, output_root, RecordingProvider(), run_id="duplicate")


def test_execute_run_persists_failed_provider_result(tmp_path: Path) -> None:
    outcome = execute_run(
        build_manifest(),
        tmp_path / "runs",
        FailingProvider(),
        run_id="failed-run",
    )

    assert outcome.record.status is RunStatus.FAILED
    assert outcome.record.error == "模拟提供器失败"
    assert [artifact.path for artifact in outcome.record.artifacts] == ["partial.txt"]


def test_load_manifest_rejects_invalid_json(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text("{invalid", encoding="utf-8")

    with pytest.raises(ManifestError, match="清单校验失败"):
        load_manifest(manifest_path)


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="需要 FFmpeg 和 ffprobe",
)
def test_cli_run_with_mock_provider_creates_valid_video(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "mock-video",
                "title": "Mock 视频测试",
                "script": "生成一个短视频。",
                "scene_count": 2,
                "aspect_ratio": "9:16",
                "duration_seconds": 1.0,
                "language": "zh-CN",
                "provider": {
                    "name": "mock",
                    "version": "0.2.0",
                    "model": "mock-video",
                    "model_version": "1",
                    "seed": 42,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_root = tmp_path / "runs"

    exit_code = main(
        [
            "run",
            str(manifest_path),
            "--output-dir",
            str(output_root),
            "--run-id",
            "cli-run",
            "--json",
        ]
    )

    assert exit_code == 0
    record = json.loads(capsys.readouterr().out)
    assert record["status"] == "completed"
    assert record["run_id"] == "cli-run"
    assert {artifact["path"] for artifact in record["artifacts"]} == {
        "final.mp4",
        "scene-plan.json",
    }

    video_path = output_root / "mock-video" / "cli-run" / "artifacts" / "final.mp4"
    media_info = probe_media(video_path)
    assert media_info.duration_seconds is not None
    assert 0.9 <= media_info.duration_seconds <= 1.2
    assert len(media_info.video_streams) == 1
    assert len(media_info.audio_streams) == 1


def test_cli_run_reports_missing_manifest(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["run", str(tmp_path / "missing.json")])

    assert exit_code == 2
    assert "无法读取清单文件" in capsys.readouterr().err
