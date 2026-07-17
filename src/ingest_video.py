"""CLI for ingesting a user-provided local gameplay video."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from src.video_ingest.extract import IngestError, ingest_video
from src.video_ingest.models import UsageRights


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def nonnegative_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be zero or greater")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract a labeled offline dataset from a local video.")
    parser.add_argument("--input", required=True, type=Path, help="local mp4, mkv, mov, or webm file")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--interval-seconds", type=positive_float, default=2.0)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--usage-rights", choices=[value.value for value in UsageRights], default="unknown")
    parser.add_argument("--creator")
    parser.add_argument("--original-url", help="provenance metadata only; no download is performed")
    parser.add_argument("--dedupe-threshold", type=nonnegative_float)
    parser.add_argument("--manifest-name", default="manifest.json")
    parser.add_argument("--labels-name", default="labels.json")
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest = ingest_video(
            args.input,
            args.output_dir,
            interval_seconds=args.interval_seconds,
            source_id=args.source_id,
            usage_rights=UsageRights(args.usage_rights),
            creator=args.creator,
            original_url=args.original_url,
            dedupe_threshold=args.dedupe_threshold,
            manifest_name=args.manifest_name,
            labels_name=args.labels_name,
            overwrite=args.overwrite,
            pretty=args.pretty,
        )
    except (IngestError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    summary = {
        "source_id": manifest.source.source_id,
        "frame_count": len(manifest.frames),
        "manifest": args.manifest_name,
        "labels": args.labels_name,
    }
    print(json.dumps(summary, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
