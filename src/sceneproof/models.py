"""SceneProof 的数据模型与清单校验。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SCHEMA_VERSION: Literal["1.0"] = "1.0"

CASE_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"
RUN_ID_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,95}$"


class StrictModel(BaseModel):
    """禁止未声明字段，避免清单中的拼写错误被静默忽略。"""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ProviderConfig(StrictModel):
    """声明一次生成使用的提供器与模型版本。"""

    name: str = Field(min_length=1, max_length=64)
    version: str = Field(default="0.2.0", min_length=1, max_length=64)
    model: str = Field(min_length=1, max_length=128)
    model_version: str = Field(min_length=1, max_length=128)
    seed: int | None = None


class GenerationManifest(StrictModel):
    """可复现的视频生成用例。"""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    case_id: str = Field(pattern=CASE_ID_PATTERN)
    title: str = Field(min_length=1, max_length=200)
    script: str = Field(min_length=1)
    scene_count: int = Field(ge=1, le=100)
    aspect_ratio: str = Field(pattern=r"^[1-9][0-9]{0,3}:[1-9][0-9]{0,3}$")
    duration_seconds: float = Field(gt=0, le=3600)
    language: str = Field(default="zh-CN", pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
    provider: ProviderConfig


class RunStatus(StrEnum):
    """生成任务的状态。"""

    COMPLETED = "completed"
    FAILED = "failed"


class ArtifactRecord(StrictModel):
    """一个生成产物的校验记录。"""

    path: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ValidationRecord(StrictModel):
    """一条与具体产物关联的校验证据。"""

    artifact_path: str = Field(min_length=1, max_length=1024)
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    passed: bool
    message: str = Field(min_length=1, max_length=1000)


class ProviderRecord(StrictModel):
    """提供器在本次运行中实际报告的信息。"""

    name: str = Field(min_length=1)
    version: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_version: str = Field(min_length=1)


class RunRecord(StrictModel):
    """一次生成任务的不可变运行记录。"""

    schema_version: Literal["1.0"] = SCHEMA_VERSION
    run_id: str = Field(pattern=RUN_ID_PATTERN)
    case_id: str = Field(pattern=CASE_ID_PATTERN)
    status: RunStatus
    started_at: datetime
    finished_at: datetime
    duration_ms: int = Field(ge=0)
    manifest: GenerationManifest
    provider: ProviderRecord
    artifacts: tuple[ArtifactRecord, ...] = ()
    validations: tuple[ValidationRecord, ...] = ()
    error: str | None = None
