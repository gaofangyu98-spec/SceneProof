"""生成运行记录、产物校验和本地持久化。"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import re
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from sceneproof.media import MediaProbeError, probe_media
from sceneproof.models import (
    RUN_ID_PATTERN,
    ArtifactRecord,
    GenerationManifest,
    ProviderRecord,
    RunRecord,
    RunStatus,
    ValidationRecord,
)
from sceneproof.providers.base import ProviderError, VideoProvider
from sceneproof.validators import (
    ValidationResult,
    validate_container,
    validate_duration,
    validate_required_audio,
    validate_required_video,
)


class ManifestError(RuntimeError):
    """清单文件无法读取或校验失败时抛出。"""


class RunLedgerError(RuntimeError):
    """运行记录无法安全创建或写入时抛出。"""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """一次运行记录的执行结果。"""

    record: RunRecord
    directory: Path


# 作用：加载生成清单；处理：读取 JSON 文件并通过数据模型校验字段和取值。
def load_manifest(path: str | Path) -> GenerationManifest:
    """从 JSON 文件读取并校验生成清单。"""

    manifest_path = Path(path).expanduser()
    try:
        content = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"无法读取清单文件：{manifest_path}") from exc

    try:
        return GenerationManifest.model_validate_json(content)
    except ValidationError as exc:
        raise ManifestError(f"清单校验失败：{exc}") from exc


# 作用：执行一次生成任务；处理：创建运行目录、调用提供器并保存完整证据。
def execute_run(
    manifest: GenerationManifest,
    output_root: str | Path,
    provider: VideoProvider,
    *,
    run_id: str | None = None,
    clock: Callable[[], datetime] | None = None,
) -> RunOutcome:
    """执行一次生成并写入不可变运行目录。"""

    now = clock or _utc_now
    started_at = _ensure_utc(now())
    resolved_run_id = run_id or _new_run_id(started_at)
    # 用例编号和运行编号会参与目录拼接，因此必须先限制格式。
    if re.fullmatch(RUN_ID_PATTERN, resolved_run_id) is None:
        raise RunLedgerError(f"运行编号格式不合法：{resolved_run_id}")

    root = Path(output_root).expanduser().resolve()
    run_dir = root / manifest.case_id / resolved_run_id
    if not run_dir.is_relative_to(root):
        raise RunLedgerError("运行目录超出输出根目录")

    try:
        artifact_dir = run_dir / "artifacts"
        # 已存在的运行目录不能复用，避免覆盖历史证据。
        artifact_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RunLedgerError(f"运行目录已经存在：{run_dir}") from exc

    _write_json_atomic(
        run_dir / "manifest.json",
        manifest.model_dump(mode="json"),
    )

    # 即使提供器失败，也要保留输入快照、错误和已经产生的部分产物。
    status = RunStatus.COMPLETED
    error: str | None = None
    provider_record = _provider_record_from_manifest(manifest)

    try:
        provider_record = provider.generate(manifest, artifact_dir)
    except ProviderError as exc:
        status = RunStatus.FAILED
        error = str(exc)

    # 以磁盘上的实际文件为准生成产物记录。
    artifacts = _collect_artifacts(artifact_dir)
    validations = _collect_validations(manifest, artifact_dir, artifacts)
    finished_at = _ensure_utc(now())

    record = RunRecord(
        run_id=resolved_run_id,
        case_id=manifest.case_id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        duration_ms=max(0, round((finished_at - started_at).total_seconds() * 1000)),
        manifest=manifest,
        provider=provider_record,
        artifacts=artifacts,
        validations=validations,
        error=error,
    )
    _write_json_atomic(run_dir / "run.json", record.model_dump(mode="json"))
    return RunOutcome(record=record, directory=run_dir)


# 作用：收集视频产物的校验证据。
# 处理：逐个探测视频并执行容器、视频流、音频流和时长校验，读取失败也记录为失败证据。
def _collect_validations(
    manifest: GenerationManifest,
    artifact_dir: Path,
    artifacts: tuple[ArtifactRecord, ...],
) -> tuple[ValidationRecord, ...]:
    validations: list[ValidationRecord] = []

    for artifact in artifacts:
        if not artifact.media_type.startswith("video/"):
            continue

        try:
            media_info = probe_media(artifact_dir / artifact.path)
            results: tuple[ValidationResult, ...] = (
                validate_container(
                    media_info,
                    expected_container=manifest.expected_container,
                ),
                validate_required_video(media_info),
                validate_required_audio(media_info),
                validate_duration(
                    media_info,
                    expected_seconds=manifest.duration_seconds,
                    tolerance_seconds=manifest.duration_tolerance_seconds,
                ),
            )
        except MediaProbeError as exc:
            results = (
                ValidationResult(
                    code="media_probe_failed",
                    passed=False,
                    message=f"无法读取媒体信息：{exc}",
                ),
            )

        for result in results:
            validations.append(
                ValidationRecord(
                    artifact_path=artifact.path,
                    code=result.code,
                    passed=result.passed,
                    message=result.message,
                )
            )

    return tuple(validations)


# 作用：收集生成产物；处理：扫描实际文件并计算路径、类型、大小和哈希。
def _collect_artifacts(artifact_dir: Path) -> tuple[ArtifactRecord, ...]:
    records: list[ArtifactRecord] = []
    for path in sorted(artifact_dir.rglob("*")):
        if path.is_symlink():
            raise RunLedgerError(f"产物目录不允许符号链接：{path}")
        if not path.is_file():
            continue
        media_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        records.append(
            ArtifactRecord(
                path=path.relative_to(artifact_dir).as_posix(),
                media_type=media_type,
                size_bytes=path.stat().st_size,
                sha256=_sha256(path),
            )
        )
    return tuple(records)


# 作用：计算文件哈希；处理：分块读取文件并返回十六进制 SHA-256。
def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


# 作用：原子写入 JSON；处理：先写临时文件，再替换目标文件以避免半成品。
def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    # 先写临时文件再替换，避免进程中断后留下不完整的 JSON。
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


# 作用：提取提供器信息；处理：把清单中的名称、版本、模型和模型版本转成记录。
def _provider_record_from_manifest(manifest: GenerationManifest) -> ProviderRecord:
    return ProviderRecord(
        name=manifest.provider.name,
        version=manifest.provider.version,
        model=manifest.provider.model,
        model_version=manifest.provider.model_version,
    )


# 作用：生成运行编号；处理：组合 UTC 时间戳和短随机串，保证目录名称基本唯一。
def _new_run_id(started_at: datetime) -> str:
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(3)}"


# 作用：获取当前时间；处理：返回包含 UTC 时区的当前时间对象。
def _utc_now() -> datetime:
    return datetime.now(UTC)


# 作用：校正时间时区；处理：拒绝无时区时间，并将其他时区统一转换为 UTC。
def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RunLedgerError("运行时间必须包含时区")
    return value.astimezone(UTC)
