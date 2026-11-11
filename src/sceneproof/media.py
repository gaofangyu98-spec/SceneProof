"""FFprobe 调用与媒体元数据模型。"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path


class MediaProbeError(RuntimeError):
    """无法获取或解析媒体元数据时抛出。"""


class ExecutableNotFoundError(MediaProbeError):
    """请求的可执行文件不存在时抛出。"""


@dataclass(frozen=True, slots=True)
class VideoStream:
    """单个视频流的精简元数据。"""

    index: int
    codec_name: str | None
    width: int | None
    height: int | None
    frame_rate: float | None


@dataclass(frozen=True, slots=True)
class AudioStream:
    """单个音频流的精简元数据。"""

    index: int
    codec_name: str | None
    channels: int | None
    sample_rate: int | None


@dataclass(frozen=True, slots=True)
class MediaInfo:
    """SceneProof 边界返回的稳定媒体元数据。"""

    path: Path
    format_name: str | None
    duration_seconds: float | None
    size_bytes: int | None
    bit_rate: int | None
    video_streams: tuple[VideoStream, ...]
    audio_streams: tuple[AudioStream, ...]


# 作用：读取媒体信息；处理：校验路径、调用 FFprobe、解析 JSON 并返回媒体对象。
def probe_media(path: str | Path, *, ffprobe_executable: str = "ffprobe") -> MediaInfo:
    """使用 FFprobe 读取媒体元数据。

    调用命令时不经过 shell，路径和后续的用户输入都会作为独立参数传入。
    """

    media_path = Path(path).expanduser()
    try:
        resolved_path = media_path.resolve(strict=True)
    except FileNotFoundError as exc:
        raise MediaProbeError(f"媒体文件不存在：{media_path}") from exc

    if not resolved_path.is_file():
        raise MediaProbeError(f"媒体路径不是普通文件：{resolved_path}")

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
        raise ExecutableNotFoundError(f"未找到 FFprobe 可执行文件：{ffprobe_executable}") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or "FFprobe 返回了非零退出码"
        raise MediaProbeError(f"无法读取媒体信息：{detail}") from exc

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaProbeError("FFprobe 返回了无效 JSON") from exc

    return build_media_info(payload, resolved_path)


# 作用：解析 FFprobe 数据；处理：提取容器字段，并分别构建视频流和音频流。
def build_media_info(payload: object, path: Path) -> MediaInfo:
    """从 FFprobe JSON 数据构建领域元数据。"""

    if not isinstance(payload, dict):
        raise MediaProbeError("FFprobe 数据必须是 JSON 对象")

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


# 作用：安全转换字符串；处理：空值返回 None，其余值转换为字符串。
def _optional_str(value: object) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


# 作用：安全转换整数；处理：空值或非法值返回 None，合法值转换为 int。
def _optional_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


# 作用：安全转换浮点数；处理：空值或非法值返回 None，合法值转换为 float。
def _optional_float(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


# 作用：解析帧率；处理：把分数形式帧率转换为浮点数，零或非法值返回 None。
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
