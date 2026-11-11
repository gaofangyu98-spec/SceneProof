"""提供器边界定义。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from sceneproof.models import GenerationManifest, ProviderRecord


class ProviderError(RuntimeError):
    """提供器无法完成生成任务时抛出。"""


class VideoProvider(Protocol):
    """平台适配器需要实现的最小接口。"""

    # 作用：执行一次平台生成；处理：接收清单和产物目录，返回实际提供器信息。
    def generate(
        self,
        manifest: GenerationManifest,
        artifact_dir: Path,
    ) -> ProviderRecord:
        """生成产物并返回本次实际使用的提供器信息。"""
