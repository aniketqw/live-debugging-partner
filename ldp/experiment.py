"""Run the grid (sessions x variants x arms x policies), test H1 to H4, write the report.

    python -m ldp.experiment            # full run, writes results/
    python -m ldp.experiment --quick    # 5 variants per session
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
from dataclasses import replace
from typing import Dict, List

from . import metrics
from .channels import ARMS, GRID_ARMS
from .engine import Engine
from .model import Params
from .policies import POLICIES, TRAPS
from .sessions import HANDS_ON, MODULES, N_VARIANTS, build

METRIC_KEYS = ["completion", "latest_intent", "unwanted_w", "recovery_s", "wasted_s", "talk_over_s",
               "input_s", "off_app_s", "words", "repeats", "asks", "compute_s", "answer_delay_s"]
BETTER = {"completion": +1, "latest_intent": +1, "unwanted_w": -1, "recovery_s": -1, "wasted_s": -1,
          "talk_over_s": -1, "input_s": -1, "off_app_s": -1, "words": -1, "repeats": -1, "asks": -1,
          "compute_s": -1, "answer_delay_s": -1}
FREE_HANDS = {"S3", "S4"}


def run_one(sid, variant, arm, policy, params=None) -> Dict:
    pol = POLICIES.get(policy) or TRAPS[policy]
    e = Engine(build(sid, variant), ARMS[arm], pol, params).run()
    m = metrics.compute(e)
    m.update(sid=sid, variant=variant, arm=arm, policy=policy)
    return m


def run_grid(n_variants=N_VARIANTS, arms=GRID_ARMS, policies=tuple(POLICIES), params=None, sessions=None) -> List[Dict]:
    rows = []
    for sid in sessions or MODULES:
        for v in range(n_variants):
            for arm in arms:
                for pol in policies:
                    rows.append(run_one(sid, v, arm, pol, params))
    return rows


# -- statistics ----------------------------------------------------------
def mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def boot_ci(xs, n=2000, seed=7):
    """Mean and 95% percentile bootstrap interval."""
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None, None
    rng = random.Random(seed)
    means = sorted(sum(rng.choice(xs) for _ in xs) / len(xs) for _ in range(n))
    return sum(xs) / len(xs), means[int(0.025 * n)], means[int(0.975 * n)]


def select(rows, **kw):
    return [r for r in rows if all((r[k] in v if isinstance(v, (set, list, tuple)) else r[k] == v) for k, v in kw.items())]


def paired(rows, a: dict, b: dict, key: str):
    """Per-variant differences (a minus b) for one metric. Pairs with a missing value are dropped."""
    ra = {(r["sid"], r["variant"]): r[key] for r in select(rows, **a)}
    rb = {(r["sid"], r["variant"]): r[key] for r in select(rows, **b)}
    return [ra[k] - rb[k] for k in ra if k in rb and ra[k] is not None and rb[k] is not None]


def verdict(diff_ci, direction):
    """'better' if the whole interval is on the good side, 'worse' on the bad side, else 'unclear'."""
    _, lo, hi = diff_ci
    if lo is None:
        return "n/a"
    if lo == hi == 0:
        return "identical"
    if direction < 0:
        return "better" if hi < 0 else ("worse" if lo > 0 else "unclear")
    return "better" if lo > 0 else ("worse" if hi < 0 else "unclear")


def compare(rows, a, b, keys, sessions):
    out = {}
    for k in keys:
        d = paired(rows, {**a, "sid": sessions}, {**b, "sid": sessions}, k)
        ci = boot_ci(d)
        out[k] = {"diff": ci[0], "lo": ci[1], "hi": ci[2], "n": len(d), "verdict": verdict(ci, BETTER[k])}
    return out


def hypotheses(rows) -> Dict:
    L = "ledger_rules"
    allS, hands, free = set(MODULES), HANDS_ON, FREE_HANDS
    iv = {"arm": "interactive_voice", "policy": L}
    h1 = compare(rows, iv, {"arm": "basic_voice", "policy": L},
                 ["latest_intent", "unwanted_w", "recovery_s", "talk_over_s"], allS)
    h2 = compare(rows, iv, {"arm": "text_interrupt", "policy": L}, ["recovery_s", "input_s", "off_app_s"], hands)
    h3 = compare(rows, {"arm": "text_interrupt", "policy": L}, iv, ["completion", "latest_intent", "unwanted_w"], free)
    h4a = compare(rows, {"arm": "interactive_voice", "policy": L}, {"arm": "interactive_voice", "policy": "always_stop"},
                  ["wasted_s"], allS)
    h4b = compare(rows, {"arm": "interactive_voice", "policy": L}, {"arm": "interactive_voice", "policy": "never_stop"},
                  ["unwanted_w"], allS)
    return {"H1": h1, "H2": h2, "H3": h3, "H4a": h4a, "H4b": h4b}


def call(h: Dict, kind: str) -> str:
    vs = [v["verdict"] for v in h.values()]
    if kind == "h3":   # held when no difference can be shown
        return "held" if all(v in ("unclear", "identical") for v in vs) else "not held"
    if all(v == "better" for v in vs):
        return "held"
    return "partly held" if any(v == "better" for v in vs) else "not held"


# -- report ----------------------------------------------------------------
def fmt(x, nd=2):
    return "n/a" if x is None else (f"{x:.{nd}f}")


def table(headers, rows_):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows_]
    return "\n".join(out)


def arm_table(rows, policy="ledger_rules", sessions=None):
    keys = ["completion", "latest_intent", "unwanted_w", "recovery_s", "wasted_s", "talk_over_s", "input_s",
            "off_app_s", "asks", "repeats", "answer_delay_s"]
    body = []
    for arm in GRID_ARMS:
        rs = select(rows, arm=arm, policy=policy, **({"sid": sessions} if sessions else {}))
        cells = []
        for k in keys:
            m, lo, hi = boot_ci([r[k] for r in rs])
            cells.append(f"{fmt(m)} [{fmt(lo)}, {fmt(hi)}]")
        body.append([arm] + cells)
    return table(["arm"] + keys, body)


def policy_table(rows, arm="interactive_voice"):
    keys = ["completion", "latest_intent", "unwanted_w", "recovery_s", "wasted_s", "talk_over_s", "asks", "repeats"]
    body = []
    for pol in POLICIES:
        rs = select(rows, arm=arm, policy=pol)
        body.append([pol] + [fmt(mean([r[k] for r in rs])) for k in keys])
    return table(["policy"] + keys, body)


def check_table(rows, policy="ledger_rules"):
    names = []
    for r in rows:
        for c in r["checks"]:
            if (r["sid"], c) not in names:
                names.append((r["sid"], c))
    body = []
    for sid, c in names:
        cells = []
        for arm in GRID_ARMS:
            rs = [r for r in select(rows, arm=arm, policy=policy, sid=sid) if c in r["checks"]]
            cells.append(f"{100 * sum(r['checks'][c] for r in rs) / max(1, len(rs)):.0f}%")
        kind = [r["check_kind"][c] for r in rows if r["sid"] == sid and c in r["check_kind"]][0]
        body.append([sid, c, kind] + cells)
    return table(["session", "check", "kind"] + GRID_ARMS, body)


def session_table(rows, policy="ledger_rules"):
    body = []
    for sid in MODULES:
        cells = []
        for arm in GRID_ARMS:
            rs = select(rows, arm=arm, policy=policy, sid=sid)
            cells.append(f"{fmt(mean([r['completion'] for r in rs]))} / {fmt(mean([r['latest_intent'] for r in rs]))}")
        body.append([sid] + cells)
    return table(["session"] + GRID_ARMS, body)


def metric_by_session(rows, key, policy="ledger_rules"):
    body = []
    for sid in MODULES:
        cells = []
        for arm in GRID_ARMS:
            m = mean([r[key] for r in select(rows, arm=arm, policy=policy, sid=sid)])
            cells.append(fmt(m))
        body.append([sid] + cells)
    return table(["session"] + GRID_ARMS, body)


def sensitivity(n_variants) -> str:
    """How the arm comparison changes when the timing guesses change (all sessions, ledger rules)."""
    L = "ledger_rules"
    base = Params()
    sweeps = [
        ("typing switch cost, ms", [(s, replace(base, switch_ms=s)) for s in (0, 1500, 3000)]),
        ("typing speed, ms per word", [(s, replace(base, type_ms_per_word=s)) for s in (600, 1200, 1800, 3000, 4500)]),
        ("voice lags, x the default", [(f, replace(base, vad_lag_ms=int(150 * f), stream_lag_ms=int(300 * f),
                                                    final_lag_ms=int(400 * f), asr_lag_ms=int(700 * f)))
                                       for f in (0.5, 1, 2, 4, 8)]),
    ]
    out = []
    for label, grid in sweeps:
        body = []
        for val, prm in grid:
            rows = run_grid(n_variants, arms=["interactive_voice", "text_interrupt"], policies=[L], params=prm)
            hands = select(rows, sid=sorted(HANDS_ON))
            d = paired(hands, {"arm": "interactive_voice"}, {"arm": "text_interrupt"}, "recovery_s")
            ci = boot_ci(d)
            def m(arm, k):
                return fmt(mean([r[k] for r in select(rows, arm=arm)]), 3)
            body.append([val, f"{fmt(ci[0])} [{fmt(ci[1])}, {fmt(ci[2])}]",
                         m("interactive_voice", "latest_intent"), m("text_interrupt", "latest_intent"),
                         m("interactive_voice", "completion"), m("text_interrupt", "completion")])
        out.append(f"**{label}**\n\n" + table(
            [label, "recovery_s diff, hands-on sessions (interactive minus text+interrupt)",
             "latest_intent interactive", "latest_intent text+interrupt", "completion interactive",
             "completion text+interrupt"], body))
    return "\n\n".join(out)


def write_report(rows, hyp, sens, path, n_variants):
    h = hyp
    def hrows(d, names=None):
        return [[k, f"{fmt(v['diff'])} [{fmt(v['lo'])}, {fmt(v['hi'])}]", v["n"], v["verdict"]] for k, v in d.items()]
    hdr = ["measure", "mean difference [95% interval]", "pairs", "verdict"]
    parts = [
        "# Results (generated by `python -m ldp.experiment`)",
        f"Sessions: {', '.join(MODULES)}. Variants per session: {n_variants}. Runs: {len(rows)}. "
        "All numbers come from the simulator with scripted users, a scripted executor, and timing guesses "
        "(see README, Limits). They test the *design*, not real people.",
        "## Hypotheses (written before the run, in SESSIONS.md section 6)",
        f"**H1 {call(h['H1'], 'h1')}.** Interactive voice vs basic voice, ledger rules, all sessions. Difference = interactive minus basic.\n\n" + table(hdr, hrows(h["H1"])),
        f"**H2 {call(h['H2'], 'h2')}.** Interactive voice vs text + interrupt, hands-on sessions (S1, S2, S5), ledger rules. "
        "`off_app_s` is partly set by the typing-switch assumption; read it with the sensitivity table below.\n\n" + table(hdr, hrows(h["H2"])),
        f"**H3 {call(h['H3'], 'h3')}.** Text + interrupt vs interactive voice, free-hands sessions (S3, S4). Held means no difference can be shown. Difference = text+interrupt minus interactive.\n\n" + table(hdr, hrows(h["H3"])),
        f"**H4 {call({**h['H4a'], **h['H4b']}, 'h4')}.** Ledger rules vs always-stop on wasted work, and vs never-stop on unwanted actions (interactive voice arm). Difference = ledger rules minus the other policy.\n\n"
        + table(hdr, [["wasted_s vs always_stop"] + hrows(h["H4a"])[0][1:], ["unwanted_w vs never_stop"] + hrows(h["H4b"])[0][1:]]),
        "## All four arms, ledger rules, all sessions (mean [95% interval over variants])",
        arm_table(rows),
        "## Completion / latest-intent accuracy per session (ledger rules)",
        session_table(rows),
        "## Correction-recovery time per session, seconds (ledger rules)",
        metric_by_session(rows, "recovery_s"),
        "## Unwanted actions per session, weighted (ledger rules)",
        metric_by_session(rows, "unwanted_w"),
        "## Policies inside the interactive voice arm",
        policy_table(rows),
        "## Which checks fail (ledger rules, pass rate)",
        check_table(rows),
        "## Sensitivity to the timing guesses (outcomes use all sessions)",
        sens,
    ]
    with open(path, "w") as f:
        f.write("\n\n".join(parts) + "\n")


def write_csv(rows, path):
    keys = ["sid", "variant", "arm", "policy"] + METRIC_KEYS
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(keys + ["failed_checks"])
        for r in rows:
            w.writerow([r[k] if r[k] is not None else "" for k in keys] + [";".join(c for c, ok in r["checks"].items() if not ok)])


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--out", default="results")
    a = ap.parse_args(argv)
    n = 5 if a.quick else N_VARIANTS
    os.makedirs(a.out, exist_ok=True)
    rows = run_grid(n)
    hyp = hypotheses(rows)
    sens = sensitivity(min(n, 10))
    write_csv(rows, os.path.join(a.out, "runs.csv"))
    with open(os.path.join(a.out, "hypotheses.json"), "w") as f:
        json.dump(hyp, f, indent=1)
    write_report(rows, hyp, sens, os.path.join(a.out, "RESULTS.md"), n)
    from .timeline import write_examples
    write_examples(os.path.join(a.out, "timelines"))
    print(open(os.path.join(a.out, "RESULTS.md")).read())


if __name__ == "__main__":
    main()
