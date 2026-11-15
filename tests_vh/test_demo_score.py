"""Scoring expectations for opted-in synthetic speech."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vh.demo_score import score


class DemoScoreTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "sample.jsonl"
        self.attempt = dict(scenario="S2", speaker_label="A", browser="Chrome", lang="en-IN",
                            transcript="Roll back staging checkout-api to release eleven.",
                            source="speech", consent=True)

    def test_normalized_digits_and_opt_in(self):
        response = score(self.attempt, self.path)
        self.assertTrue(response["digit_exact"])
        self.assertEqual(response["expected_digits"], "11")
        self.assertEqual(response["heard_digits"], "11")
        self.assertEqual(json.loads(self.path.read_text())["speaker_label"], "A")
        different = score({**self.attempt, "transcript": "release ten", "consent": False}, self.path)
        self.assertFalse(different["digit_exact"])
        self.assertEqual(different["heard_digits"], "10")
        self.assertEqual(len(self.path.read_text().splitlines()), 1)

    def test_typed_and_free_speech_are_excluded(self):
        for update in ({"source": "typed"}, {"scenario": "free"}):
            self.assertFalse(score({**self.attempt, **update}, self.path)["recorded"])
        self.assertFalse(self.path.exists())

    def test_missing_fields_and_real_names_rejected(self):
        for item in ({}, {**self.attempt, "speaker_label": "A real name"},
                     {**self.attempt, "consent": "yes"}):
            with self.assertRaises(ValueError):
                score(item, self.path)
