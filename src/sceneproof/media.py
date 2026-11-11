"""FFprobe integration and media metadata models."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


class MediaProbeError(RuntimeError):
    """Raised when media metadata cannot be obtained or parsed."""


class ExecutableNotFoundError(MediaProbeError):
    """Raised when the requested executable is unavailable."""


@dataclass(frozen=True, slots=True)
class VideoStream:
    """Selected metadata for one video stream."""

    index: int
    codec_name: str | None
    width: int | None
    height: int | None
    frame_rate: float | None


@dataclass(frozen=True, slots=True)
class AudioStream:
    """Selected metadata for one audio stream."""

    index: int
    codec_name: str | None
    channels: int | None
    sample_rate: int | None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """Stable media metadata returned by the SceneProof boundary."""

    path: Path
    format_name: str | None
    duration_seconds: float | None
    size_bytes: int | None
    bit_rate: int | None
    video_streams: tuple[VideoStream, ...]
    audio_streams: tuple[AudioStream, ...]


def probe_media(path: str | Path, *, ffprobe_executable: str = "ffprobe") -> MediaInfo:
    """Read media metadata using FFprobe.

    The command is executed without a shell so paths and future user-provided values are passed
    as individual process arguments.
    """

    media_path = Path(path).expanduser()
    try:
        resolved_path = media_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MediaProbeError(f"Media file does not exist: {media_path}") from exc

    if not resolved_path.is_file():
        raise MediaProbeError(f"Media path is not a regular file: {resolved_path}")

    command = [
        ffprobe_executable,
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(resolved_path),
    ]

    # 使用参数列表调用 FFprobe，不能把用户路径拼进 shell 命令。
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ExecutableNotFoundError(
            f"FFprobe executable was not found: {ffprobe_executable}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "FFprobe returned a non-zero exit code"
        raise MediaProbeError(f"Unable to probe media: {detail}") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("FFprobe returned invalid JSON") from exc

    return build_media_info(payload, resolved_path)


def build_media_info(payload: object, path: Path) -> MediaInfo:
    """Build domain metadata from an FFprobe JSON payload."""

    if not isinstance(payload, dict):
        raise MediaProbeError("FFprobe payload must be a JSON object")

    format_data = payload.get("format")
    streams_data = payload.get("streams")
    if not isinstance(format_data, dict):
        format_data = {}
    if not isinstance(streams_data, list):
        streams_data = []

    video_streams: list[VideoStream] = []
    audio_streams: list[AudioStream] = []

    # FFprobe 可能返回字幕、数据等流，这里只保留当前阶段需要的视频和音频。
    for raw_stream in streams_data:
        if not isinstance(raw_stream, dict):
            continue

        index = _optional_int(raw_stream.get("index"))
        if index is None:
            continue

        codec_type = raw_stream.get("codec_type")
        codec_name = _optional_str(raw_stream.get("codec_name"))

        if codec_type == "video":
            video_streams.append(
                VideoStream(
                    index=index,
                    codec_name=codec_name,
                    width=_optional_int(raw_stream.get("width")),
                    height=_optional_int(raw_stream.get("height")),
                    frame_rate=_parse_frame_rate(raw_stream.get("avg_frame_rate")),
                )
            )
        elif codec_type == "audio":
            audio_streams.append(
                AudioStream(
                    index=index,
                    codec_name=codec_name,
                    channels=_optional_int(raw_stream.get("channels")),
                    sample_rate=_optional_int(raw_stream.get("sample_rate")),
                )
            )

    return MediaInfo(
        path=path,
        format_name=_optional_str(format_data.get("format_name")),
        duration_seconds=_optional_float(format_data.get("duration")),
        size_bytes=_optional_int(format_data.get("size")),
        bit_rate=_optional_int(format_data.get("bit_rate")),
        video_streams=tuple(video_streams),
        audio_streams=tuple(audio_streams),
    )


def _optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _parse_frame_rate(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        rate = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        return None
    if rate.numerator == 0 or rate.denominator == 0:
        return None
    return float(rate)
