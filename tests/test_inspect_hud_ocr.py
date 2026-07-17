import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from src.inspect_hud_ocr import main
from src.recognition.tesseract_cli import TesseractResult


class InspectHudOcrTests(unittest.TestCase):
    def test_writes_evidence_without_leaking_paths_or_external_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_dir, output_dir = root / "private-user-dir", root / "review"
            input_dir.mkdir()
            for field in ("player_gold", "player_level"):
                cv2.imwrite(str(input_dir / f"{field}.png"), np.full((8, 12, 3), 180, dtype=np.uint8))
            with patch("src.recognition.tesseract_cli.TesseractCli.recognize_digits", side_effect=[TesseractResult("50", .9), TesseractResult("7", .8)]):
                self.assertEqual(main(["--input-dir", str(input_dir), "--output-dir", str(output_dir), "--tesseract-cmd", str(root / "secret" / "tesseract.exe")]), 0)
            payload = json.loads((output_dir / "result.json").read_text())
            self.assertEqual(payload["player_gold"]["status"], "observed")
            self.assertEqual(payload["player_level"]["value"], 7)
            report = (output_dir / "report.html").read_text()
            combined = report + (output_dir / "result.json").read_text()
            self.assertNotIn(str(root), combined)
            self.assertNotIn("http://", report)
            self.assertNotIn("https://", report)
            for field in ("player_gold", "player_level"):
                self.assertTrue((output_dir / "debug" / f"{field}-original.png").is_file())
                self.assertTrue((output_dir / "debug" / f"{field}-preprocessed.png").is_file())
                self.assertIn(field, report)
            for text in ("raw text", "value", "confidence", "status"):
                self.assertIn(text, report)

    def test_rejects_nonempty_output_to_prevent_stale_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            input_dir, output_dir = root / "input", root / "review"
            input_dir.mkdir()
            output_dir.mkdir()
            stale = output_dir / "stale.png"
            stale.write_bytes(b"keep")
            with self.assertRaises(SystemExit):
                main(["--input-dir", str(input_dir), "--output-dir", str(output_dir)])
            self.assertEqual(stale.read_bytes(), b"keep")
