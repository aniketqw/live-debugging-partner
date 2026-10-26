"""S5: which warning? A screen reference that changes mid-sentence, then a new need.

The dashboard shows three warnings. The user says "This one is wrong" while the selection
moves from warning 2 to warning 1, then corrects: "No, the one above it." Later come a
new requirement (Swiss francs) and a constraint (do not touch the tax logic).
"""
import random

from ..model import Intent, Part, Ref, SessionSpec, make_utt
from .base import App

ORDER = ["w:1", "w:2", "w:3"]      # w:1 is the top warning and the real fault (missing currency)
NAMES = {"w:1": "missing currency", "w:2": "VAT rounding", "w:3": "slow query"}


class S5App(App):
    def __init__(self):
        self.target = None
        self.fix_committed = {}
        self.chg_commits = []
        self.tax_touched = False
        self.chf_done = False
        self.last = None

    def on_intent(self, ctx, it, target):
        k, a = it.kind, it.args
        if k == "TASK" and a["name"] == "fix_warning":
            self.target = target
            ctx.say(f"The {NAMES.get(target, 'unknown')} warning. I will fix that.")

            def commit(c, job):
                self.chg_commits.append(job.target)
            j1 = ctx.new_job("fix_currency_field", "chg", 10_000, commit_ms=9000, edit=True,
                             pausable=True, target=target, on_commit=commit)
            self.last = ctx.new_job("run_checks", "ro", 6000, after=[j1])
        elif k == "REQUIREMENT" and a["tag"] == "chf":
            self._add_chf(ctx)

    def _add_chf(self, ctx):
        def commit(c, job):
            self.chf_done = True
            if "no_tax_edit" not in c.constraints and c.t >= c.spec.truth["constraint_ms"]:
                self.tax_touched = True
                c.flag_unwanted(job, "tax_edit_after_constraint")
            self.chg_commits.append(job.target)
        after = [self.last] if self.last else []
        job = ctx.new_job("add_chf_totals", "chg", 14_000, commit_ms=13_000, edit=True, pausable=True,
                          target=self.target or "w:1", on_commit=commit, after=after)
        self.last = job

    def finalize(self, ctx):
        c = self.chg_commits
        return [
            ("fix_applied_to_missing_currency", "task", "w:1" in c[:1] or ("w:1" in c)),
            ("swiss_franc_totals_added", "task", self.chf_done),
            ("tax_logic_untouched", "intent", not self.tax_touched),
            ("other_warnings_untouched", "intent", all(x == "w:1" for x in c)),
        ]


def build(variant: int) -> SessionSpec:
    rng = random.Random(5000 + variant)
    speed = rng.uniform(0.85, 1.2)
    t0 = int(rng.uniform(0.2, 0.6) * 1000)
    t_move = t0 + int(rng.uniform(1.2, 1.8) * 1000)
    t_chf = int(rng.uniform(13, 17) * 1000)
    t_tax = int(rng.uniform(23.5, 26.5) * 1000)

    u0 = make_utt("s5.u0", t0, [
        Part("This one is wrong.", Intent("TASK", {"name": "fix_warning"}, ref=Ref("deictic", word=0))),
        Part("No,", marker=True),
        Part("the one above it.", Intent("TASK", {"name": "fix_warning"}, ref=Ref("relative", base=0, rel=-1)),
             replaces=0, typed_ref=Ref("deictic", word=0)),
    ], speed, hands_on=True)
    u1 = make_utt("s5.u1", t_chf, [Part("Also make it work for Swiss francs.",
                                        Intent("REQUIREMENT", {"tag": "chf"}))], speed, hands_on=True, correction=True)
    u2 = make_utt("s5.u2", t_tax, [Part("And don't touch the tax logic.",
                                        Intent("CONSTRAINT", {"tag": "no_tax_edit"}))],
                  speed, hands_on=True, correction=True, must_apply=True, patience_ms=6000)
    return SessionSpec("S5", variant, [u0, u1, u2],
                       selection=[(0, "w:2"), (t_move, "w:1")], sys_events=[], app_factory=S5App,
                       end_ms=120_000,
                       truth={"order": ORDER, "constraint_ms": u2.seg_end(0), "target": "w:1", "default_guess": "w:3",
                              "answers": {"TASK": ("The missing currency one.", "w:1")}})
