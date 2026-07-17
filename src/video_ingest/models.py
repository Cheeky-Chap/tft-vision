"""Serializable provenance models for offline gameplay-video datasets."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class SourceKind(str, Enum):
    LOCAL_FILE = "local_file"


class UsageRights(str, Enum):
    OWNED = "owned"
    LICENSED = "licensed"
    PERMITTED = "permitted"
    UNKNOWN = "unknown"


class VideoSource(BaseModel):
    source_id: str
    input_filename: str
    source_kind: SourceKind = SourceKind.LOCAL_FILE
    usage_rights: UsageRights = UsageRights.UNKNOWN
    creator: str | None = None
    original_url: str | None = None
    sha256: str
    duration_seconds: float = Field(ge=0)
    fps: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ExtractionOptions(BaseModel):
    interval_seconds: float = Field(gt=0)
    dedupe_threshold: float | None = Field(default=None, ge=0)


class FrameRecord(BaseModel):
    frame_id: str
    relative_path: str
    frame_number: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    sha256: str

    @field_validator("relative_path")
    @classmethod
    def relative_paths_only(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        if normalized.startswith("/") or ":" in normalized.split("/")[0] or ".." in normalized.split("/"):
            raise ValueError("frame path must be relative to the output directory")
        return normalized


class VideoManifest(BaseModel):
    schema_version: str = "1.0"
    source: VideoSource
    extraction_options: ExtractionOptions
    frames: list[FrameRecord]

    @field_validator("frames")
    @classmethod
    def frames_are_deterministically_sorted(cls, value: list[FrameRecord]) -> list[FrameRecord]:
        expected = sorted(value, key=lambda frame: (frame.timestamp_ms, frame.frame_number, frame.frame_id))
        if value != expected:
            raise ValueError("frames must be sorted by timestamp, frame number, and frame ID")
        return value
