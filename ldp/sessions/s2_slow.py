"""S2: "It gets slow after a minute". A running load test, and speech that must not kill it.

Fault: a connection leak. Latency rises about a minute into the load test. The user
says "Stop talking. Don't kill the test." A good agent stops speaking and keeps the test.
"""
import random

from ..model import Intent, Part, SessionSpec, make_utt
from .base import App, said

SPIKE_LINE = "Latency just jumped. The connection pool looks saturated, and I suspect a leak in the checkout handler."


class S2App(App):
    def __init__(self):
        self.test1 = None
        self.test2 = None
        self.fix = None
        self.checked = False
        self.pool_fixed = False
        self.rerun_flat = False
        self.spike_seen = False

    def on_intent(self, ctx, it, target):
        k, a = it.kind, it.args
        if k == "TASK" and a["name"] == "load_test":
            ctx.say("Starting the load test. I will tell you when it gets slow.")
            self.test1 = ctx.new_job("load_test", "ro", 90_000)
        elif k == "TASK" and a["name"] == "check_connections":
            def done(c, job):
                self.checked = True
                c.say("Active connections keep growing: 94 of 100 are in use.")
            ctx.new_job("check_connections", "ro", 6000, on_done=done)
        elif k == "TASK" and a["name"] == "fix_and_rerun":
            def commit(c, job):
                self.pool_fixed = True
            self.fix = ctx.new_job("fix_pool", "chg", 5000, commit_ms=4000, edit=True,
                                   pausable=True, on_commit=commit)

            def done(c, job):
                self.rerun_flat = self.pool_fixed
                c.say("Second run: latency stays flat.")
            self.test2 = ctx.new_job("load_test_2", "ro", 90_000, after=[self.fix], on_done=done)

    def on_sys(self, ctx, name, data):
        if name == "latency_jump" and self.test1 is not None and self.test1.running:
            self.spike_seen = True
            ctx.notify(SPIKE_LINE)

    def finalize(self, ctx):
        spike_t = ctx.spec.truth["spike_ms"]
        reported = [t for t in said(ctx, "Latency just jumped") if spike_t <= t <= spike_t + 3000]
        # how long the agent kept talking after the user began "Stop talking."
        u2 = [u for u in ctx.spec.utts if u.uid == "s2.u2"][0]
        kept = 0
        for a, b in ctx.speech_log:
            if a <= u2.t < b:
                kept = b - u2.t
        survived = self.test1 is not None and self.test1.state.value != "cancelled"
        return [
            ("spike_reported_within_3s", "task", bool(reported)),
            ("pool_fixed", "task", self.pool_fixed),
            ("rerun_flat", "task", self.rerun_flat),
            ("connections_checked", "task", self.checked),
            ("load_test_not_killed", "intent", survived),
            ("stopped_talking_within_1.5s", "intent", kept <= 1500),
        ]


def build(variant: int) -> SessionSpec:
    rng = random.Random(2000 + variant)
    speed = rng.uniform(0.85, 1.2)
    spike = int(rng.uniform(60, 65) * 1000)
    t_keep = int(rng.uniform(40, 50) * 1000)
    t_stop = spike + int(rng.uniform(3.0, 5.0) * 1000)
    t_check = t_stop + int(rng.uniform(7, 11) * 1000)
    t_fix = int(rng.uniform(95, 100) * 1000)

    u0 = make_utt("s2.u0", 0, [Part("Run the load test and tell me when it gets slow.",
                                    Intent("TASK", {"name": "load_test", "ro": True}))], speed, hands_on=True)
    u1 = make_utt("s2.u1", t_keep, [Part("Keep it running, I want to watch the graph.",
                                         Intent("KEEP_JOB", {"job": "load_test"}))], speed, hands_on=True)
    u2 = make_utt("s2.u2", t_stop, [
        Part("Stop talking.", Intent("STOP_SPEECH")),
        Part("Don't kill the test.", Intent("KEEP_JOB", {"job": "load_test"})),
    ], speed, hands_on=True, correction=True, must_apply=True, patience_ms=3000)
    u3 = make_utt("s2.u3", t_check, [Part("Okay, check the connections.",
                                          Intent("TASK", {"name": "check_connections", "ro": True}))], speed, hands_on=True)
    u4 = make_utt("s2.u4", t_fix, [Part("Fix the pool, then run the same test again.",
                                        Intent("TASK", {"name": "fix_and_rerun"}))], speed, hands_on=True)
    return SessionSpec("S2", variant, [u0, u1, u2, u3, u4], selection=[(0, "graph")],
                       sys_events=[(spike, "latency_jump", {})], app_factory=S2App,
                       end_ms=t_fix + 130_000, truth={"spike_ms": spike, "order": []})
