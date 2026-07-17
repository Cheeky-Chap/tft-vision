"""Interface implemented by future OCR and image recognizers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Set
from typing import Any

import numpy as np

from src.state import Observation


class Recognizer(ABC):
    """A side-effect-free recognizer operating on named ROI arrays."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Stable recognizer name used in diagnostics."""

    @property
    @abstractmethod
    def required_rois(self) -> Set[str]:
        """ROI names that must be supplied before this recognizer can run."""

    @property
    @abstractmethod
    def output_fields(self) -> Set[str]:
        """Snapshot fields produced, using ROI names for shop slots."""

    @abstractmethod
    def recognize(
        self, rois: Mapping[str, np.ndarray]
    ) -> Mapping[str, Observation[Any]]:
        """Return observations without mutating the input arrays."""
