"""生成清单数据模型测试。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sceneproof.models import GenerationManifest


# 作用：构造合法清单数据；处理：返回包含完整提供器和媒体配置的测试字典。
def valid_manifest_payload() -> dict[str, object]:
    return {
        "case_id": "three-scene-demo",
        "title": "三场景短视频演示",
        "script": "人物走进咖啡馆，然后坐下。",
        "scene_count": 2,
        "aspect_ratio": "9:16",
        "duration_seconds": 2.0,
        "language": "zh-CN",
        "provider": {
            "name": "mock",
            "version": "0.2.0",
            "model": "mock-video",
            "model_version": "1",
            "seed": 42,
        },
    }


# 作用：验证合法清单；处理：生成数据模型并检查关键字段是否被正确保留。
def test_generation_manifest_accepts_valid_payload() -> None:
    manifest = GenerationManifest.model_validate(valid_manifest_payload())

    assert manifest.case_id == "three-scene-demo"
    assert manifest.scene_count == 2
    assert manifest.provider.seed == 42


# 作用：验证未知字段拦截；处理：向清单添加非法字段并检查数据模型抛错。
def test_generation_manifest_rejects_unknown_fields() -> None:
    payload = valid_manifest_payload()
    payload["unknown_field"] = "value"

    with pytest.raises(ValidationError, match="unknown_field"):
        GenerationManifest.model_validate(payload)


# 作用：验证画幅校验；处理：使用非法画幅值并检查数据模型拒绝输入。
def test_generation_manifest_rejects_invalid_aspect_ratio() -> None:
    payload = valid_manifest_payload()
    payload["aspect_ratio"] = "vertical"

    with pytest.raises(ValidationError, match="aspect_ratio"):
        GenerationManifest.model_validate(payload)


# 作用：验证用例编号校验；处理：使用路径穿越字符并检查数据模型拒绝输入。
def test_generation_manifest_rejects_invalid_case_id() -> None:
    payload = valid_manifest_payload()
    payload["case_id"] = "../escape"

    with pytest.raises(ValidationError, match="case_id"):
        GenerationManifest.model_validate(payload)
