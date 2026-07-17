import unittest

from pydantic import ValidationError

from src.state import Observation


class ObservationTests(unittest.TestCase):
    def test_confidence_range_is_validated(self):
        with self.assertRaises(ValidationError):
            Observation(value=1, confidence=1.01, status="observed", source="test")

    def test_non_observed_statuses_serialize(self):
        observations = [
            Observation.unknown("a"),
            Observation.unavailable("b"),
            Observation.failed("c", "safe failure"),
        ]
        self.assertEqual(
            [item.model_dump(mode="json")["status"] for item in observations],
            ["unknown", "unavailable", "error"],
        )
