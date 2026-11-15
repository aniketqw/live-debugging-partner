"""Engine checks on tiny sessions where the answer can be counted by hand."""
import unittest
from dataclasses import replace

from ldp.channels import ARMS, GRID_ARMS
from ldp.engine import Engine
from ldp.metrics import overlap_ms
from ldp.model import Intent, Part, SessionSpec, make_utt
from ldp.policies import LEDGER_RULES, TRAPS
from ldp.sessions.base import App


class Toy(App):
    def __init__(self):
        self.done = False

    def on_intent(self, ctx, it, target):
        if it.kind == "TASK" and it.args["name"] == "work":
            def done(c, job):
                self.done = True
            ctx.new_job("work", "ro", 5000, on_done=done)
        if it.kind == "TASK" and it.args["name"] == "talk":
            ctx.say("one two three four five six seven eight nine ten")

    def finalize(self, ctx):
        return [("work_done", "task", self.done)]


def toy_spec(utts, end=60_000):
    return SessionSpec("TOY", 0, utts, selection=[(0, "x")], sys_events=[], app_factory=Toy,
                       end_ms=end, truth={"order": []})


class EngineTests(unittest.TestCase):
    def test_fairness_without_interruptions_all_arms_agree(self):
        """With nothing to interrupt, every arm must reach the same outcome."""
        u = make_utt("toy.u0", 0, [Part("Please do the work.", Intent("TASK", {"name": "work", "ro": True}))])
        for arm in GRID_ARMS + ["oracle"]:
            e = Engine(toy_spec([u]), ARMS[arm], LEDGER_RULES).run()
            self.assertTrue(e.app.done, arm)
            self.assertEqual(e.app.finalize(e)[0][2], True)

    def test_determinism(self):
        from ldp.sessions import build
        for arm in GRID_ARMS:
            a = Engine(build("S2", 3), ARMS[arm], LEDGER_RULES).run().log
            b = Engine(build("S2", 3), ARMS[arm], LEDGER_RULES).run().log
            self.assertEqual(a, b, arm)

    def test_lag_jitter_does_not_depend_on_arm_or_policy(self):
        from ldp.sessions import build
        spec = build("S1", 4)
        u = spec.utts[1]
        vals = {Engine(build("S1", 4), ARMS[a], p).lag("stream_lag_ms", u, 0)
                for a in GRID_ARMS for p in (LEDGER_RULES, TRAPS["quiet"])}
        self.assertEqual(len(vals), 1)

    def test_talk_over_matches_hand_count(self):
        """Agent talks 10 words = 4200 ms. A second user sentence starts 1000 ms after it starts."""
        u0 = make_utt("toy.u0", 0, [Part("Talk.", Intent("TASK", {"name": "talk"}))])
        agent_start = -(-u0.dur_ms // 100) * 100                # oracle arm: no lag, rounded up to a tick
        u1 = make_utt("toy.u1", agent_start + 1000, [Part("Hold on.", Intent("STOP_SPEECH"))])
        # a policy that does not listen, so nothing cuts the agent
        pol = replace(LEDGER_RULES, name="deaf", listens=False)
        # a harmless meaning, so nothing cuts the agent and the hand count stays simple
        u1.segs[0].intent = Intent("NOTE")
        e = Engine(toy_spec([u0, u1]), ARMS["oracle"], pol).run()
        self.assertEqual(e.speech_log[0], (agent_start, agent_start + 4200))
        self.assertEqual(overlap_ms(e.speech_log, e.user_speech), u1.dur_ms)

    def test_stop_speech_cuts_the_agent(self):
        u0 = make_utt("toy.u0", 0, [Part("Talk.", Intent("TASK", {"name": "talk"}))])
        agent_start = -(-u0.dur_ms // 100) * 100
        u1 = make_utt("toy.u1", agent_start + 1000, [Part("Stop talking.", Intent("STOP_SPEECH"))])
        e = Engine(toy_spec([u0, u1]), ARMS["oracle"], LEDGER_RULES).run()
        a, b = e.speech_log[0]
        self.assertLess(b - agent_start, 4200)                  # cut short
        self.assertLessEqual(b - u1.t, e.P.tick_ms * 3 + 0)     # within about 300 ms of the onset (oracle: 0 lag)

    def test_queue_arms_wait_until_idle(self):
        """Text and basic voice deliver a message only when the agent is idle."""
        u0 = make_utt("toy.u0", 0, [Part("Work.", Intent("TASK", {"name": "work", "ro": True}))])
        u1 = make_utt("toy.u1", 1000, [Part("Work again.", Intent("TASK", {"name": "work", "ro": True}))])
        et = Engine(toy_spec([u0, u1]), ARMS["text"], LEDGER_RULES).run()
        ei = Engine(toy_spec([u0, u1]), ARMS["text_interrupt"], LEDGER_RULES).run()
        starts_t = [t for t, ev, kw in et.log if ev == "job_start"]
        starts_i = [t for t, ev, kw in ei.log if ev == "job_start"]
        self.assertGreaterEqual(starts_t[1], starts_t[0] + 5000)   # waited for the first job
        self.assertLess(starts_i[1], starts_i[0] + 5000)           # did not wait

    def test_off_app_time_counts_only_when_hands_are_on_the_app(self):
        u = make_utt("toy.u0", 0, [Part("Work.", Intent("TASK", {"name": "work", "ro": True}))], hands_on=True)
        e = Engine(toy_spec([u]), ARMS["text_interrupt"], LEDGER_RULES).run()
        self.assertEqual(e.off_app_ms, e.P.switch_ms + u.typed_words * e.P.type_ms_per_word + e.P.send_ms)
        u2 = make_utt("toy.u0", 0, [Part("Work.", Intent("TASK", {"name": "work", "ro": True}))], hands_on=False)
        self.assertEqual(Engine(toy_spec([u2]), ARMS["text_interrupt"], LEDGER_RULES).run().off_app_ms, 0)
        self.assertEqual(Engine(toy_spec([u]), ARMS["interactive_voice"], LEDGER_RULES).run().off_app_ms, 0)

    def test_repeat_and_original_count_once(self):
        """If a message is queued and the user repeats it, the agent acts on it once."""
        u0 = make_utt("toy.u0", 0, [Part("Work.", Intent("TASK", {"name": "work", "ro": True}))])
        u1 = make_utt("toy.u1", 500, [Part("Work now.", Intent("TASK", {"name": "work", "ro": True}))],
                      must_apply=True, patience_ms=1500)
        e = Engine(toy_spec([u0, u1], end=60_000), ARMS["basic_voice"], LEDGER_RULES).run()
        self.assertEqual(e.repeats, 1)
        self.assertEqual(len([1 for t, ev, kw in e.log if ev == "job_start"]), 2)   # u0 and u1 once each


if __name__ == "__main__":
    unittest.main()
