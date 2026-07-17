import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import cv2
import numpy as np

from src.analyze_crops import main


class AnalyzeCropsTests(unittest.TestCase):
    def test_cli_reads_synthetic_image_and_emits_json(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertTrue(cv2.imwrite(str(root / "player_gold.png"), np.zeros((3, 3, 3))))
            output = StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["--input-dir", str(root)]), 0)
            payload = json.loads(output.getvalue())
            self.assertEqual(payload["player_gold"]["status"], "unknown")
            self.assertEqual(payload["player_level"]["status"], "unavailable")

    def test_unreadable_image_is_reported_as_unavailable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "stage_info.jpg").write_text("not an image", encoding="utf-8")
            target = root / "state.json"
            self.assertEqual(
                main(["--input-dir", str(root), "--output", str(target), "--pretty"]),
                0,
            )
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(payload["stage_info"]["status"], "unavailable")
            self.assertIn("stage_info", payload["metadata"]["load_errors"])
