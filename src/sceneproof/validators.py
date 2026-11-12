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
