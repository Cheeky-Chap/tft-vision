import unittest

import numpy as np

from src.recognition import RecognitionPipeline, Recognizer
from src.state import Observation


class StubRecognizer(Recognizer):
    def __init__(self, name, output, value=None, failure=None):
        self._name = name
        self._output = output
        self._value = value
        self._failure = failure

    @property
    def name(self):
        return self._name

    @property
    def required_rois(self):
        return {self._output}

    @property
    def output_fields(self):
        return {self._output}

    def recognize(self, rois):
        if self._failure:
            raise RuntimeError(self._failure)
        return {
            self._output: Observation(
                value=self._value,
                confidence=0.9,
                status="observed",
                source=self.name,
            )
        }


class PipelineTests(unittest.TestCase):
    def test_empty_input_produces_complete_snapshot(self):
        snapshot = RecognitionPipeline().run({})
        self.assertEqual(len(snapshot.shop_slots), 5)
        self.assertEqual(snapshot.player_gold.status.value, "unavailable")

    def test_failure_does_not_discard_other_result(self):
        pipeline = RecognitionPipeline(
            [
                StubRecognizer("gold", "player_gold", 12),
                StubRecognizer("level", "player_level", failure="bad model"),
            ]
        )
        image = np.zeros((2, 2, 3), dtype=np.uint8)
        snapshot = pipeline.run({"player_gold": image, "player_level": image})
        self.assertEqual(snapshot.player_gold.value, 12)
        self.assertEqual(snapshot.player_level.status.value, "error")
        self.assertIn("RuntimeError", snapshot.player_level.error)

    def test_registration_order_does_not_change_result(self):
        recognizers = [
            StubRecognizer("gold", "player_gold", 10),
            StubRecognizer("level", "player_level", 7),
        ]
        image = np.zeros((1, 1), dtype=np.uint8)
        rois = {"player_gold": image, "player_level": image}
        first = RecognitionPipeline(recognizers).run(rois).model_dump(
            exclude={"created_at"}
        )
        second = RecognitionPipeline(reversed(recognizers)).run(rois).model_dump(
            exclude={"created_at"}
        )
        self.assertEqual(first, second)
