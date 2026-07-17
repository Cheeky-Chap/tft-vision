"""Deterministic OCR recognizer for gold and level HUD crops."""
from __future__ import annotations
import re
from collections.abc import Mapping, Set
from typing import Any
import cv2
import numpy as np
from src.recognition.base import Recognizer
from src.recognition.tesseract_cli import TesseractCli, TesseractExecutionError, TesseractUnavailable
from src.state import Observation, ObservationStatus

FIELDS = {"player_gold": (0, 999), "player_level": (1, 10)}
MIN_CONFIDENCE = 0.5

def preprocess_numeric_hud(image: np.ndarray) -> np.ndarray:
    if image.size == 0: raise ValueError("empty ROI image")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image.copy()
    enlarged = cv2.resize(gray, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
    normalized = cv2.normalize(enlarged, None, 0, 255, cv2.NORM_MINMAX)
    denoised = cv2.medianBlur(normalized, 3)
    return cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

def parse_numeric_observation(field: str, raw_text: str, confidence: float) -> Observation[int]:
    cleaned, limits = raw_text.strip(), FIELDS[field]
    if (confidence < MIN_CONFIDENCE or not re.fullmatch(r"\d+", cleaned)
            or not limits[0] <= int(cleaned) <= limits[1]):
        return Observation(source="tesseract_hud_numeric", raw_text=raw_text, confidence=confidence)
    return Observation(value=int(cleaned), confidence=confidence, status=ObservationStatus.OBSERVED,
                       source="tesseract_hud_numeric", raw_text=raw_text)

class HudNumericRecognizer(Recognizer):
    def __init__(self, tesseract: TesseractCli | None = None) -> None:
        self.tesseract = tesseract or TesseractCli()
        self.last_preprocessed: dict[str, np.ndarray] = {}
    @property
    def name(self) -> str: return "tesseract_hud_numeric"
    @property
    def required_rois(self) -> Set[str]: return set()
    @property
    def output_fields(self) -> Set[str]: return set(FIELDS)
    def recognize(self, rois: Mapping[str, np.ndarray]) -> Mapping[str, Observation[Any]]:
        output = {}
        self.last_preprocessed = {}
        for field in FIELDS:
            if field not in rois:
                output[field] = Observation.unavailable(self.name)
                continue
            try:
                processed = preprocess_numeric_hud(rois[field])
                self.last_preprocessed[field] = processed
                result = self.tesseract.recognize_digits(processed)
                output[field] = parse_numeric_observation(field, result.raw_text, result.confidence)
            except TesseractUnavailable:
                output[field] = Observation.unavailable(self.name)
            except (TesseractExecutionError, cv2.error, ValueError) as exc:
                reason = str(exc) if isinstance(exc, TesseractExecutionError) else "OCR preprocessing failed"
                output[field] = Observation.failed(self.name, reason)
        return output
