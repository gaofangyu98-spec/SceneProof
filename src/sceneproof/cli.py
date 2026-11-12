"""SceneProof 命令行入口。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from sceneproof import __version__
from sceneproof.ledger import ManifestError, RunLedgerError, RunOutcome, execute_run, load_manifest
from sceneproof.media import MediaInfo, MediaProbeError, probe_media
from sceneproof.models import RunStatus
from sceneproof.providers import create_provider
from sceneproof.providers.base import ProviderError


# 作用：构建命令行解析规则；处理：注册主命令、子命令和参数并返回解析器。
def build_parser() -> argparse.ArgumentParser:
    """创建主解析器并注册版本、probe 和 run 参数。

    返回的是命令行解析规则对象，不是命令执行后的参数结果。
    """
    parser = argparse.ArgumentParser(
        prog="sceneproof",
        description="面向 AI 视频生产链路的证据化质量验证工具。",
    )

    # --version 是特殊动作，输出版本后直接结束，不继续执行子命令。
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    probe_parser = subparsers.add_parser("probe", help="检查本地媒体文件。")
    probe_parser.add_argument("path", type=Path, help="媒体文件路径。")
    probe_parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON。")

    run_parser = subparsers.add_parser("run", help="执行生成清单并保存运行记录。")
    run_parser.add_argument("manifest", type=Path, help="生成清单 JSON 文件。")
    run_parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(".data/runs"),
        help="运行记录输出目录，默认 .data/runs。",
    )
    run_parser.add_argument("--run-id", help="指定运行编号，主要用于测试和复现。")
    run_parser.add_argument("--json", action="store_true", dest="as_json", help="输出 JSON。")

    return parser


# 作用：运行命令行程序；处理：解析命令，分发到 probe 或 run，并返回退出码。
def main(argv: Sequence[str] | None = None) -> int:
    """运行 SceneProof 命令行程序。"""

    _configure_text_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "probe":
        try:
            media_info = probe_media(args.path)
        except MediaProbeError as exc:
            print(f"错误：{exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(_media_info_payload(media_info), ensure_ascii=False, indent=2))
        else:
            _print_media_summary(media_info)
        return 0

    if args.command == "run":
        return _run_command(args)

    parser.error(f"不支持的命令：{args.command}")


# 作用：执行生成任务命令；处理：加载清单、选择提供器、运行并输出结果。
def _run_command(args: argparse.Namespace) -> int:
    try:
        manifest = load_manifest(args.manifest)
        provider = create_provider(manifest.provider.name)
        outcome = execute_run(
            manifest,
            args.output_dir,
            provider,
            run_id=args.run_id,
        )
    except (ManifestError, ProviderError, RunLedgerError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        return 2

    if args.as_json:
        print(outcome.record.model_dump_json(indent=2))
    else:
        _print_run_summary(outcome)

    if outcome.record.status is RunStatus.FAILED:
        print(f"生成失败：{outcome.record.error}", file=sys.stderr)
        return 2
    return 0


# 作用：统一终端编码；处理：在旧版 Windows 编码环境下将标准输出切换为 UTF-8。
def _configure_text_streams() -> None:
    """在旧版 Windows 编码环境下将标准输出切换为 UTF-8。"""

    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        if isinstance(encoding, str) and encoding.lower().replace("-", "") == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


# 作用：转换媒体信息；处理：把数据对象转成可序列化字典，并将路径转成字符串。
def _media_info_payload(media_info: MediaInfo) -> dict[str, object]:
    payload = asdict(media_info)
    payload["path"] = str(media_info.path)
    return payload


# 作用：打印媒体摘要；处理：输出格式、时长、大小以及视频流和音频流详情。
def _print_media_summary(media_info: MediaInfo) -> None:
    print(f"文件：{media_info.path}")
    print(f"格式：{media_info.format_name or '未知'}")
    print(f"时长：{_format_seconds(media_info.duration_seconds)}")
    print(f"大小：{_format_bytes(media_info.size_bytes)}")
    print(f"视频流数量：{len(media_info.video_streams)}")

    for video_stream in media_info.video_streams:
        dimensions = _format_dimensions(video_stream.width, video_stream.height)
        frame_rate = _format_number(video_stream.frame_rate)
        print(
            f"  #{video_stream.index}：编码={video_stream.codec_name or '未知'}，"
            f"分辨率={dimensions}，帧率={frame_rate}"
        )

    print(f"音频流数量：{len(media_info.audio_streams)}")
    for audio_stream in media_info.audio_streams:
        print(
            f"  #{audio_stream.index}：编码={audio_stream.codec_name or '未知'}，"
            f"声道={audio_stream.channels or '未知'}，"
            f"采样率={audio_stream.sample_rate or '未知'}"
        )


# 作用：打印运行摘要；处理：输出运行编号、状态、目录和全部产物信息。
def _print_run_summary(outcome: RunOutcome) -> None:
    record = outcome.record
    directory = outcome.directory
    status_text = "已完成" if record.status is RunStatus.COMPLETED else "失败"
    print(f"运行编号：{record.run_id}")
    print(f"用例编号：{record.case_id}")
    print(f"运行状态：{status_text}")
    print(f"运行目录：{directory}")
    print(f"产物数量：{len(record.artifacts)}")
    for artifact in record.artifacts:
        print(f"  - {artifact.path} ({artifact.size_bytes} 字节)")

    print(f"校验数量：{len(record.validations)}")
    for validation in record.validations:
        result_text = "通过" if validation.passed else "失败"
        print(f"  - {validation.artifact_path} [{result_text}] {validation.message}")


# 作用：格式化分辨率；处理：合法宽高转换为“宽x高”，缺失值返回“未知”。
def _format_dimensions(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "未知"
    return f"{width}x{height}"


# 作用：格式化时长；处理：保留三位小数并附加“秒”，缺失值返回“未知”。
def _format_seconds(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value:.3f} 秒"


# 作用：格式化文件大小；处理：输出字节数，缺失值返回“未知”。
def _format_bytes(value: int | None) -> str:
    if value is None:
        return "未知"
    return f"{value} 字节"


# 作用：格式化普通数字；处理：最多保留三位小数并去掉无意义的末尾零。
def _format_number(value: float | None) -> str:
    if value is None:
        return "未知"
    return f"{value:.3f}".rstrip("0").rstrip(".")
