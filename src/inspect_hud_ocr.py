"""Inspect gold and level OCR from saved crops without capture or networking."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
from typing import Sequence
import cv2
from src.recognition import HudNumericRecognizer, RecognitionPipeline
from src.recognition.tesseract_cli import TesseractCli
from src.review.ocr_report import render_ocr_report

FIELDS = ("player_gold", "player_level")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create an offline gold/level OCR inspection report.")
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--tesseract-cmd", default="tesseract", help="executable name or path")
    parser.add_argument("--timeout", type=float, default=10.0, help="OCR timeout per crop")
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.input_dir.is_dir(): parser.error("input directory does not exist")
    if args.timeout <= 0: parser.error("timeout must be positive")
    if args.output_dir.exists() and not args.output_dir.is_dir():
        parser.error("output directory path is not a directory")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        parser.error("output directory must be empty")
    rois = {}
    for field in FIELDS:
        path = args.input_dir / f"{field}.png"
        image = cv2.imread(str(path), cv2.IMREAD_COLOR) if path.is_file() else None
        if image is not None: rois[field] = image
    recognizer = HudNumericRecognizer(TesseractCli(args.tesseract_cmd, args.timeout))
    snapshot = RecognitionPipeline([recognizer]).run(rois, unavailable_rois=set(FIELDS) - set(rois))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    debug = args.output_dir / "debug"
    debug.mkdir(exist_ok=True)
    for field, image in rois.items():
        cv2.imwrite(str(debug / f"{field}-original.png"), image)
        if field in recognizer.last_preprocessed:
            cv2.imwrite(str(debug / f"{field}-preprocessed.png"), recognizer.last_preprocessed[field])
    (args.output_dir / "result.json").write_text(
        json.dumps(snapshot.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    observations = {field: getattr(snapshot, field) for field in FIELDS}
    (args.output_dir / "report.html").write_text(render_ocr_report(observations, Path("debug")), encoding="utf-8")
    return 0

if __name__ == "__main__": raise SystemExit(main())
