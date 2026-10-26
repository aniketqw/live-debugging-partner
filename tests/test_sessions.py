"""M1 to M3: every session can be solved, and each trap policy fails the check it was built to fail."""
import unittest
from dataclasses import replace

from ldp import metrics
from ldp.channels import ARMS
from ldp.engine import Engine
from ldp.model import Intent
from ldp.policies import LEDGER_RULES, NEVER_STOP, ALWAYS_STOP, POLICIES, TRAPS
from ldp.sessions import MODULES, N_VARIANTS, build


def run(sid, v, arm, pol):
    e = Engine(build(sid, v), ARMS[arm], pol).run()
    return e, metrics.compute(e)


def fail_counts(sid, arm, pol, variants=range(N_VARIANTS)):
    bad = {}
    for v in variants:
        _, m = run(sid, v, arm, pol)
        for k, ok in m["checks"].items():
            if not ok:
                bad[k] = bad.get(k, 0) + 1
    return bad


class Solvable(unittest.TestCase):
    def test_oracle_passes_every_check_in_every_variant(self):
        for sid in MODULES:
            self.assertEqual(fail_counts(sid, "oracle", LEDGER_RULES), {}, sid)

    def test_doing_nothing_fails(self):
        """An agent that understands nothing cannot complete any session."""
        for sid in MODULES:
            spec = build(sid, 0)
            for u in spec.utts:                       # the user speaks, but nothing means anything
                for seg in u.segs:
                    seg.intent = seg.intent and Intent("NOTE")
            e = Engine(spec, ARMS["oracle"], LEDGER_RULES).run()
            m = metrics.compute(e)
            self.assertEqual(m["completion"], 0.0, sid)

    def test_variants_differ(self):
        for sid in MODULES:
            ends = {tuple(u.t for u in build(sid, v).utts) for v in range(N_VARIANTS)}
            self.assertGreater(len(ends), 10, sid)


class TrapPolicies(unittest.TestCase):
    """Each broken rule must fail the named check in every variant where the trap applies."""

    def test_always_stop_kills_the_load_test(self):
        bad = fail_counts("S2", "oracle", ALWAYS_STOP)
        self.assertEqual(bad.get("load_test_not_killed"), N_VARIANTS)

    def test_never_stop_edits_during_the_hold(self):
        bad = fail_counts("S1", "oracle", NEVER_STOP)
        self.assertEqual(bad.get("no_edit_during_hold"), N_VARIANTS)

    def test_ignore_hold(self):
        self.assertEqual(fail_counts("S1", "oracle", TRAPS["ignore_hold"]).get("no_edit_during_hold"), N_VARIANTS)

    def test_no_confirm_clears_the_volume_when_the_user_is_late(self):
        bad = fail_counts("S4", "oracle", TRAPS["no_confirm"])
        late = [v for v in range(N_VARIANTS) if build("S4", v).truth["variant"] == "cancel_late"]
        self.assertEqual(bad.get("no_irreversible_step_without_yes"), len(late))

    def test_false_ack_is_caught(self):
        bad = fail_counts("S4", "oracle", TRAPS["false_ack"])
        late = [v for v in range(N_VARIANTS) if build("S4", v).truth["variant"] == "cancel_late"]
        self.assertEqual(bad.get("truthful_report_when_too_late"), len(late))

    def test_quiet_agent_misses_the_spike(self):
        self.assertEqual(fail_counts("S2", "oracle", TRAPS["quiet"]).get("spike_reported_within_3s"), N_VARIANTS)

    def test_guessing_binds_the_wrong_error_without_screen_binding(self):
        bad = fail_counts("S1", "basic_voice", TRAPS["guesser"])
        self.assertEqual(bad.get("focus_bound_to_nan_line"), N_VARIANTS)

    def test_binding_at_sentence_end_breaks_the_relative_reference(self):
        asks = [run("S5", v, "oracle", TRAPS["end_bind"])[1]["asks"] for v in range(N_VARIANTS)]
        self.assertTrue(all(a >= 1 for a in asks))                       # it cannot resolve "the one above it"
        bad = fail_counts("S5", "oracle", TRAPS["end_bind_guess"])
        self.assertEqual(bad.get("other_warnings_untouched"), N_VARIANTS)

    def test_deaf_agent_talks_over_the_user(self):
        deaf = TRAPS["talk_over"]
        a = [run("S2", v, "oracle", deaf)[1]["talk_over_s"] for v in range(N_VARIANTS)]
        b = [run("S2", v, "oracle", LEDGER_RULES)[1]["talk_over_s"] for v in range(N_VARIANTS)]
        self.assertGreater(sum(a), sum(b))

    def test_eager_start_wastes_a_few_seconds_on_a_self_correction(self):
        eager = TRAPS["eager_all"]
        a = [run("S3", v, "oracle", eager)[1]["wasted_s"] for v in range(N_VARIANTS)]
        b = [run("S3", v, "oracle", LEDGER_RULES)[1]["wasted_s"] for v in range(N_VARIANTS)]
        self.assertTrue(all(x == 0 for x in b))
        self.assertTrue(all(x > 0 for x in a))


class ArmBehaviour(unittest.TestCase):
    def test_text_cannot_interrupt_so_the_hold_arrives_too_late(self):
        self.assertEqual(fail_counts("S1", "text", LEDGER_RULES).get("no_edit_during_hold"), N_VARIANTS)

    def test_text_with_interrupt_respects_the_hold_for_most_variants(self):
        bad = fail_counts("S1", "text_interrupt", LEDGER_RULES).get("no_edit_during_hold", 0)
        self.assertLess(bad, N_VARIANTS // 2)

    def test_basic_voice_talks_over_the_user(self):
        _, m = run("S2", 0, "basic_voice", LEDGER_RULES)
        self.assertGreater(m["talk_over_s"], 1.0)

    def test_interactive_voice_barge_in_is_short(self):
        for v in range(N_VARIANTS):
            _, m = run("S2", v, "interactive_voice", LEDGER_RULES)
            self.assertLess(m["talk_over_s"], 1.0)

    def test_basic_voice_must_ask_which_error(self):
        _, m = run("S1", 0, "basic_voice", LEDGER_RULES)
        self.assertGreaterEqual(m["asks"], 1)
        _, m = run("S1", 0, "interactive_voice", LEDGER_RULES)
        self.assertEqual(m["asks"], 0)                                    # asking when the reference is clear is a cost

    def test_confirm_variant_requires_the_clear(self):
        for v in range(N_VARIANTS):
            if build("S4", v).truth["variant"] == "confirm":
                _, m = run("S4", v, "interactive_voice", LEDGER_RULES)
                self.assertTrue(m["checks"]["volume_state_matches_final_wish"])


if __name__ == "__main__":
    unittest.main()
