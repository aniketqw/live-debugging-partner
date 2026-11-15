"""Handwritten transcription pairs for the calibration counter."""

import unittest
from scripts.calibrate_asr import differences


class CalibrationTests(unittest.TestCase):
    def test_exact_and_adjacent_swap(self):
        ref = "release one zero checkout-api"
        self.assertFalse(any(differences(ref, "release ten checkout-api").values()))
        self.assertEqual(differences(ref, "release zero one checkout-api")["digit_swaps"], 1)

    def test_substitution_drop_and_insertion_are_separate(self):
        self.assertEqual(differences("release one one", "release one zero")["digit_substitutions"], 1)
        self.assertEqual(differences("release one one", "release one")["digit_drops"], 1)
        self.assertEqual(differences("release one one", "release one one two")["digit_insertions"], 1)

    def test_service_identifier_error_is_visible(self):
        self.assertEqual(differences("checkout-api release eleven", "check-out-api release eleven")["service_errors"], 1)
