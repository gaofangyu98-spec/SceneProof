"""生成提供器的注册与创建。"""

from __future__ import annotations

from sceneproof.providers.base import ProviderError, VideoProvider
from sceneproof.providers.mock import MockVideoProvider


# 作用：创建生成提供器；处理：根据名称返回对应实现，未知名称抛出明确错误。
def create_provider(name: str) -> VideoProvider:
    """根据清单中的名称创建提供器。"""

    if name == "mock":
        return MockVideoProvider()
    raise ProviderError(f"不支持的生成提供器：{name}")
