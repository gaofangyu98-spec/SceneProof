"""确定性校验器的测试。"""

from __future__ import annotations

from pathlib import Path

from sceneproof.media import AudioStream, MediaInfo
from sceneproof.validators import validate_required_audio


# 作用：验证有音频时校验通过；处理：构造带一条音频流的媒体信息，检查状态码和中文结果。
def test_validate_required_audio_passes_when_audio_exists() -> None:
    media_info = MediaInfo(
        path=Path("sample.mp4"),
        format_name="mp4",
        duration_seconds=1.0,
        size_bytes=1024,
        bit_rate=8192,
        video_streams=(),
        audio_streams=(
            AudioStream(
                index=1,
                codec_name="aac",
                channels=2,
                sample_rate=48000,
            ),
        ),
    )

    result = validate_required_audio(media_info)

    assert result.passed is True
    assert result.code == "audio_present"
    assert "音频" in result.message


# 作用：验证无音频时校验失败；处理：构造无音频流的媒体信息，检查缺失音频状态和中文错误说明。
def test_validate_required_audio_fails_when_audio_is_missing() -> None:
    media_info = MediaInfo(
        path=Path("sample.mp4"),
        format_name="mp4",
        duration_seconds=1.0,
        size_bytes=1024,
        bit_rate=8192,
        video_streams=(),
        audio_streams=(),
    )

    result = validate_required_audio(media_info)

    assert result.passed is False
    assert result.code == "missing_audio"
    assert "音频" in result.message
