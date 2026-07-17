"""Serializable analysis records used by the offline review gallery."""

from __future__ import annotations

from enum import Enum
from pathlib import PurePosixPath
import re

from pydantic import BaseModel, Field, field_validator, model_validator

from src.state.models import GameStateSnapshot
from src.video_ingest.labels import ViewTarget


class SceneType(str, Enum):
    PLANNING = "planning"
    COMBAT = "combat"
    CAROUSEL = "carousel"
    AUGMENT_SELECT = "augment_select"
    ITEM_SELECT = "item_select"
    LOADING = "loading"
    UNKNOWN = "unknown"


class AnalysisStatus(str, Enum):
    COMPLETED = "completed"
    PARTIAL = "partial"
    PENDING = "pending"
    ERROR = "error"


def validate_relative_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not normalized or ".." in path.parts or ":" in path.parts[0]:
        raise ValueError("image path must be relative to the output directory")
    return normalized


def redact_absolute_paths(value: str | None) -> str | None:
    if value is None:
        return None
    # Error text may originate in local analyzers. Preserve the useful message,
    # but never persist Unix or Windows absolute paths in portable artifacts.
    value = re.sub(r"(?<![\w])(?:[A-Za-z]:[\\/]|/)(?:[^\s:]+[\\/])*[^\s:]*", "[path]", value)
    return value


class FrameAnalysisRecord(BaseModel):
    frame_id: str
    timestamp_ms: int = Field(ge=0)
    image_path: str
    scene_type: SceneType = SceneType.UNKNOWN
    view_target: ViewTarget = ViewTarget.UNKNOWN
    target_player: str | None = None
    state: GameStateSnapshot | None = None
    explanation: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    analysis_status: AnalysisStatus = AnalysisStatus.PENDING
    analysis_source: str | None = None
    error: str | None = None

    _relative_image_path = field_validator("image_path")(validate_relative_path)
    _safe_error = field_validator("error")(redact_absolute_paths)

    @model_validator(mode="after")
    def validate_analysis_result(self) -> "FrameAnalysisRecord":
        if self.explanation is not None and not self.explanation.strip():
            raise ValueError("explanation must be null instead of blank")
        if self.explanation is None and self.analysis_status == AnalysisStatus.COMPLETED:
            raise ValueError("completed analysis requires an explanation")
        if self.analysis_status == AnalysisStatus.PENDING and self.explanation is not None:
            raise ValueError("pending analysis cannot include an explanation")
        if self.analysis_status == AnalysisStatus.ERROR and not self.error:
            raise ValueError("error analysis requires an error message")
        if self.analysis_status != AnalysisStatus.ERROR and self.error is not None:
            raise ValueError("only error analysis may include an error message")
        return self
