"""pytest 共用测试夹具。"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def sample_video(tmp_path: Path) -> Path:
    """在 FFmpeg 可用时生成一个可重复的短视频。"""

    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("媒体集成测试需要 FFmpeg")

    output = tmp_path / "sample.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=320x240:rate=10",
            "-t",
            "1.2",
            "-c:v",
            "mpeg4",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
    )
    return output
