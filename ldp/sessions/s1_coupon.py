"""S1: coupon checkout error. Hold edits, point at "that error", keep the response format.

Fault: percent coupons are stored as text "10%", which gives NaN in the payment call
and a 500. A good agent holds edits when told, binds "that error" to the selected log
line, and applies a fix of the cause with the response format preserved.
"""
import random

from ..model import Intent, Part, Ref, SessionSpec, make_utt
from .base import App, said

SEL_NAN = "log:nan"
SEL_SLOW = "log:slow"


class S1App(App):
    def __init__(self, insp_ms):
        self.insp_ms = insp_ms
        self.fix = None            # (kind, format_ok) of the last committed fix
        self.edit_times = []
        self.replay_done_t = None
        self.user_fix = False
        self.auto_started = False
        self.focus_at_fix = None

    def on_intent(self, ctx, it, target):
        k, a = it.kind, it.args
        if k == "TASK" and a["name"] == "investigate":
            ctx.say("Checking the request and server logs.")
            ctx.new_job("inspect_logs", "ro", self.insp_ms)
        elif k == "TASK" and a["name"] == "replay":
            def done(c, job):
                c.say("Without the coupon: fine. With it: error 500.")
                self.replay_done_t = c.t
            ctx.new_job("replay_no_coupon", "ro", 6000, on_done=done)
        elif k == "FOCUS":
            ctx.focus = target
            ctx.say("That one: the NaN error." if target == SEL_NAN else "OK, that one.")
        elif k == "TASK" and a["name"] == "fix":
            self.user_fix = True
            self._fix(ctx, auto=False)

    def _fix(self, ctx, auto):
        kind = "cause" if ctx.focus == SEL_NAN else "hide"
        fmt = "preserve_format" in ctx.constraints
        self.focus_at_fix = ctx.focus

        def commit(c, job):
            self.fix = (kind, fmt)
            self.edit_times.append(c.t)

        def done(c, job):
            c.say("Fixed. The coupon value is stored as a number now.")
        if auto:
            ctx.say("Found the cause. Applying a fix.")
        ctx.new_job("fix", "chg", 6000, commit_ms=5000, edit=True, pausable=True,
                    on_commit=commit, on_done=done)

    def on_job_done(self, ctx, job):
        if job.name == "inspect_logs" and not ctx.edit_hold and not self.user_fix and not self.auto_started:
            self.auto_started = True
            self._fix(ctx, auto=True)

    def finalize(self, ctx):
        fix = self.fix or (None, False)
        lift = ctx.spec.truth["hold_windows"][0][1]
        before = [t for t in self.edit_times if t < lift]
        return [
            ("fix_addresses_cause", "task", fix[0] == "cause"),
            ("response_format_preserved", "task", fix[0] is not None and fix[1]),
            ("replay_without_coupon_done", "task", self.replay_done_t is not None),
            ("no_edit_during_hold", "intent", not before),
            ("focus_bound_to_nan_line", "intent", self.focus_at_fix == SEL_NAN),
        ]


def build(variant: int) -> SessionSpec:
    rng = random.Random(1000 + variant)
    speed = rng.uniform(0.85, 1.2)
    t_hold = int(rng.uniform(7.0, 10.5) * 1000)
    insp_ms = int(rng.uniform(12, 16) * 1000)
    t_sel = int(rng.uniform(22, 26) * 1000)
    t_fix = t_sel + int(rng.uniform(6, 9) * 1000)

    u0 = make_utt("s1.u0", 0, [
        Part("Open the checkout page."),
        Part("The problem starts after I apply the coupon.", Intent("TASK", {"name": "investigate", "ro": True})),
    ], speed, hands_on=True)
    u1 = make_utt("s1.u1", t_hold, [
        Part("Wait, don't change anything yet.", Intent("HOLD_EDITS")),
        Part("Try it without the coupon first.", Intent("TASK", {"name": "replay", "ro": True})),
    ], speed, hands_on=True, correction=True, must_apply=True, patience_ms=6000)
    u2 = make_utt("s1.u2", t_sel, [
        Part("That error there, that's the one.", Intent("FOCUS", ref=Ref("deictic", word=1))),
    ], speed, hands_on=True)
    u3 = make_utt("s1.u3", t_fix, [
        Part("Yes.", Intent("LIFT_HOLD")),
        Part("Fix that,", Intent("TASK", {"name": "fix"})),
        Part("but preserve the response format.", Intent("CONSTRAINT", {"tag": "preserve_format"})),
    ], speed, hands_on=True)
    hold_end = u1.seg_end(0)
    lift = u3.t + u3.words[0][2]
    return SessionSpec(
        "S1", variant, [u0, u1, u2, u3],
        selection=[(0, "page"), (t_hold + 2000, SEL_SLOW), (t_sel - 300, SEL_NAN)],
        sys_events=[], app_factory=lambda: S1App(insp_ms), end_ms=t_fix + 30000,
        truth={"hold_windows": [(hold_end, lift)], "default_guess": SEL_SLOW,
               "answers": {"FOCUS": ("The one with NaN in it.", SEL_NAN)}, "order": []},
    )
