"""Dataset loading and dependency-free static HTML rendering."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Iterable

from pydantic import ValidationError

from src.review.models import AnalysisStatus, FrameAnalysisRecord, SceneType
from src.video_ingest.labels import EventType, Phase, VideoLabels
from src.video_ingest.models import VideoManifest


class ReviewReportError(ValueError):
    pass


def _load_model(path: Path, model_type):
    try:
        return model_type.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError, json.JSONDecodeError) as exc:
        raise ReviewReportError(f"could not read valid {path.name}: {type(exc).__name__}") from exc


def load_records(dataset_dir: Path, analyses_name: str = "analyses.jsonl") -> tuple[list[FrameAnalysisRecord], VideoLabels]:
    manifest = _load_model(dataset_dir / "manifest.json", VideoManifest)
    labels = _load_model(dataset_dir / "labels.json", VideoLabels)
    labels_by_id = {label.frame_id: label for label in labels.frames}
    analyses_path = dataset_dir / analyses_name
    if analyses_path.exists():
        loaded: list[FrameAnalysisRecord] = []
        try:
            for number, line in enumerate(analyses_path.read_text(encoding="utf-8").splitlines(), 1):
                if line.strip():
                    loaded.append(FrameAnalysisRecord.model_validate_json(line))
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            raise ReviewReportError(f"could not read valid {analyses_path.name} line {number}: {type(exc).__name__}") from exc
        known_ids = {frame.frame_id for frame in manifest.frames}
        if any(record.frame_id not in known_ids for record in loaded):
            raise ReviewReportError("analysis refers to a frame outside manifest.json")
        loaded_by_id = {record.frame_id: record for record in loaded}
        if len(loaded_by_id) != len(loaded):
            raise ReviewReportError("analyses.jsonl contains duplicate frame IDs")
        records = []
        for frame in manifest.frames:
            records.append(loaded_by_id.get(frame.frame_id) or _pending_record(frame, labels_by_id.get(frame.frame_id)))
        return records, labels

    records = []
    for frame in manifest.frames:
        records.append(_pending_record(frame, labels_by_id.get(frame.frame_id)))
    return records, labels


def _pending_record(frame, label) -> FrameAnalysisRecord:
    phase = label.phase.value if label else Phase.UNKNOWN.value
    scene_map = {value.value: value.value for value in SceneType}
    return FrameAnalysisRecord(
        frame_id=frame.frame_id,
        timestamp_ms=frame.timestamp_ms,
        image_path=frame.relative_path,
        scene_type=scene_map.get(phase, SceneType.UNKNOWN.value),
        view_target=label.view_target if label else "unknown",
        target_player=label.target_player if label else None,
    )


def write_records(path: Path, records: Iterable[FrameAnalysisRecord]) -> None:
    payload = "".join(record.model_dump_json(exclude_none=True) + "\n" for record in records)
    path.write_text(payload, encoding="utf-8")


def _event_kind(record: FrameAnalysisRecord, labels: VideoLabels) -> str:
    kinds: list[str] = []
    for event in labels.events:
        if event.start_ms <= record.timestamp_ms <= event.end_ms:
            if event.event_type == EventType.AUGMENT_SELECTED:
                kinds.append("augment")
            elif event.event_type == EventType.ITEM_SELECTED:
                kinds.append("item")
    if record.scene_type == SceneType.AUGMENT_SELECT:
        kinds.append("augment")
    if record.scene_type == SceneType.ITEM_SELECT:
        kinds.append("item")
    return " ".join(sorted(set(kinds))) or "none"


def _timestamp(timestamp_ms: int) -> str:
    minutes, seconds = divmod(timestamp_ms // 1000, 60)
    millis = timestamp_ms % 1000
    return f"{minutes:02d}:{seconds:02d}.{millis:03d}"


def render_html(records: list[FrameAnalysisRecord], labels: VideoLabels) -> str:
    cards: list[str] = []
    for record in records:
        raw = record.model_dump_json(indent=2, exclude_none=True)
        confidence = "미분석" if record.confidence is None else f"{record.confidence:.2f}"
        confidence_value = "-1" if record.confidence is None else f"{record.confidence:.6f}"
        explanation = record.explanation or "analysis_pending — AI 설명이 아직 생성되지 않았습니다."
        target = record.target_player or record.view_target.value
        summary = "구조화된 상태 없음" if record.state is None else html.escape(record.state.model_dump_json(exclude_none=True))
        cards.append(f'''<article class="frame" data-scene="{record.scene_type.value}" data-view="{record.view_target.value}" data-status="{record.analysis_status.value}" data-event="{_event_kind(record, labels)}" data-confidence="{confidence_value}">
<img loading="lazy" src="{html.escape(record.image_path, quote=True)}" alt="프레임 {html.escape(record.frame_id)}">
<div><h2>{html.escape(_timestamp(record.timestamp_ms))} · {record.scene_type.value}</h2>
<p>관전 대상: {html.escape(target)} · 상태: {record.analysis_status.value} · confidence: {confidence}</p>
<p>{html.escape(explanation)}</p><p class="summary">{summary}</p>
<details><summary>원본 JSON</summary><pre>{html.escape(raw)}</pre></details></div></article>''')
    return '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>TFT 오프라인 프레임 리뷰</title><style>
body{font-family:system-ui,sans-serif;margin:1rem;background:#111827;color:#e5e7eb}.filters{display:flex;flex-wrap:wrap;gap:.6rem;margin-bottom:1rem}.frame{display:grid;grid-template-columns:minmax(240px,40%) 1fr;gap:1rem;background:#1f2937;margin:1rem 0;padding:1rem;border-radius:.5rem}.frame img{width:100%;height:auto}.frame[hidden]{display:none}select,input{background:#fff;color:#111;padding:.35rem}pre{white-space:pre-wrap;word-break:break-word}@media(max-width:700px){.frame{grid-template-columns:1fr}}
</style></head><body><h1>TFT 오프라인 프레임 리뷰</h1><section class="filters" aria-label="필터">
<label>화면 <select id="scene"><option value="">전체</option><option>planning</option><option>combat</option><option>carousel</option><option>augment_select</option><option>item_select</option><option>loading</option><option>unknown</option></select></label>
<label>관전 <select id="view"><option value="">전체</option><option>self</option><option>enemy</option><option>carousel</option><option>unknown</option></select></label>
<label>상태 <select id="status"><option value="">전체</option><option>completed</option><option>partial</option><option>pending</option><option>error</option></select></label>
<label>이벤트 <select id="event"><option value="">전체</option><option>augment</option><option>item</option><option>none</option></select></label>
<label>최소 confidence <input id="minimum" type="number" min="0" max="1" step="0.05" value="0"></label>
<label>최대 confidence <input id="maximum" type="number" min="0" max="1" step="0.05" value="1"></label></section><main>''' + "".join(cards) + '''</main><script>
const ids=['scene','view','status','event','minimum','maximum'];function apply(){const v=Object.fromEntries(ids.map(id=>[id,document.getElementById(id).value]));document.querySelectorAll('.frame').forEach(x=>{const c=Number(x.dataset.confidence);x.hidden=!!((v.scene&&x.dataset.scene!==v.scene)||(v.view&&x.dataset.view!==v.view)||(v.status&&x.dataset.status!==v.status)||(v.event&&!x.dataset.event.split(' ').includes(v.event))||(c>=0&&(c<Number(v.minimum)||c>Number(v.maximum))))})}ids.forEach(id=>document.getElementById(id).addEventListener('input',apply));
</script></body></html>'''


def build_report(dataset_dir: Path, output: Path, analyses_name: str = "analyses.jsonl") -> int:
    dataset_dir = dataset_dir.resolve()
    output = output.resolve()
    try:
        output.relative_to(dataset_dir)
    except ValueError as exc:
        raise ReviewReportError("output must be inside the dataset directory") from exc
    analyses_path = (dataset_dir / analyses_name).resolve()
    protected_paths = {
        (dataset_dir / "manifest.json").resolve(),
        (dataset_dir / "labels.json").resolve(),
        analyses_path,
    }
    if output in protected_paths:
        raise ReviewReportError("output must not overwrite a dataset input")

    manifest = _load_model(dataset_dir / "manifest.json", VideoManifest)
    frame_paths = {(dataset_dir / frame.relative_path).resolve() for frame in manifest.frames}
    if output in frame_paths:
        raise ReviewReportError("output must not overwrite a dataset input")

    records, labels = load_records(dataset_dir, analyses_name)
    if not analyses_path.exists():
        write_records(analyses_path, records)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_html(records, labels), encoding="utf-8")
    return len(records)
