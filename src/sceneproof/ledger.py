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

from sceneproof.models import (
    RUN_ID_PATTERN,
    ArtifactRecord,
    GenerationManifest,
    ProviderRecord,
    RunRecord,
    RunStatus,
)
from sceneproof.providers.base import ProviderError, VideoProvider


class ManifestError(RuntimeError):
    """清单文件无法读取或校验失败时抛出。"""


class RunLedgerError(RuntimeError):
    """运行记录无法安全创建或写入时抛出。"""


@dataclass(frozen=True, slots=True)
class RunOutcome:
    """一次运行记录的执行结果。"""

    record: RunRecord
    directory: Path


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
    if re.fullmatch(RUN_ID_PATTERN, resolved_run_id) is None:
        raise RunLedgerError(f"运行编号格式不合法：{resolved_run_id}")

    root = Path(output_root).expanduser().resolve()
    run_dir = root / manifest.case_id / resolved_run_id
    if not run_dir.is_relative_to(root):
        raise RunLedgerError("运行目录超出输出根目录")

    try:
        artifact_dir = run_dir / "artifacts"
        artifact_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise RunLedgerError(f"运行目录已经存在：{run_dir}") from exc

    _write_json_atomic(
        run_dir / "manifest.json",
        manifest.model_dump(mode="json"),
    )

    status = RunStatus.COMPLETED
    error: str | None = None
    provider_record = _provider_record_from_manifest(manifest)

    try:
        provider_record = provider.generate(manifest, artifact_dir)
    except ProviderError as exc:
        status = RunStatus.FAILED
        error = str(exc)

    finished_at = _ensure_utc(now())
    artifacts = _collect_artifacts(artifact_dir)
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
        error=error,
    )
    _write_json_atomic(run_dir / "run.json", record.model_dump(mode="json"))
    return RunOutcome(record=record, directory=run_dir)


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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f".{path.name}.tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _provider_record_from_manifest(manifest: GenerationManifest) -> ProviderRecord:
    return ProviderRecord(
        name=manifest.provider.name,
        version=manifest.provider.version,
        model=manifest.provider.model,
        model_version=manifest.provider.model_version,
    )


def _new_run_id(started_at: datetime) -> str:
    timestamp = started_at.strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}-{secrets.token_hex(3)}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise RunLedgerError("运行时间必须包含时区")
    return value.astimezone(UTC)
