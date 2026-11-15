"""Apply one invariant mutation at a time in isolated runtime module objects."""

from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tests_vh import test_runtime

SOURCE_PATH = ROOT / "vh/runtime.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
CASES = [
    ("I1", "test_I1_waits_for_confirm_and_bare_does_not", [
        ("if self.mode == \"harness\" and call.name == _ROLLBACK:\n                self._propose(call, prefix)",
         "if False:\n                self._propose(call, prefix)"),
    ]),
    ("I2", "test_I2_ignores_model_readback_when_arguments_disagree", [
        ("        job = self._new_job(call)\n        old = job.state",
         "        readback = self._model_text or readback\n        job = self._new_job(call)\n        old = job.state"),
        ("        response = self.model.respond(deepcopy(self.history), tool_schemas())",
         "        response = self.model.respond(deepcopy(self.history), tool_schemas())\n        self._model_text = response.text"),
    ]),
    ("I3", "test_I3_history_keeps_only_completed_prefix_after_cut", [
        ("        self._record_spoken(prefix)", "        self._record_spoken(spoken.text)"),
    ]),
    ("I4", "test_I4_determinism", [
        ("        self.trace.append(event)",
         "        import time\n        event['data']['wall_time'] = time.time()\n        self.trace.append(event)"),
    ]),
    ("I5", "test_I5_never_speaks_success_for_timed_out_tool", [
        ("        proposed = False\n        accepted = False",
         "        if response.tool_calls:\n            self._say(response.text)\n        proposed = False\n        accepted = False"),
    ]),
    ("I6", "test_I6_reusing_a_dispatched_call_id_cannot_change_release_again", [
        ("if call.id in self._attempted:", "if False:"),
        ("if confirmed.id not in self._attempted:", "if True:"),
    ]),
    ("I7", "test_I7_replaying_successful_tool_records_reconstructs_state", [
        ("        final = self.backend.snapshot()",
         "        self.backend._state['services']['checkout-api']['active_release'] = '99'\n        final = self.backend.snapshot()"),
    ]),
]


def run(name):
    return unittest.TextTestRunner(verbosity=2).run(test_runtime.RuntimeTests(name))


for invariant, test, replacements in CASES:
    mutated = SOURCE
    for before, after in replacements:
        assert mutated.count(before) == 1, before
        mutated = mutated.replace(before, after)
    module = ModuleType(f"_a9_mutant_{invariant}")
    module.__file__ = str(SOURCE_PATH)
    sys.modules[module.__name__] = module
    exec(compile(mutated, str(SOURCE_PATH), "exec"), module.__dict__)
    print(f"{invariant}: {test}", flush=True)
    with patch.object(test_runtime, "CallSession", module.CallSession), patch.object(
        test_runtime, "run_call", module.run_call
    ):
        result = run(test)
        assert result.failures and not result.errors, invariant
    assert run(test).wasSuccessful(), invariant
    print(f"PASS: {invariant} mutation failed as expected; restoration passed.", flush=True)
