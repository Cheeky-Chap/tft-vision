"""Build a structured JSON snapshot from previously saved ROI images."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

import cv2
import numpy as np

from src.recognition import RecognitionPipeline
from src.recognition.pipeline import SUPPORTED_OUTPUTS


IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg"})


def _candidates(input_dir: Path, roi_name: str) -> list[Path]:
    direct = [input_dir / f"{roi_name}{suffix}" for suffix in sorted(IMAGE_EXTENSIONS)]
    nested_dir = input_dir / roi_name
    nested = (
        sorted(
            path
            for path in nested_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if nested_dir.is_dir()
        else []
    )
    return [path for path in direct if path.is_file()] + nested


def load_rois(input_dir: Path) -> tuple[dict[str, np.ndarray], set[str], dict[str, str]]:
    """Load exactly one image per supported ROI using documented path rules."""

    rois: dict[str, np.ndarray] = {}
    unavailable: set[str] = set()
    errors: dict[str, str] = {}
    for roi_name in sorted(SUPPORTED_OUTPUTS):
        candidates = _candidates(input_dir, roi_name)
        if not candidates:
            unavailable.add(roi_name)
            continue
        if len(candidates) > 1:
            unavailable.add(roi_name)
            errors[roi_name] = "multiple image files found; keep exactly one"
            continue
        image = cv2.imread(str(candidates[0]), cv2.IMREAD_COLOR)
        if image is None:
            unavailable.add(roi_name)
            errors[roi_name] = f"unreadable image: {candidates[0].name}"
            continue
        rois[roi_name] = image
    return rois, unavailable, errors


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an offline game-state JSON snapshot from saved ROI crops."
    )
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output", type=Path, help="write JSON here instead of stdout")
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.input_dir.is_dir():
        parser.error(f"input directory does not exist: {args.input_dir}")

    rois, unavailable, errors = load_rois(args.input_dir)
    snapshot = RecognitionPipeline().run(
        rois,
        unavailable_rois=unavailable,
        frame_id=args.input_dir.name,
        metadata={"input_dir": str(args.input_dir), "load_errors": errors},
    )
    payload = snapshot.model_dump(mode="json")
    rendered = json.dumps(payload, indent=2 if args.pretty else None, ensure_ascii=False)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
