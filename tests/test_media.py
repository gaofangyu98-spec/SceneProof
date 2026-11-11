"""媒体探测和命令行输出测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sceneproof.cli import main
from sceneproof.media import (
    ExecutableNotFoundError,
    MediaProbeError,
    build_media_info,
    probe_media,
)


# 作用：验证元数据解析；处理：输入模拟 FFprobe 数据并检查视频流和音频流字段。
def test_build_media_info_parses_ffprobe_payload() -> None:
    payload = {
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "duration": "15.250000",
            "size": "4096",
            "bit_rate": "2148",
        },
        "streams": [
            {
                "index": 0,
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "avg_frame_rate": "30000/1001",
            },
            {
                "index": 1,
                "codec_type": "audio",
                "codec_name": "aac",
                "channels": 2,
                "sample_rate": "48000",
            },
        ],
    }

    media_info = build_media_info(payload, Path("sample.mp4"))

    assert media_info.format_name == "mov,mp4,m4a,3gp,3g2,mj2"
    assert media_info.duration_seconds == pytest.approx(15.25)
    assert media_info.size_bytes == 4096
    assert media_info.video_streams[0].width == 1080
    assert media_info.video_streams[0].height == 1920
    assert media_info.video_streams[0].frame_rate == pytest.approx(29.970, rel=1e-3)
    assert media_info.audio_streams[0].channels == 2
    assert media_info.audio_streams[0].sample_rate == 48000


# 作用：验证缺失文件处理；处理：探测不存在的路径并检查中文错误信息。
def test_probe_media_rejects_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.mp4"

    with pytest.raises(MediaProbeError, match="媒体文件不存在"):
        probe_media(missing)


# 作用：验证 FFprobe 缺失处理；处理：指定不存在的可执行文件并检查异常类型。
def test_probe_media_reports_missing_executable(sample_video: Path) -> None:
    with pytest.raises(ExecutableNotFoundError):
        probe_media(sample_video, ffprobe_executable="definitely-not-an-ffprobe-binary")


# 作用：验证真实视频探测；处理：读取夹具视频并检查时长、分辨率和音频流。
def test_probe_media_reads_real_video(sample_video: Path) -> None:
    media_info = probe_media(sample_video)

    assert media_info.duration_seconds is not None
    assert 1.0 <= media_info.duration_seconds <= 2.0
    assert len(media_info.video_streams) == 1
    assert media_info.video_streams[0].width == 320
    assert media_info.video_streams[0].height == 240
    assert media_info.audio_streams == ()


# 作用：验证命令行 JSON 输出；处理：执行 probe 子命令并解析标准输出结果。
def test_cli_probe_emits_json(
    sample_video: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["probe", str(sample_video), "--json"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["path"] == str(sample_video.resolve())
    assert payload["video_streams"][0]["width"] == 320


# 作用：验证命令行错误返回；处理：探测缺失文件并检查退出码和错误输出。
def test_cli_returns_error_for_missing_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = main(["probe", str(tmp_path / "missing.mp4")])

    assert exit_code == 2
    assert "媒体文件不存在" in capsys.readouterr().err
