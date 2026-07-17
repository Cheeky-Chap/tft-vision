"""Deterministic, failure-isolated execution of ROI recognizers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from src.recognition.base import Recognizer
from src.state import GameStateSnapshot, Observation


SUPPORTED_OUTPUTS = frozenset(
    {
        "player_gold",
        "player_level",
        "player_streak",
        "stage_info",
        "shop_slot_1",
        "shop_slot_2",
        "shop_slot_3",
        "shop_slot_4",
        "shop_slot_5",
        "my_board",
        "my_bench",
        "enemy_board",
        "enemy_bench",
    }
)


def _safe_error(exc: Exception) -> str:
    text = " ".join(str(exc).split())
    return f"{type(exc).__name__}: {text}" if text else type(exc).__name__


class RecognitionPipeline:
    """Run registered recognizers and assemble a complete snapshot."""

    def __init__(self, recognizers: Iterable[Recognizer] = ()) -> None:
        self._recognizers: dict[str, Recognizer] = {}
        for recognizer in recognizers:
            self.register(recognizer)

    def register(self, recognizer: Recognizer) -> None:
        if not recognizer.name:
            raise ValueError("recognizer name must not be empty")
        if recognizer.name in self._recognizers:
            raise ValueError(f"recognizer already registered: {recognizer.name}")
        invalid = set(recognizer.output_fields) - SUPPORTED_OUTPUTS
        if invalid:
            raise ValueError(f"unsupported output fields: {sorted(invalid)}")
        occupied = {
            field
            for current in self._recognizers.values()
            for field in current.output_fields
        }
        duplicates = occupied & set(recognizer.output_fields)
        if duplicates:
            raise ValueError(f"output fields already registered: {sorted(duplicates)}")
        self._recognizers[recognizer.name] = recognizer

    def run(
        self,
        rois: Mapping[str, np.ndarray],
        *,
        unavailable_rois: Iterable[str] = (),
        frame_id: str | None = None,
        session_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> GameStateSnapshot:
        unavailable = set(unavailable_rois)
        observations = {
            field: (
                Observation.unavailable(field)
                if field in unavailable or field not in rois
                else Observation.unknown(field)
            )
            for field in SUPPORTED_OUTPUTS
        }

        for name in sorted(self._recognizers):
            recognizer = self._recognizers[name]
            missing = set(recognizer.required_rois) - set(rois)
            if missing:
                for field in recognizer.output_fields:
                    observations[field] = Observation.unavailable(field)
                continue
            try:
                result = recognizer.recognize(rois)
                unexpected = set(result) - set(recognizer.output_fields)
                if unexpected:
                    raise ValueError(f"undeclared output fields: {sorted(unexpected)}")
                for field in recognizer.output_fields:
                    observations[field] = result.get(field, Observation.unknown(name))
            except Exception as exc:  # recognizers are an intentional isolation boundary
                message = _safe_error(exc)
                for field in recognizer.output_fields:
                    observations[field] = Observation.failed(name, message)

        return GameStateSnapshot(
            frame_id=frame_id,
            session_id=session_id,
            player_gold=observations["player_gold"],
            player_level=observations["player_level"],
            player_streak=observations["player_streak"],
            stage_info=observations["stage_info"],
            shop_slots=[observations[f"shop_slot_{index}"] for index in range(1, 6)],
            my_board=observations["my_board"],
            my_bench=observations["my_bench"],
            enemy_board=observations["enemy_board"],
            enemy_bench=observations["enemy_bench"],
            metadata=dict(metadata or {}),
        )
