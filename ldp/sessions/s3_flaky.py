"""S3: flaky tests with a changing request.

"Run the billing tests, no wait, the auth tests." A question while the run goes on.
A flaky test that must run five times. And "Skip the integration ones", which applies
to the current run (ground truth in the script).
"""
import random

from ..model import Intent, Part, SessionSpec, make_utt
from .base import App

RUN_MS = {"auth": 180_000, "billing": 150_000}
UNIT_MS = 100_000     # the first 100 s of an auth run are unit tests; integration tests follow


class S3App(App):
    def __init__(self):
        self.runs = []
        self.repeat_done = False
        self.skip_t = None
        self.skip_late = False

    def on_intent(self, ctx, it, target):
        k, a = it.kind, it.args
        if k == "TASK" and a["name"] == "run_tests":
            suite = a["suite"]
            ctx.say(f"Running the {suite} tests.")
            job = ctx.new_job(f"run_{suite}", "ro", RUN_MS[suite])
            self.runs.append(job)
        elif k == "QUERY" and a["topic"] == "last_failures":
            def done(c, job):
                c.say("Last time two auth tests failed: token expiry and refresh.")
                c.mark_answer("last_failures")
            ctx.new_job("read_report", "ro", 2000, on_done=done)
        elif k == "TASK" and a["name"] == "repeat":
            def done(c, job):
                self.repeat_done = True
                c.say("Token expiry failed 2 of 5 runs. It is flaky.")
            ctx.new_job("repeat_token_expiry", "ro", 40_000, on_done=done)
        elif k == "TASK" and a["name"] == "skip_integration":
            self.skip_t = ctx.t
            cur = [j for j in ctx.running("run_auth")]
            if cur:
                job = cur[0]
                # unit tests still running: the run ends when they end. Otherwise it ends now.
                job.dur_ms = max(UNIT_MS, job.run_ms + ctx.P.tick_ms)
                ctx.say("Skipping the integration tests in this run.")
            else:
                self.skip_late = True
                ctx.say("That run already finished with the integration tests. The unit results are ready.")

    def on_sys(self, ctx, name, data):
        if name == "test_fail" and ctx.running("run_auth"):
            ctx.notify("test_token_expiry failed.")

    def extra_waste_ms(self, ctx):
        """Integration compute that ran after the user said to skip it."""
        T = ctx.spec.truth["skip_ms"]
        waste = 0
        for job in self.runs:
            if job.name != "run_auth" or job.t_start is None:
                continue
            a = job.t_start + UNIT_MS
            b = job.t_end if job.t_end is not None else ctx.t
            if job.state.value == "cancelled":
                continue
            waste += max(0, b - max(a, T))
        return waste

    def finalize(self, ctx):
        billing_done = any(j.name == "run_billing" and j.done for j in self.runs)
        T = ctx.spec.truth["skip_ms"]
        integ = self.extra_waste_ms(ctx)
        auth = [j for j in self.runs if j.name == "run_auth"]
        auth_end = max([j.t_end for j in auth if j.t_end] or [ctx.t])
        ans = ctx.answer_t.get("last_failures")
        wasted = (ctx.wasted_ms + integ) / 1000
        return [
            ("auth_run_only_no_billing_results", "task", not billing_done),
            ("flaky_test_run_five_times", "task", self.repeat_done),
            ("last_failures_answered", "task", ans is not None),
            ("integration_skipped_after_request", "intent", integ <= 1000),
            ("answered_while_run_continued", "intent", ans is not None and ans < auth_end),
            ("wasted_compute_below_15s", "intent", wasted <= 15),
        ]


def build(variant: int) -> SessionSpec:
    rng = random.Random(3000 + variant)
    speed = rng.uniform(0.85, 1.2)
    t_q = int(rng.uniform(36, 44) * 1000)
    t_fail = int(rng.uniform(66, 72) * 1000)
    t_flaky = t_fail + int(rng.uniform(1, 3) * 1000)
    t_skip = int(rng.uniform(82, 88) * 1000)

    u0 = make_utt("s3.u0", 0, [
        Part("Run the billing tests,", Intent("TASK", {"name": "run_tests", "suite": "billing", "ro": True})),
        Part("no wait,", marker=True),
        Part("the auth tests.", Intent("TASK", {"name": "run_tests", "suite": "auth", "ro": True}), replaces=0),
    ], speed)
    u1 = make_utt("s3.u1", t_q, [Part("What failed last time?", Intent("QUERY", {"topic": "last_failures", "ro": True}))], speed)
    u2 = make_utt("s3.u2", t_flaky, [Part("Is that flaky? Run it five times.",
                                          Intent("TASK", {"name": "repeat", "ro": True}))], speed)
    u3 = make_utt("s3.u3", t_skip, [Part("Skip the integration ones.", Intent("TASK", {"name": "skip_integration"}))],
                  speed, correction=True, must_apply=True, patience_ms=8000)
    skip_ms = u3.seg_end(0)
    return SessionSpec("S3", variant, [u0, u1, u2, u3], selection=[(0, "terminal")],
                       sys_events=[(t_fail, "test_fail", {})], app_factory=S3App,
                       end_ms=600_000, truth={"skip_ms": skip_ms, "order": []})
