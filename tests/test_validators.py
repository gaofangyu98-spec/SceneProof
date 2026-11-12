"""确定性校验器的测试。"""

from __future__ import annotations

from pathlib import Path

from sceneproof.media import AudioStream, MediaInfo, VideoStream
from sceneproof.validators import validate_required_audio, validate_required_video


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


# 作用：验证有视频时校验通过；处理：构造带一条视频流的媒体信息，检查状态码和中文结果。
def test_validate_required_video_passes_when_video_exists() -> None:
    media_info = MediaInfo(
        path=Path("sample.mp4"),
        format_name="mp4",
        duration_seconds=1.0,
        size_bytes=1024,
        bit_rate=8192,
        video_streams=(
            VideoStream(
                index=0,
                codec_name="h264",
                width=1080,
                height=1920,
                frame_rate=30.0,
            ),
        ),
        audio_streams=(),
    )

    result = validate_required_video(media_info)

    assert result.passed is True
    assert result.code == "video_present"
    assert "视频" in result.message


# 作用：验证无视频时校验失败；处理：构造没有视频流的媒体信息，检查缺失视频状态和中文说明。
def test_validate_required_video_fails_when_video_is_missing() -> None:
    media_info = MediaInfo(
        path=Path("sample.mp4"),
        format_name="mp4",
        duration_seconds=1.0,
        size_bytes=1024,
        bit_rate=8192,
        video_streams=(),
        audio_streams=(),
    )

    result = validate_required_video(media_info)

    assert result.passed is False
    assert result.code == "missing_video"
    assert "视频" in result.message
