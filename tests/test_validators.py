"""确定性校验器的测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from sceneproof.media import AudioStream, MediaInfo, VideoStream
from sceneproof.validators import (
    validate_container,
    validate_duration,
    validate_required_audio,
    validate_required_video,
)


# 作用：构造带指定时长和容器的媒体对象；处理：返回包含最小视频流和音频流的测试数据。
def media_info_with_duration(
    duration_seconds: float | None,
    *,
    format_name: str | None = "mp4",
) -> MediaInfo:
    return MediaInfo(
        path=Path("sample.mp4"),
        format_name=format_name,
        duration_seconds=duration_seconds,
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
        audio_streams=(
            AudioStream(
                index=1,
                codec_name="aac",
                channels=2,
                sample_rate=48000,
            ),
        ),
    )


# 作用：验证容器匹配时通过；处理：使用包含 mp4 别名的 FFprobe 值并检查通过结果。
def test_validate_container_passes_for_matching_alias() -> None:
    media_info = media_info_with_duration(
        2.0,
        format_name="mov,mp4,m4a,3gp,3g2,mj2",
    )

    result = validate_container(media_info, expected_container="mp4")

    assert result.passed is True
    assert result.code == "container_matched"
    assert "mp4" in result.message


# 作用：验证容器不匹配时失败；处理：使用 WebM 容器并要求 mp4 后检查失败状态码和说明。
def test_validate_container_fails_for_mismatch() -> None:
    media_info = media_info_with_duration(2.0, format_name="matroska,webm")

    result = validate_container(media_info, expected_container="mp4")

    assert result.passed is False
    assert result.code == "container_mismatch"
    assert "webm" in result.message


# 作用：验证缺失容器信息时失败；处理：构造没有 format_name 的媒体信息并检查缺失状态码。
def test_validate_container_fails_when_format_is_missing() -> None:
    media_info = media_info_with_duration(2.0, format_name=None)

    result = validate_container(media_info, expected_container="mp4")

    assert result.passed is False
    assert result.code == "container_missing"
    assert "容器" in result.message


# 作用：验证空预期容器被拒绝；处理：传入空白字符串并检查异常。
def test_validate_container_rejects_empty_expected_container() -> None:
    with pytest.raises(ValueError, match="预期容器"):
        validate_container(
            media_info_with_duration(2.0),
            expected_container="  ",
        )


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


# 作用：验证时长在容差内时通过；处理：使用接近预期时长的媒体信息检查通过状态和状态码。
def test_validate_duration_passes_within_tolerance() -> None:
    result = validate_duration(
        media_info_with_duration(2.19),
        expected_seconds=2.0,
        tolerance_seconds=0.2,
    )

    assert result.passed is True
    assert result.code == "duration_within_tolerance"
    assert "容差" in result.message


# 作用：验证时长超出容差时失败；处理：使用明显偏离预期时长的媒体信息检查失败状态和中文说明。
def test_validate_duration_fails_outside_tolerance() -> None:
    result = validate_duration(
        media_info_with_duration(2.3),
        expected_seconds=2.0,
        tolerance_seconds=0.2,
    )

    assert result.passed is False
    assert result.code == "duration_out_of_tolerance"
    assert "超过" in result.message


# 作用：验证缺失时长时失败；处理：构造没有时长元数据的媒体信息并检查缺失状态码。
def test_validate_duration_fails_when_duration_is_missing() -> None:
    result = validate_duration(
        media_info_with_duration(None),
        expected_seconds=2.0,
        tolerance_seconds=0.2,
    )

    assert result.passed is False
    assert result.code == "duration_missing"
    assert "时长" in result.message


# 作用：验证非法时长参数被拒绝；处理：分别传入非正预期时长和负容差并检查异常。
@pytest.mark.parametrize(
    ("expected_seconds", "tolerance_seconds"),
    [(0.0, 0.2), (2.0, -0.1)],
)
def test_validate_duration_rejects_invalid_thresholds(
    expected_seconds: float,
    tolerance_seconds: float,
) -> None:
    with pytest.raises(ValueError):
        validate_duration(
            media_info_with_duration(2.0),
            expected_seconds=expected_seconds,
            tolerance_seconds=tolerance_seconds,
        )
