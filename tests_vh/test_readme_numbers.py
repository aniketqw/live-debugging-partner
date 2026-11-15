"""Manually chosen data for the README number guard."""

from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


_SCRIPT = Path(__file__).resolve().parents[1] / "scripts/check_readme_numbers.py"


class ReadmeGuardTests(unittest.TestCase):
    def run_fixture(self, readme_text):
        with TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / "readme.md").write_text(readme_text)
            (root / "results.md").write_text("Baseline: 112 runs, proportion 0.925, 75%.")
            (root / "allow.json").write_text('["3.12"]')
            return subprocess.run([sys.executable, str(_SCRIPT),
                                   "--readme", str(root / "readme.md"),
                                   "--results", str(root / "results.md"),
                                   "--allowlist", str(root / "allow.json")],
                                  text=True, capture_output=True)

    def test_known_numbers_and_documented_runtime_version_pass(self):
        result = self.run_fixture("Python 3.12; 112 runs and 0.925. [trace](traces/00007.jsonl)")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_substring_of_a_result_and_changed_percent_fail(self):
        result = self.run_fixture("Claimed 12 runs and 76%.")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("12", result.stdout)
        self.assertIn("76%", result.stdout)
