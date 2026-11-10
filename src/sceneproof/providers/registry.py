"""生成提供器的注册与创建。"""

from __future__ import annotations

from sceneproof.providers.base import ProviderError, VideoProvider
from sceneproof.providers.mock import MockVideoProvider


def create_provider(name: str) -> VideoProvider:
    """根据清单中的名称创建提供器。"""

    if name == "mock":
        return MockVideoProvider()
    raise ProviderError(f"不支持的生成提供器：{name}")
