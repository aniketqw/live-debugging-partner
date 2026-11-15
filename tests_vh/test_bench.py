"""Run the real smoke benchmark offline and inspect the saved artifacts."""

import csv
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import unittest


class BenchTests(unittest.TestCase):
    def call(self, out, *options):
        return subprocess.run([sys.executable, "-m", "vh.bench", "--output-dir", str(out), *options],
                              text=True, capture_output=True)

    def test_smoke_reproducibility_shapes_and_barge_in(self):
        with TemporaryDirectory() as scratch:
            first, second = Path(scratch) / "one", Path(scratch) / "two"
            for address in (first, second):
                result = self.call(address, "--grid", "smoke")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual((first / "runs.csv").read_bytes(), (second / "runs.csv").read_bytes())
            self.assertEqual((first / "RESULTS.md").read_bytes(), (second / "RESULTS.md").read_bytes())
            report = (first / "RESULTS.md").read_text()
            self.assertIn("Limits", report)
            self.assertIn("V1 | PASS", report)
            for n in range(1, 9):
                self.assertIn(f"## T{n} ", report)
            with (first / "runs.csv").open(newline="") as file:
                rows = list(csv.DictReader(file))
            traces = list((first / "traces").glob("*.jsonl"))
            self.assertEqual(len(traces), len(rows))
            for sid in ("S1", "S2", "S3", "S4"):
                self.assertEqual({r["seed"] for r in rows if r["scenario"] == sid}, {"1"})
                self.assertEqual({r["mode"] for r in rows if r["scenario"] == sid},
                                 {"bare", "prompt_only", "harness"})
            by_mode = {r["mode"]: int(r["talk_over_ms"]) for r in rows if r["scenario"] == "S3"}
            self.assertGreater(by_mode["bare"], by_mode["harness"])

    def test_zero_request_cap_stops_before_local_inference(self):
        with TemporaryDirectory() as scratch:
            out = Path(scratch)
            result = self.call(out, "--grid", "quick", "--models", "llama3.1:latest",
                               "--request-mode", "live", "--allow-live-local", "--max-requests", "0")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("request cap reached", result.stdout)
            self.assertEqual(len(list((out / "traces").glob("*.jsonl"))), 0)
            self.assertIn("request_limit", (out / "RESULTS.md").read_text())
