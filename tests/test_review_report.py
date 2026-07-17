import json
import os
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from src.build_review_report import build_parser
from src.review.explanations import TemplateExplanationGenerator
from src.review.models import AnalysisStatus, FrameAnalysisRecord, SceneType
from src.review.report import ReviewReportError, build_report, load_records, render_html
from src.state.models import GameStateSnapshot, Observation, ObservationStatus
from src.video_ingest.labels import EventType, FrameLabel, SelectionEvent, VideoLabels, ViewTarget
from src.video_ingest.models import ExtractionOptions, FrameRecord, VideoManifest, VideoSource


def record(**changes):
    values = dict(frame_id="frame-1", timestamp_ms=754000, image_path="frames/frame-1.jpg")
    values.update(changes)
    return FrameAnalysisRecord(**values)


class ReviewReportTests(unittest.TestCase):
    def test_output_help_describes_safe_report_path(self):
        help_text = " ".join(build_parser().format_help().split())
        self.assertIn("HTML file path inside the dataset directory", help_text)
        self.assertIn("manifest.json", help_text)
        self.assertIn("labels.json", help_text)
        self.assertIn("analyses JSONL file", help_text)
        self.assertIn("frame image path", help_text)

    def _dataset(self, root: Path) -> dict[str, Path]:
        source = VideoSource(source_id="game", input_filename="clip.mp4", sha256="a" * 64, duration_seconds=1, fps=1, width=10, height=10)
        frame = FrameRecord(frame_id="frame-1", relative_path="frames/frame-1.jpg", frame_number=0, timestamp_ms=0, width=10, height=10, sha256="b" * 64)
        paths = {
            "manifest": root / "manifest.json",
            "labels": root / "labels.json",
            "analyses": root / "analyses.jsonl",
            "frame": root / frame.relative_path,
        }
        paths["frame"].parent.mkdir()
        paths["manifest"].write_text(VideoManifest(source=source, extraction_options=ExtractionOptions(interval_seconds=1), frames=[frame]).model_dump_json(), encoding="utf-8")
        paths["labels"].write_text(VideoLabels(source_id="game", frames=[FrameLabel(frame_id="frame-1", phase="combat", view_target="self")]).model_dump_json(), encoding="utf-8")
        paths["analyses"].write_text(record(timestamp_ms=0).model_dump_json() + "\n", encoding="utf-8")
        paths["frame"].write_bytes(b"synthetic-frame-bytes")
        return paths

    def test_missing_explanation_is_pending_and_relative(self):
        item = record()
        self.assertEqual(item.analysis_status, AnalysisStatus.PENDING)
        self.assertIsNone(item.explanation)
        self.assertIsNone(json.loads(item.model_dump_json())["explanation"])
        with self.assertRaises(ValidationError):
            record(image_path="/private/frame.jpg")
        with self.assertRaises(ValidationError):
            record(explanation="", analysis_status="completed")

    def test_template_explanation_is_deterministic_and_does_not_guess(self):
        state = GameStateSnapshot(
            player_gold=Observation(value=32, confidence=.9, status=ObservationStatus.OBSERVED, source="test"),
            player_level=Observation.unknown("test"),
        )
        item = record(scene_type=SceneType.PLANNING, view_target=ViewTarget.SELF, state=state)
        generator = TemplateExplanationGenerator()
        first = generator.generate(item)
        self.assertEqual(first, generator.generate(item))
        self.assertIn("12분 34초", first)
        self.assertIn("골드는 32", first)
        self.assertIn("레벨은 확인 불가", first)
        self.assertNotIn("레벨은 1", first)

    def test_html_has_relative_image_timestamp_explanation_and_filters(self):
        item = record(scene_type="augment_select", view_target="enemy", explanation="관찰된 설명", confidence=.75, analysis_status="completed")
        labels = VideoLabels(source_id="game", frames=[FrameLabel(frame_id="frame-1")], events=[SelectionEvent(event_id="e", event_type=EventType.AUGMENT_SELECTED, start_ms=753000, end_ms=755000)])
        output = render_html([item], labels)
        self.assertIn('src="frames/frame-1.jpg"', output)
        self.assertIn("12:34.000", output)
        self.assertIn("관찰된 설명", output)
        self.assertIn('data-scene="augment_select" data-view="enemy" data-status="completed" data-event="augment" data-confidence="0.750000"', output)
        self.assertNotIn("https://", output)
        self.assertNotIn("http://", output)
        self.assertNotIn("src=\"//", output)

    def test_builds_pending_records_from_manifest_and_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = VideoSource(source_id="game", input_filename="clip.mp4", sha256="a" * 64, duration_seconds=1, fps=1, width=10, height=10)
            frame = FrameRecord(frame_id="frame-1", relative_path="frames/frame-1.jpg", frame_number=0, timestamp_ms=0, width=10, height=10, sha256="b" * 64)
            (root / "manifest.json").write_text(VideoManifest(source=source, extraction_options=ExtractionOptions(interval_seconds=1), frames=[frame]).model_dump_json(), encoding="utf-8")
            (root / "labels.json").write_text(VideoLabels(source_id="game", frames=[FrameLabel(frame_id="frame-1", phase="combat", view_target="self")]).model_dump_json(), encoding="utf-8")
            self.assertEqual(build_report(root, root / "review.html"), 1)
            analysis = json.loads((root / "analyses.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(analysis["analysis_status"], "pending")
            self.assertEqual(analysis["scene_type"], "combat")
            self.assertNotIn(str(root), (root / "review.html").read_text(encoding="utf-8"))
            with self.assertRaises(ReviewReportError):
                build_report(root, root.parent / "review.html")

    def test_rejects_dataset_inputs_without_changing_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self._dataset(root)
            for path in paths.values():
                before = path.read_bytes()
                with self.subTest(path=path.name), self.assertRaises(ReviewReportError):
                    build_report(root, path)
                self.assertEqual(path.read_bytes(), before)

    def test_rejects_dot_dot_normalization_bypass(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self._dataset(root)
            before = paths["labels"].read_bytes()
            with self.assertRaises(ReviewReportError):
                build_report(root, root / "frames" / ".." / "labels.json")
            self.assertEqual(paths["labels"].read_bytes(), before)

    def test_rejects_symlink_alias_bypass_when_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self._dataset(root)
            alias = root / "alias.html"
            try:
                os.symlink(paths["frame"], alias)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks are not supported")
            before = paths["frame"].read_bytes()
            with self.assertRaises(ReviewReportError):
                build_report(root, alias)
            self.assertEqual(paths["frame"].read_bytes(), before)

    def test_review_html_is_allowed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._dataset(root)
            self.assertEqual(build_report(root, root / "review.html"), 1)
            self.assertTrue((root / "review.html").is_file())

    def test_normal_execution_creates_analyses_and_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = self._dataset(root)
            paths["analyses"].unlink()
            self.assertEqual(build_report(root, root / "review.html"), 1)
            self.assertTrue(paths["analyses"].is_file())
            self.assertTrue((root / "review.html").is_file())

    def test_errors_do_not_disclose_absolute_paths(self):
        failed = record(analysis_status="error", error="decoder failed at /private/user/frame.png")
        self.assertEqual(failed.error, "decoder failed at [path]")
        self.assertNotIn("/private", failed.model_dump_json())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ReviewReportError) as caught:
                build_report(root, root / "review.html")
            self.assertNotIn(str(root), str(caught.exception))

    def test_partial_analysis_file_keeps_unanalyzed_manifest_frames_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = VideoSource(source_id="game", input_filename="clip.mp4", sha256="a" * 64, duration_seconds=2, fps=1, width=10, height=10)
            frames = [FrameRecord(frame_id=f"frame-{number}", relative_path=f"frames/{number}.jpg", frame_number=number, timestamp_ms=number * 1000, width=10, height=10, sha256=str(number) * 64) for number in (1, 2)]
            (root / "manifest.json").write_text(VideoManifest(source=source, extraction_options=ExtractionOptions(interval_seconds=1), frames=frames).model_dump_json(), encoding="utf-8")
            (root / "labels.json").write_text(VideoLabels(source_id="game", frames=[]).model_dump_json(), encoding="utf-8")
            completed = record(frame_id="frame-1", timestamp_ms=1000, image_path="frames/1.jpg", explanation="완료", analysis_status="completed")
            (root / "analyses.jsonl").write_text(completed.model_dump_json() + "\n", encoding="utf-8")
            records, _ = load_records(root)
            self.assertEqual([item.analysis_status for item in records], [AnalysisStatus.COMPLETED, AnalysisStatus.PENDING])


if __name__ == "__main__":
    unittest.main()
