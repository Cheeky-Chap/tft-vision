import json
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np
from pydantic import ValidationError

from src.ingest_video import build_parser
from src.video_ingest.extract import IngestError, ingest_video
from src.video_ingest.labels import EventType, SelectionEvent


def make_video(path: Path, colors: list[int], fps: float = 2.0) -> None:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (32, 24)
    )
    if not writer.isOpened():
        raise RuntimeError("synthetic video writer unavailable")
    for color in colors:
        writer.write(np.full((24, 32, 3), color, dtype=np.uint8))
    writer.release()


class VideoIngestTests(unittest.TestCase):
    def test_input_and_interval_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(IngestError, "unsupported input extension"):
                ingest_video(root / "clip.txt", root / "out", source_id="clip")
            with self.assertRaisesRegex(IngestError, "does not exist"):
                ingest_video(root / "missing.mp4", root / "out", source_id="clip")
            with self.assertRaisesRegex(IngestError, "local file path"):
                ingest_video(Path("https://example.com/clip.mp4"), root / "out", source_id="clip")
        with self.assertRaises(SystemExit):
            build_parser().parse_args(
                ["--input", "x.mp4", "--output-dir", "out", "--source-id", "x", "--interval-seconds", "0"]
            )

    def test_deterministic_manifest_relative_paths_and_unknown_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            video = root / "input.avi"
            make_video(video, [0, 30, 60, 90, 120], fps=2.0)
            # Rename after encoding so validation covers a required extension.
            source = root / "input.mp4"
            video.rename(source)
            first = root / "first"
            second = root / "second"
            manifest_a = ingest_video(source, first, interval_seconds=1, source_id="game-1")
            manifest_b = ingest_video(source, second, interval_seconds=1, source_id="game-1")

            keys_a = [(f.frame_id, f.frame_number, f.timestamp_ms) for f in manifest_a.frames]
            keys_b = [(f.frame_id, f.frame_number, f.timestamp_ms) for f in manifest_b.frames]
            self.assertEqual(keys_a, keys_b)
            self.assertEqual(keys_a, [("game-1-000000-000000000000", 0, 0), ("game-1-000002-000000001000", 2, 1000), ("game-1-000004-000000002000", 4, 2000)])
            payload = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
            serialized = json.dumps(payload)
            self.assertNotIn(str(root), serialized)
            self.assertTrue(all(not Path(frame["relative_path"]).is_absolute() for frame in payload["frames"]))
            labels = json.loads((first / "labels.json").read_text(encoding="utf-8"))
            self.assertEqual(labels["frames"][0]["view_target"], "unknown")
            self.assertIsNone(labels["frames"][0]["shop_visible"])
            self.assertEqual(labels["events"], [])

    def test_event_range_validation(self):
        with self.assertRaises(ValidationError):
            SelectionEvent(event_id="event-1", event_type=EventType.LEVEL_UP, start_ms=20, end_ms=10)

    def test_nonempty_output_and_overwrite_preserve_user_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            encoded = root / "clip.avi"
            make_video(encoded, [0, 50, 100])
            source = root / "clip.mkv"
            encoded.rename(source)
            output = root / "dataset"
            output.mkdir()
            user_file = output / "keep.txt"
            user_file.write_text("mine", encoding="utf-8")
            with self.assertRaisesRegex(IngestError, "not empty"):
                ingest_video(source, output, interval_seconds=1, source_id="clip")
            ingest_video(source, output, interval_seconds=1, source_id="clip", overwrite=True)
            user_frame = output / "frames" / "do-not-delete.txt"
            user_frame.write_text("mine too", encoding="utf-8")
            self.assertEqual(user_file.read_text(encoding="utf-8"), "mine")
            ingest_video(source, output, interval_seconds=1, source_id="clip", overwrite=True)
            self.assertEqual(user_file.read_text(encoding="utf-8"), "mine")
            self.assertEqual(user_frame.read_text(encoding="utf-8"), "mine too")

    def test_corrupt_video_fails_safely(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "broken.webm"
            source.write_bytes(b"not a video")
            with self.assertRaisesRegex(IngestError, "could not be decoded"):
                ingest_video(source, root / "out", source_id="broken")

    def test_dedupe_is_disabled_by_default_and_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            encoded = root / "same.avi"
            make_video(encoded, [40, 40, 80, 80], fps=1.0)
            source = root / "same.mov"
            encoded.rename(source)
            all_frames = ingest_video(source, root / "all", interval_seconds=1, source_id="same")
            unique = ingest_video(
                source, root / "unique", interval_seconds=1, source_id="same", dedupe_threshold=1.0
            )
            self.assertEqual(len(all_frames.frames), 4)
            self.assertEqual([frame.timestamp_ms for frame in unique.frames], [0, 2000])


if __name__ == "__main__":
    unittest.main()
