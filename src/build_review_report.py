"""Build a browser-readable offline frame review gallery."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from src.review.report import ReviewReportError, build_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a dependency-free offline TFT frame review report.")
    parser.add_argument("--dataset-dir", required=True, type=Path, help="directory containing manifest.json and labels.json")
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help=(
            "HTML file path inside the dataset directory; must not be manifest.json, "
            "labels.json, the analyses JSONL file, or any frame image path"
        ),
    )
    parser.add_argument("--analyses-name", default="analyses.jsonl", help="analysis JSONL filename inside the dataset directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if Path(args.analyses_name).name != args.analyses_name:
        print("error: analyses name must be a filename", file=sys.stderr)
        return 2
    try:
        count = build_report(args.dataset_dir, args.output, args.analyses_name)
    except (ReviewReportError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"frame_count": count, "output": args.output.name}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
