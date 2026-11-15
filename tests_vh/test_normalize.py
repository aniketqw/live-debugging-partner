"""Handwritten staging release expectations; no real audio."""

import csv
from pathlib import Path
from random import Random
import unittest

from vh.normalize import despeak, normalize, spoken_form


DATA = Path(__file__).parent / "data"


class NormalizeTests(unittest.TestCase):
    def test_handwritten_development_csv(self):
        with (DATA / "spoken_numbers_dev.csv").open(encoding="utf-8", newline="") as file:
            examples = list(csv.DictReader(file))
        self.assertGreaterEqual(len(examples), 60)
        for case in examples:
            with self.subTest(spoken=case["spoken"]):
                self.assertEqual(normalize(case["spoken"])[0], case["expected"])

    def test_release_readback_preserves_zeroes(self):
        self.assertEqual(spoken_form("01", "release"), "zero one")
        self.assertEqual(despeak("zero one", "release"), "01")
        rng = Random(172)
        for _ in range(200):
            value = f"{rng.randrange(100):02d}"
            self.assertEqual(despeak(spoken_form(value, "release"), "release"), value)

    def test_invalid_release_readback_rejects(self):
        for value in ("a1", "11 12", "１１", ""):
            with self.subTest(value=value), self.assertRaises(ValueError):
                spoken_form(value, "release")
        with self.assertRaises(ValueError):
            despeak("eleven", "release")

    def test_spans_name_original_exact_source_slice(self):
        source = "Use TWENTY-one; release  zero\tone."
        text, spans = normalize(source)
        self.assertEqual(text, "Use 21; release  01.")
        self.assertEqual(spans, [
            {"orig": "TWENTY-one", "value": "21", "start": 4, "end": 14},
            {"orig": "zero\tone", "value": "01", "start": 25, "end": 33},
        ])

    def test_unsupported_run_does_not_leak_a_numeric_target(self):
        text = "Roll back to eleven hundred!"
        result, spans = normalize(text)
        self.assertEqual(result, text)
        self.assertEqual(spans, [{"orig": "eleven hundred", "value": None, "start": 13, "end": 27}])

    def test_human_authored_heldout_if_available(self):
        path = DATA / "spoken_numbers_heldout.csv"
        if not path.exists():
            print("no held-out set yet")
            return
        with path.open(encoding="utf-8", newline="") as file:
            examples = list(csv.DictReader(file))
        matches = sum(normalize(r["spoken"])[0] == r["expected"] for r in examples)
        print(f"held-out set: {matches} exact matches from {len(examples)} cases")
