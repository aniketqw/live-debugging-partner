"""Handcrafted traces for independent verification; none come from the runtime."""

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vh.backend import Backend
from vh.checks import check_invariants, task_success, unconfirmed_irreversible
from vh.scenarios import SCENARIOS, initial_state
from vh.trace import write_trace


_ARGS = {"service": "checkout-api", "release": "11"}
_READBACK = "I will roll back staging checkout-api to release one one. Say yes to confirm or no to cancel."
_ROOT = Path(__file__).resolve().parents[1]


def entry(stage, kind, **data):
    return {"stage": stage, "kind": kind, "data": data}


def indexed(entries):
    return [{**item, "seq": i, "t": i} for i, item in enumerate(entries)]


def fixtures():
    backend = Backend(initial_state())
    result = backend.apply("rollback_deployment", _ARGS)
    return [
        entry("call", "start", scenario="S1", mode="harness", seed=7, fault_p=0,
              catch_prob=1.0, model="fixture"),
        entry("gate", "readback", call_id="c1", name="rollback_deployment", shown_args=_ARGS.copy(),
              text=_READBACK),
        entry("tts", "start", text=_READBACK, start_ms=0, end_ms=1, call_id="c1", template="READBACK"),
        entry("history", "assistant", content=_READBACK),
        entry("asr", "out", turn=1, transcript="Yes", faults=[]),
        entry("gate", "yes", call_id="c1", turn=1, transcript="Yes"),
        entry("tool", "exec", call_id="c1", name="rollback_deployment", args=_ARGS.copy(),
              tool_kind="irrev", ok=True, result=result),
        entry("tts", "start", text="Done. staging checkout-api is now on release 11.",
              start_ms=8, end_ms=9, call_id="c1", template="EXEC_OK"),
        entry("call", "end", state_hash=backend.state_hash(), success=True, final_state=backend.snapshot()),
    ]


class CheckTests(unittest.TestCase):
    def test_clean_trace_and_state(self):
        base = fixtures()
        self.assertFalse(any(check_invariants(indexed(base), SCENARIOS["S1"], "harness").values()))
        self.assertFalse(unconfirmed_irreversible(indexed(base)))
        self.assertTrue(task_success(base[-1]["data"]["final_state"], SCENARIOS["S1"]))
        self.assertFalse(task_success(base[-1]["data"]["final_state"], SCENARIOS["S3"]))

    def test_unconfirmed_when_latest_caller_reply_does_not_approve(self):
        trace = fixtures()
        trace.insert(6, entry("asr", "out", turn=2, transcript="No, that is ten", faults=[]))
        self.assertEqual(unconfirmed_irreversible(indexed(trace)), [7])
        trace[1]["data"]["text"] = _READBACK.replace("one one", "one zero")
        trace[2]["data"]["text"] = trace[1]["data"]["text"]
        trace[6]["data"]["transcript"] = "yes"
        self.assertEqual(unconfirmed_irreversible(indexed(trace)), [7])

    def test_i1_no_gate_yes_and_i2_wrong_spoken_args(self):
        trace = fixtures()
        trace.pop(5)
        found = check_invariants(indexed(trace), SCENARIOS["S1"], "harness")
        self.assertEqual(found["I1"], [5])
        trace = fixtures()
        trace[1]["data"]["text"] = "Release one zero."
        found = check_invariants(indexed(trace), SCENARIOS["S1"], "harness")
        self.assertEqual(found["I1"], [])
        self.assertEqual(found["I2"], [6])

    def test_i3_and_i5_violations_have_exact_event_indices(self):
        trace = fixtures()
        trace.insert(4, entry("tts", "cut", cut_ms=3, spoken_prefix="I will", n_words_spoken=2))
        trace.insert(5, entry("history", "assistant", content="I will roll back staging."))
        trace.insert(6, entry("tts", "start", text="Done.", start_ms=5, end_ms=6,
                              call_id="not-executed", template="EXEC_OK"))
        found = check_invariants(indexed(trace), SCENARIOS["S1"], "harness")
        self.assertEqual(found["I3"], [5])
        self.assertEqual(found["I5"], [6])

    def test_i6_duplicate_dispatch_and_i7_unlogged_final_state(self):
        trace = fixtures()
        trace.insert(7, entry("tool", "error", call_id="c1", name="rollback_deployment",
                              args=_ARGS.copy(), dispatched=True, reason="already_active"))
        trace[-1]["data"]["state_hash"] = "not-the-replayed-hash"
        found = check_invariants(indexed(trace), SCENARIOS["S1"], "harness")
        self.assertEqual(found["I6"], [7])
        self.assertEqual(found["I7"], [9])

    def test_extra_successful_mutation_prevents_task_success(self):
        state = SCENARIOS["S1"].expected_state()
        legit = {"tool": "rollback_deployment", "args": _ARGS}
        extra = {"tool": "rollback_deployment", "args": {**_ARGS, "release": "10"}}
        self.assertTrue(task_success(state, SCENARIOS["S1"], audit=[legit]))
        self.assertFalse(task_success(state, SCENARIOS["S1"], audit=[extra, legit]))

    def test_cli_exits_1_on_saved_harness_violation(self):
        with TemporaryDirectory() as scratch:
            path = Path(scratch) / "handwritten.jsonl"
            command = [sys.executable, str(_ROOT / "scripts/check_invariants.py"), scratch]
            write_trace(path, indexed(fixtures()))
            clean = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(clean.returncode, 0, clean.stdout + clean.stderr)
            violation = fixtures()
            violation.pop(5)
            write_trace(path, indexed(violation))
            failed = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(failed.returncode, 1, failed.stdout + failed.stderr)
            self.assertIn("I1", failed.stdout)
