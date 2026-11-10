"""Command-line interface for SceneProof."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from sceneproof import __version__
from sceneproof.media import MediaInfo, MediaProbeError, probe_media


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""

    parser = argparse.ArgumentParser(
        prog="sceneproof",
        description="Evidence-based video verification for AI production workflows.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)
    probe_parser = subparsers.add_parser("probe", help="Inspect a local media file with FFprobe.")
    probe_parser.add_argument("path", type=Path, help="Path to the media file.")
    probe_parser.add_argument("--json", action="store_true", dest="as_json", help="Emit JSON.")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the SceneProof CLI."""

    _configure_text_streams()
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "probe":
        try:
            media_info = probe_media(args.path)
        except MediaProbeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2

        if args.as_json:
            print(json.dumps(_media_info_payload(media_info), ensure_ascii=False, indent=2))
        else:
            _print_media_summary(media_info)
        return 0

    parser.error(f"Unsupported command: {args.command}")


def _configure_text_streams() -> None:
    """Use UTF-8 for CLI output on Windows locales that default to a legacy code page."""

    for stream in (sys.stdout, sys.stderr):
        encoding = getattr(stream, "encoding", None)
        if isinstance(encoding, str) and encoding.lower().replace("-", "") == "utf8":
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8")


def _media_info_payload(media_info: MediaInfo) -> dict[str, object]:
    payload = asdict(media_info)
    payload["path"] = str(media_info.path)
    return payload


def _print_media_summary(media_info: MediaInfo) -> None:
    print(f"File: {media_info.path}")
    print(f"Format: {media_info.format_name or 'unknown'}")
    print(f"Duration: {_format_seconds(media_info.duration_seconds)}")
    print(f"Size: {_format_bytes(media_info.size_bytes)}")
    print(f"Video streams: {len(media_info.video_streams)}")

    for video_stream in media_info.video_streams:
        dimensions = _format_dimensions(video_stream.width, video_stream.height)
        frame_rate = _format_number(video_stream.frame_rate)
        print(
            f"  #{video_stream.index}: codec={video_stream.codec_name or 'unknown'}, "
            f"resolution={dimensions}, fps={frame_rate}"
        )

    print(f"Audio streams: {len(media_info.audio_streams)}")
    for audio_stream in media_info.audio_streams:
        print(
            f"  #{audio_stream.index}: codec={audio_stream.codec_name or 'unknown'}, "
            f"channels={audio_stream.channels or 'unknown'}, "
            f"sample_rate={audio_stream.sample_rate or 'unknown'}"
        )


def _format_dimensions(width: int | None, height: int | None) -> str:
    if width is None or height is None:
        return "unknown"
    return f"{width}x{height}"


def _format_seconds(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.3f}s"


def _format_bytes(value: int | None) -> str:
    if value is None:
        return "unknown"
    return f"{value} bytes"


def _format_number(value: float | None) -> str:
    if value is None:
        return "unknown"
    return f"{value:.3f}".rstrip("0").rstrip(".")
