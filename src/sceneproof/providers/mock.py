"""确定性的本地 Mock 视频提供器。"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from sceneproof import __version__
from sceneproof.models import GenerationManifest, ProviderRecord
from sceneproof.providers.base import ProviderError


class MockVideoProvider:
    """使用 FFmpeg 生成一个轻量视频，用于打通测试链路。"""

    def __init__(self, *, ffmpeg_executable: str = "ffmpeg") -> None:
        self._ffmpeg_executable = ffmpeg_executable

    def generate(
        self,
        manifest: GenerationManifest,
        artifact_dir: Path,
    ) -> ProviderRecord:
        ffmpeg = shutil.which(self._ffmpeg_executable)
        if ffmpeg is None:
            raise ProviderError(f"未找到 FFmpeg 可执行文件：{self._ffmpeg_executable}")

        artifact_dir.mkdir(parents=True, exist_ok=True)
        width, height = _resolve_dimensions(manifest.aspect_ratio)
        video_path = artifact_dir / "final.mp4"
        # Mock 视频只保证可播放，并使用无声音频源创建真实音频流。
        command = [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc2=size={width}x{height}:rate=1",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=48000:cl=stereo",
            "-t",
            f"{manifest.duration_seconds:.3f}",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "aac",
            "-pix_fmt",
            "yuv420p",
            "-shortest",
            "-movflags",
            "+faststart",
            str(video_path),
        ]
        result = subprocess.run(
            # 参数列表方式不会经过 shell，路径中的空格不会被重新解释。
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            detail = result.stderr.strip() or "FFmpeg 返回了非零退出码"
            raise ProviderError(f"Mock 视频生成失败：{detail}")

        scene_plan = artifact_dir / "scene-plan.json"
        # 将场景时长写成结构化证据，供后续校验器读取。
        scene_plan.write_text(
            json.dumps(
                _build_scene_plan(manifest),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        return ProviderRecord(
            name="mock",
            version=__version__,
            model=manifest.provider.model,
            model_version=manifest.provider.model_version,
        )


def _resolve_dimensions(aspect_ratio: str) -> tuple[int, int]:
    width_ratio, height_ratio = (int(value) for value in aspect_ratio.split(":", maxsplit=1))
    if width_ratio >= height_ratio:
        width = 320
        height = max(2, round(width * height_ratio / width_ratio))
    else:
        height = 320
        width = max(2, round(height * width_ratio / height_ratio))
    return _make_even(width), _make_even(height)


def _make_even(value: int) -> int:
    return max(2, value // 2 * 2)


def _build_scene_plan(manifest: GenerationManifest) -> dict[str, object]:
    scene_duration = manifest.duration_seconds / manifest.scene_count
    scenes = [
        {
            "index": index,
            "start_seconds": round((index - 1) * scene_duration, 3),
            "end_seconds": round(index * scene_duration, 3),
        }
        for index in range(1, manifest.scene_count + 1)
    ]
    return {
        "case_id": manifest.case_id,
        "scene_count": manifest.scene_count,
        "duration_seconds": manifest.duration_seconds,
        "scenes": scenes,
    }
