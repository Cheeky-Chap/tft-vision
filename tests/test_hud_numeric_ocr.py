import subprocess
import unittest
from unittest.mock import patch

import numpy as np

from src.recognition.hud_numeric import HudNumericRecognizer, parse_numeric_observation
from src.recognition.tesseract_cli import TesseractCli, TesseractExecutionError, TesseractResult, TesseractUnavailable


class FakeTesseract:
    def __init__(self, results): self.results = iter(results)
    def recognize_digits(self, image): return next(self.results)


class HudNumericTests(unittest.TestCase):
    def test_boundaries_and_rejections(self):
        for field, accepted in (("player_gold", ("0", "999")), ("player_level", ("1", "10"))):
            for text in accepted:
                self.assertEqual(parse_numeric_observation(field, text, .8).status.value, "observed")
        for field, rejected in (("player_gold", ("-1", "1000", "1 2", "")), ("player_level", ("0", "11", "2x"))):
            for text in rejected:
                self.assertEqual(parse_numeric_observation(field, text, .8).status.value, "unknown")
        self.assertEqual(parse_numeric_observation("player_gold", "25", .49).status.value, "unknown")

    def test_recognizer_distinguishes_results(self):
        image = np.zeros((4, 4, 3), dtype=np.uint8)
        recognizer = HudNumericRecognizer(FakeTesseract([TesseractResult("25", .91), TesseractResult("", 0)]))
        result = recognizer.recognize({"player_gold": image, "player_level": image})
        self.assertEqual(result["player_gold"].value, 25)
        self.assertEqual(result["player_level"].status.value, "unknown")

    @patch("src.recognition.tesseract_cli.cv2.imwrite", return_value=True)
    @patch("src.recognition.tesseract_cli.subprocess.run")
    def test_cli_uses_safe_digit_configuration_and_parses_tsv(self, run, _write):
        run.return_value = subprocess.CompletedProcess([], 0, "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n5\t1\t1\t1\t1\t1\t0\t0\t1\t1\t92.5\t42\n", "")
        result = TesseractCli().recognize_digits(np.zeros((2, 2), dtype=np.uint8))
        self.assertEqual(result.raw_text, "42")
        self.assertAlmostEqual(result.confidence, .925)
        args = run.call_args.args[0]
        self.assertIn("--psm", args)
        self.assertIn("tessedit_char_whitelist=0123456789", args)
        self.assertFalse(run.call_args.kwargs["shell"])

    @patch("src.recognition.tesseract_cli.cv2.imwrite", return_value=True)
    @patch("src.recognition.tesseract_cli.subprocess.run", side_effect=FileNotFoundError)
    def test_missing_executable_is_unavailable(self, _run, _write):
        with self.assertRaises(TesseractUnavailable): TesseractCli().recognize_digits(np.zeros((1, 1), dtype=np.uint8))

    @patch("src.recognition.tesseract_cli.cv2.imwrite", return_value=True)
    @patch("src.recognition.tesseract_cli.subprocess.run", side_effect=subprocess.TimeoutExpired("tesseract", 1))
    def test_timeout_is_error(self, _run, _write):
        with self.assertRaises(TesseractExecutionError): TesseractCli().recognize_digits(np.zeros((1, 1), dtype=np.uint8))
