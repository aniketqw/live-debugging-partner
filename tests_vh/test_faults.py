"""Synthetic speech fault tests with a handwritten staging regression snapshot."""

from random import Random
import unittest

from vh.faults import FaultConfig, inject


class FirstChoice:
    def random(self):
        return 0.0

    def choice(self, options):
        return options[0]


def undo_faults(transcript, faults):
    for entry in reversed(faults):
        index, before, after = entry["index"], entry["before"], entry["after"]
        end = index + len(after)
        if transcript[index:end] != after:
            raise AssertionError("edit did not match the logged transcript")
        transcript = transcript[:index] + before + transcript[end:]
    return transcript


class FaultTests(unittest.TestCase):
    def test_zero_probability_preserves_bytes_and_rng_state(self):
        reference = "  Roll  checkout-api\tback to one one\n"
        rng = Random(17)
        before = rng.getstate()
        self.assertEqual(inject(reference, rng, FaultConfig(0)), (reference, []))
        self.assertEqual(rng.getstate(), before)

    def test_repeats_for_same_seed_and_varies_across_seeds(self):
        reference = "Roll checkout-api back to release one one"
        cfg = FaultConfig(0.7)
        self.assertEqual(inject(reference, Random(8), cfg), inject(reference, Random(8), cfg))
        self.assertGreater(len({inject(reference, Random(seed), cfg)[0] for seed in range(12)}), 1)

    def test_individual_fault_kinds(self):
        cases = (
            ("digit_sub", "five", "nine", "five", "nine"),
            ("digit_sub", "11", "01", "11", "01"),
            ("digit_drop", "one", "", "one", ""),
            ("digit_swap", "one  and two", "two  and one", "one  and two", "two  and one"),
            ("name_homophone", "checkout-api", "check-out-api", "checkout-api", "check-out-api"),
            ("word_drop", "release", "", "release", ""),
        )
        for kind, text, want, before, after in cases:
            with self.subTest(kind=kind, text=text):
                output, edits = inject(text, FirstChoice(), FaultConfig(1, (kind,)))
                self.assertEqual(output, want)
                self.assertEqual(edits, [{"kind": kind, "index": 0, "before": before, "after": after}])
                self.assertEqual(undo_faults(output, edits), text)

    def test_one_faults_every_eligible_token_and_undo_preserves_whitespace(self):
        text = "  Roll  checkout-api\tone  two\n"
        cfg = FaultConfig(1, ("word_drop", "name_homophone", "digit_drop"))
        after, edits = inject(text, FirstChoice(), cfg)
        self.assertEqual([entry["before"] for entry in edits], ["Roll", "checkout-api", "one", "two"])
        self.assertEqual(undo_faults(after, edits), text)

    def test_regression_snapshot_for_seed_one(self):
        # Expected edits hand-traced from Random draws, not copied from inject.
        reference = "Roll checkout-api back to release one one"
        after, edits = inject(reference, Random(1), FaultConfig(0.15))
        self.assertEqual(after, " checkout-api back to release one won")
        self.assertEqual(edits, [
            {"kind": "word_drop", "index": 0, "before": "Roll", "after": ""},
            {"kind": "digit_sub", "index": 34, "before": "one", "after": "won"},
        ])
        self.assertEqual(undo_faults(after, edits), reference)

    def test_invalid_configuration_is_rejected(self):
        for p in (-0.01, 1.01, float("nan")):
            with self.subTest(p=p), self.assertRaises(ValueError):
                FaultConfig(p)
        with self.assertRaises(ValueError):
            FaultConfig(1, ("unsupported",))
