"""Independent staging fixtures and scripted caller behavior."""

from random import Random
import unittest

from tests_vh.test_faults import undo_faults
from vh.caller import ScriptedCaller, hear_turn, random_streams
from vh.confirm import render
from vh.faults import FaultConfig, inject
from vh.scenarios import SCENARIOS, initial_state


class ScenarioTests(unittest.TestCase):
    def test_demonstration_scenarios_and_expected_states(self):
        self.assertEqual(set(SCENARIOS), {"S1", "S2", "S3", "S4"})
        self.assertEqual(initial_state(), {"services": {"checkout-api": {
            "environment": "staging", "active_release": "12",
            "rollback_targets": ["10", "11"],
        }}})
        for sid, release in {"S1": "11", "S2": "11", "S3": "12", "S4": "12"}.items():
            scenario = SCENARIOS[sid]
            expected = initial_state()
            expected["services"]["checkout-api"]["active_release"] = release
            self.assertEqual(scenario.expected_state(), expected)
            self.assertEqual(scenario.intended, {"service": "checkout-api", "release": "11"})
        self.assertIsNone(SCENARIOS["S1"].backend_fault)
        self.assertEqual(SCENARIOS["S4"].backend_fault, "timeout_first")
        self.assertEqual(SCENARIOS["S3"].turns[-1].role, "forced")

    def test_caller_matches_only_a_complete_readback(self):
        caller = ScriptedCaller(SCENARIOS["S1"], Random(4), 1)
        self.assertEqual(caller.reply(render("READBACK_rollback_deployment",
                                            service="checkout-api", release="one one")), "yes")
        self.assertEqual(caller.reply("staging checkout-api release one one"), "No, it is one one.")

    def test_correction_can_be_missed_or_cancel_after_three_corrections(self):
        incorrect = render("READBACK_rollback_deployment", service="checkout-api", release="one zero")
        always = ScriptedCaller(SCENARIOS["S2"], Random(3), 1)
        never = ScriptedCaller(SCENARIOS["S2"], Random(3), 0)
        self.assertEqual(never.reply(incorrect), "yes")
        self.assertEqual([always.reply(incorrect) for _ in range(4)],
                         ["No, it is one one."] * 3 + ["cancel"])
        self.assertEqual(always.reply(incorrect), "cancel")

    def test_fixed_mishearing_is_logged_and_reversible_without_random_faults(self):
        turn = SCENARIOS["S2"].turns[0]
        transcript, edits = hear_turn(turn, Random(9), FaultConfig(0))
        self.assertEqual(turn.say, "Roll back staging checkout-api to release one one.")
        self.assertEqual(transcript, "Roll back staging checkout-api to release one zero.")
        self.assertEqual(len(edits), 1)
        self.assertEqual(undo_faults(transcript, edits), turn.say)

    def test_changing_catch_probability_does_not_change_asr_stream(self):
        wrong = render("READBACK_rollback_deployment", service="checkout-api", release="one zero")
        cfg = FaultConfig(0.5)
        groups = []
        for catch in (0, 1):
            caller_rng, asr_rng = random_streams(9)
            caller = ScriptedCaller(SCENARIOS["S2"], caller_rng, catch)
            heard = []
            for _ in range(3):
                caller.reply(wrong)
                heard.append(inject("Roll back release one one", asr_rng, cfg))
            groups.append(heard)
        self.assertEqual(groups[0], groups[1])
