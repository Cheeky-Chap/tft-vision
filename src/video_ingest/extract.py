"""Deterministic frame extraction from a local gameplay video."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np

from src.video_ingest.labels import empty_labels
from src.video_ingest.models import (
    ExtractionOptions,
    FrameRecord,
    UsageRights,
    VideoManifest,
    VideoSource,
)


SUPPORTED_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".webm"})
MANAGED_FRAME_DIRECTORY = "frames"


class IngestError(Exception):
    """A safe, user-actionable video ingestion failure."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_input(path: Path) -> Path:
    raw = str(path)
    network_scheme = raw.split(":", 1)[0].lower() if ":" in raw else ""
    if network_scheme in {"http", "https", "ftp", "ftps", "rtsp"} or raw.startswith("//") or raw.startswith("\\\\"):
        raise IngestError("input must be a local file path, not a URL or network address")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise IngestError("unsupported input extension; expected mp4, mkv, mov, or webm")
    if not path.is_file():
        raise IngestError(f"input file does not exist or is not readable: {path.name}")
    try:
        with path.open("rb"):
            pass
    except OSError as exc:
        raise IngestError(f"input file is not readable: {path.name}") from exc
    return path.resolve()


def _validate_name(value: str, option: str) -> str:
    if not value or Path(value).name != value or value in {".", ".."}:
        raise IngestError(f"{option} must be a filename without directory components")
    return value


def _prepare_output(output_dir: Path, input_path: Path, overwrite: bool, manifest_name: str, labels_name: str) -> None:
    resolved = output_dir.resolve()
    if resolved == input_path.parent or resolved == input_path or resolved in input_path.parents:
        raise IngestError("output directory must not contain or replace the input video")
    output_dir.mkdir(parents=True, exist_ok=True)
    entries = list(output_dir.iterdir())
    if entries and not overwrite:
        raise IngestError("output directory is not empty; use --overwrite to replace managed outputs")
    if not overwrite:
        return

    manifest_path = output_dir / manifest_name
    managed_paths: list[Path] = [manifest_path, output_dir / labels_name]
    if manifest_path.is_file():
        try:
            previous = VideoManifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
            managed_paths.extend(output_dir / record.relative_path for record in previous.frames)
        except (OSError, ValueError):
            raise IngestError("existing manifest is invalid; refusing unsafe overwrite")
    managed_paths.append(output_dir / MANAGED_FRAME_DIRECTORY)
    for path in managed_paths:
        if path.is_file():
            path.unlink()
    frames_dir = output_dir / MANAGED_FRAME_DIRECTORY
    if frames_dir.is_dir():
        try:
            frames_dir.rmdir()
        except OSError:
            pass


def _difference_hash(frame: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.resize(gray, (16, 16), interpolation=cv2.INTER_AREA).astype(np.float32)


def ingest_video(
    input_path: Path,
    output_dir: Path,
    *,
    interval_seconds: float = 2.0,
    source_id: str,
    usage_rights: UsageRights = UsageRights.UNKNOWN,
    creator: str | None = None,
    original_url: str | None = None,
    dedupe_threshold: float | None = None,
    manifest_name: str = "manifest.json",
    labels_name: str = "labels.json",
    overwrite: bool = False,
    pretty: bool = False,
) -> VideoManifest:
    if interval_seconds <= 0:
        raise IngestError("interval-seconds must be a positive number")
    if dedupe_threshold is not None and dedupe_threshold < 0:
        raise IngestError("dedupe-threshold must be zero or greater")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", source_id):
        raise IngestError("source-id may contain only letters, numbers, dot, underscore, and hyphen")
    manifest_name = _validate_name(manifest_name, "manifest-name")
    labels_name = _validate_name(labels_name, "labels-name")
    source = _validate_input(input_path)
    _prepare_output(output_dir, source, overwrite, manifest_name, labels_name)

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise IngestError(f"input video could not be decoded: {source.name}")
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if fps <= 0 or frame_count <= 0 or width <= 0 or height <= 0:
        capture.release()
        raise IngestError(f"input video has invalid metadata: {source.name}")

    frames_dir = output_dir / MANAGED_FRAME_DIRECTORY
    frames_dir.mkdir(exist_ok=True)
    records: list[FrameRecord] = []
    previous_hash: np.ndarray | None = None
    step = 0
    try:
        while True:
            frame_number = round(step * interval_seconds * fps)
            if frame_number >= frame_count:
                break
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ok, frame = capture.read()
            if not ok or frame is None:
                raise IngestError(f"input video could not be decoded at frame {frame_number}")
            timestamp_ms = round(frame_number * 1000 / fps)
            current_hash = _difference_hash(frame)
            duplicate = (
                dedupe_threshold is not None
                and previous_hash is not None
                and float(np.mean(np.abs(current_hash - previous_hash))) <= dedupe_threshold
            )
            previous_hash = current_hash
            if not duplicate:
                frame_id = f"{source_id}-{frame_number:06d}-{timestamp_ms:012d}"
                filename = f"frame_{frame_number:06d}_{timestamp_ms:012d}.png"
                relative = f"{MANAGED_FRAME_DIRECTORY}/{filename}"
                target = output_dir / relative
                if target.exists():
                    raise IngestError(f"managed frame target already exists: {filename}")
                if not cv2.imwrite(str(target), frame):
                    raise IngestError(f"failed to write extracted frame: {filename}")
                records.append(
                    FrameRecord(
                        frame_id=frame_id,
                        relative_path=relative,
                        frame_number=frame_number,
                        timestamp_ms=timestamp_ms,
                        width=frame.shape[1],
                        height=frame.shape[0],
                        sha256=_sha256(target),
                    )
                )
            step += 1
    finally:
        capture.release()

    video_source = VideoSource(
        source_id=source_id,
        input_filename=source.name,
        usage_rights=usage_rights,
        creator=creator,
        original_url=original_url,
        sha256=_sha256(source),
        duration_seconds=frame_count / fps,
        fps=fps,
        width=width,
        height=height,
    )
    manifest = VideoManifest(
        source=video_source,
        extraction_options=ExtractionOptions(
            interval_seconds=interval_seconds, dedupe_threshold=dedupe_threshold
        ),
        frames=records,
    )
    indent = 2 if pretty else None
    (output_dir / manifest_name).write_text(
        json.dumps(manifest.model_dump(mode="json"), ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
    labels = empty_labels(source_id, [record.frame_id for record in records])
    (output_dir / labels_name).write_text(
        json.dumps(labels.model_dump(mode="json"), ensure_ascii=False, indent=indent) + "\n",
        encoding="utf-8",
    )
    return manifest
