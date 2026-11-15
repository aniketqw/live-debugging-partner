"""Known interval values and independently chosen paired differences."""

import unittest

from vh.stats import paired_boot, wilson


class StatisticsTests(unittest.TestCase):
    def test_wilson_known_binomial_intervals(self):
        cases = [
            (0, 10, (0.0, 0.0, 0.27753)),
            (10, 10, (1.0, 0.72247, 1.0)),
            (5, 10, (0.5, 0.23659, 0.76341)),
        ]
        for k, n, expected in cases:
            for actual, want in zip(wilson(k, n), expected):
                self.assertAlmostEqual(actual, want, places=5)
        self.assertEqual(wilson(0, 0), (None, None, None))
        with self.assertRaises(ValueError):
            wilson(2, 1)

    def test_paired_bootstrap_direction_and_same_seed(self):
        self.assertEqual(paired_boot([1, 1, 0], [0, 0, 0]), paired_boot([1, 1, 0], [0, 0, 0]))
        self.assertEqual(paired_boot([1, 1], [0, 0]), (1.0, 1.0, 1.0))
        self.assertEqual(paired_boot([], []), (None, None, None))
        with self.assertRaises(ValueError):
            paired_boot([1], [])
