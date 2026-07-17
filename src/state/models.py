"""Serializable recognition results for a single TFT frame."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field, model_validator


T = TypeVar("T")


class ObservationStatus(str, Enum):
    OBSERVED = "observed"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ERROR = "error"


class Observation(BaseModel, Generic[T]):
    """A value produced (or deliberately not produced) by a recognizer."""

    value: T | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    status: ObservationStatus = ObservationStatus.UNKNOWN
    source: str
    raw_text: str | None = None
    error: str | None = None

    @model_validator(mode="after")
    def validate_status_fields(self) -> "Observation[T]":
        if self.status != ObservationStatus.OBSERVED and self.value is not None:
            raise ValueError("only observed results may contain a value")
        if self.status == ObservationStatus.ERROR and not self.error:
            raise ValueError("error results must include an error message")
        if self.status != ObservationStatus.ERROR and self.error is not None:
            raise ValueError("only error results may include an error message")
        return self

    @classmethod
    def unknown(cls, source: str) -> "Observation[Any]":
        return cls(source=source, status=ObservationStatus.UNKNOWN)

    @classmethod
    def unavailable(cls, source: str) -> "Observation[Any]":
        return cls(source=source, status=ObservationStatus.UNAVAILABLE)

    @classmethod
    def failed(cls, source: str, message: str) -> "Observation[Any]":
        return cls(source=source, status=ObservationStatus.ERROR, error=message)


def _unknown(source: str) -> Observation[Any]:
    return Observation.unknown(source)


class GameStateSnapshot(BaseModel):
    """All currently supported observations for one offline or captured frame."""

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frame_id: str | None = None
    session_id: str | None = None
    player_gold: Observation[int] = Field(default_factory=lambda: _unknown("player_gold"))
    player_level: Observation[int] = Field(default_factory=lambda: _unknown("player_level"))
    player_streak: Observation[int] = Field(default_factory=lambda: _unknown("player_streak"))
    stage_info: Observation[str] = Field(default_factory=lambda: _unknown("stage_info"))
    shop_slots: list[Observation[Any]] = Field(
        default_factory=lambda: [_unknown(f"shop_slot_{index}") for index in range(1, 6)],
        min_length=5,
        max_length=5,
    )
    my_board: Observation[Any] = Field(default_factory=lambda: _unknown("my_board"))
    my_bench: Observation[Any] = Field(default_factory=lambda: _unknown("my_bench"))
    enemy_board: Observation[Any] = Field(default_factory=lambda: _unknown("enemy_board"))
    enemy_bench: Observation[Any] = Field(default_factory=lambda: _unknown("enemy_bench"))
    metadata: dict[str, Any] = Field(default_factory=dict)
