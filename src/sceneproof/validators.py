"""SceneProof 的确定性质量校验器。"""

from __future__ import annotations

from dataclasses import dataclass

from sceneproof.media import MediaInfo


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """一条可序列化、可比较的校验结果。"""

    code: str
    passed: bool
    message: str


# 作用：检查媒体是否至少包含一条音频流。
# 处理：根据 audio_streams 是否存在返回通过或失败结果，不抛出异常。
def validate_required_audio(media_info: MediaInfo) -> ValidationResult:
    """校验媒体文件是否包含音频流。"""

    if media_info.audio_streams:
        return ValidationResult(
            code="audio_present",
            passed=True,
            message="检测到音频流，校验通过。",
        )

    return ValidationResult(
        code="missing_audio",
        passed=False,
        message="未检测到音频流，视频缺少应有的声音。",
    )


# 作用：检查媒体是否至少包含一条视频流。
# 处理：根据 video_streams 是否存在返回通过或失败结果，不抛出异常。
def validate_required_video(media_info: MediaInfo) -> ValidationResult:
    """校验媒体文件是否包含视频流。"""

    if media_info.video_streams:
        return ValidationResult(
            code="video_present",
            passed=True,
            message="检测到视频流，校验通过。",
        )

    return ValidationResult(
        code="missing_video",
        passed=False,
        message="未检测到视频流，产物不是可播放的视频。",
    )


# 作用：检查媒体实际时长是否落在预期时长和容差范围内。
# 处理：缺失时长直接失败，否则比较绝对偏差并返回稳定状态码和中文说明。
def validate_duration(
    media_info: MediaInfo,
    *,
    expected_seconds: float,
    tolerance_seconds: float,
) -> ValidationResult:
    """校验媒体时长是否符合清单中的预期。"""

    if expected_seconds <= 0:
        raise ValueError("预期时长必须大于 0")
    if tolerance_seconds < 0:
        raise ValueError("时长容差不能小于 0")

    if media_info.duration_seconds is None:
        return ValidationResult(
            code="duration_missing",
            passed=False,
            message="无法读取视频时长，无法完成时长校验。",
        )

    difference = abs(media_info.duration_seconds - expected_seconds)
    if difference <= tolerance_seconds:
        return ValidationResult(
            code="duration_within_tolerance",
            passed=True,
            message=(
                f"实际时长 {media_info.duration_seconds:.3f} 秒，"
                f"与预期 {expected_seconds:.3f} 秒的偏差在 {tolerance_seconds:.3f} 秒容差内。"
            ),
        )

    return ValidationResult(
        code="duration_out_of_tolerance",
        passed=False,
        message=(
            f"实际时长 {media_info.duration_seconds:.3f} 秒，"
            f"与预期 {expected_seconds:.3f} 秒相差 {difference:.3f} 秒，"
            f"超过 {tolerance_seconds:.3f} 秒容差。"
        ),
    )
