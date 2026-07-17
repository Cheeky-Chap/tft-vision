"""Explicit adapter for a locally installed Tesseract executable."""
from __future__ import annotations
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
import cv2
import numpy as np

@dataclass(frozen=True)
class TesseractResult:
    raw_text: str
    confidence: float

class TesseractUnavailable(RuntimeError): pass
class TesseractExecutionError(RuntimeError): pass

class TesseractCli:
    def __init__(self, command: str = "tesseract", timeout: float = 10.0) -> None:
        self.command, self.timeout = command, timeout

    def recognize_digits(self, image: np.ndarray) -> TesseractResult:
        with tempfile.TemporaryDirectory(prefix="tft-ocr-") as temporary:
            path = Path(temporary) / "input.png"
            if not cv2.imwrite(str(path), image):
                raise TesseractExecutionError("could not prepare OCR input")
            try:
                result = subprocess.run(
                    [self.command, str(path), "stdout", "--psm", "7", "-c",
                     "tessedit_char_whitelist=0123456789", "tsv"],
                    shell=False, capture_output=True, text=True,
                    timeout=self.timeout, check=False,
                )
            except FileNotFoundError as exc:
                raise TesseractUnavailable("Tesseract executable is unavailable") from exc
            except subprocess.TimeoutExpired as exc:
                raise TesseractExecutionError("Tesseract timed out") from exc
            except OSError as exc:
                raise TesseractUnavailable("Tesseract executable is unavailable") from exc
            if result.returncode:
                raise TesseractExecutionError("Tesseract exited unsuccessfully")
            return _parse_tsv(result.stdout)

def _parse_tsv(payload: str) -> TesseractResult:
    texts, scores = [], []
    for line in payload.splitlines()[1:]:
        columns = line.split("\t", 11)
        if len(columns) != 12 or not columns[11].strip():
            continue
        text = columns[11].strip()
        texts.append(text)
        try: score = float(columns[10])
        except ValueError: continue
        if score >= 0: scores.append((score, len(text)))
    weight = sum(size for _, size in scores)
    confidence = sum(score * size for score, size in scores) / weight / 100 if weight else 0.0
    return TesseractResult(" ".join(texts), max(0.0, min(1.0, confidence)))
