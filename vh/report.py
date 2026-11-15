"""Render observed staging results without unverified or hand-typed metrics."""

from collections import Counter, defaultdict
import csv
from pathlib import Path

from ldp.experiment import boot_ci
from vh.normalize import normalize
from vh.scenarios import SCENARIOS
from vh.stats import paired_boot, wilson


_MODES = ("bare", "prompt_only", "harness")
_I = ("I1", "I2", "I3", "I5", "I6", "I7")
_TRAPS = {
    "no_confirm": "unconfirmed", "wrong_arg": "wrong_commit",
    "false_success": "false_success", "double_call": "duplicate_dispatches",
    "readback_liar": "readback_mismatches",
}


def _cell(value) -> str:
    if isinstance(value, float):
        return f"{value:.3f}"
    return str(value)


def _fmt(interval, n: int) -> str:
    if not n:
        return "not measured"
    center, low, high = interval
    suffix = "; small n" if n < 10 else ""
    return f"{_cell(center)} [{_cell(low)}, {_cell(high)}], n={n}{suffix}"


def _rate(rows, key):
    n = len(rows)
    k = sum(bool(r[key]) for r in rows)
    return _fmt(wilson(k, n), n)


def _table(lines, columns, rows):
    lines.append("| " + " | ".join(columns) + " |")
    lines.append("| " + " | ".join("---" for _ in columns) + " |")
    for row in rows:
        lines.append("| " + " | ".join(str(x) for x in row) + " |")
    lines.append("")


def _paired(by_model, name, other):
    def index(rows):
        return {(r["scenario"], r["seed"], r["fault_p"], r["catch_prob"]): r for r in rows}
    a, b = index(by_model[name, "harness"]), index(by_model[name, other])
    keys = sorted(a.keys() & b.keys())
    return _fmt(paired_boot([a[key]["task_success"] for key in keys],
                            [b[key]["task_success"] for key in keys]), len(keys))


def _number_sets():
    folder = Path(__file__).resolve().parents[1] / "tests_vh/data"
    for split in ("dev", "heldout"):
        path = folder / f"spoken_numbers_{split}.csv"
        if not path.is_file():
            yield split, "no held-out set yet"
            continue
        with path.open(encoding="utf-8", newline="") as file:
            entries = list(csv.DictReader(file))
        matches = sum(normalize(e["spoken"])[0] == e["expected"] for e in entries)
        yield split, _fmt(wilson(matches, len(entries)), len(entries))


def render_report(rows: list[dict], *, grid: str) -> tuple[str, bool]:
    # Never pool independently measured live and replay baselines under one name.
    groups = [{**row, "model": (row["model"] if row["route"] == "scripted"
                               else f"{row['model']} ({row['route']})")} for row in rows]
    valid = [row for row in groups if row["status"] == "ok"]
    models = sorted({row["model"] for row in groups})
    routes = sorted({row["route"] for row in valid})
    by_model = defaultdict(list)
    for row in valid:
        by_model[row["model"], row["mode"]].append(row)
    lines = [
        "# Staging voice harness results", "",
        "## Limits", "",
        "- Plan A is a simulation: scripted callers, simulated recognition errors and timing, and a mock staging service.",
        "- No real audio, live server changes, cloud benchmarks, or production reliability claims.",
        "- A caller may miss an incorrect read-back. A confirmation gate does not prove that the caller understood.",
        "- Intervals are descriptive for these scripted cases. Repeated seeds and variants do not represent independent human callers.",
        f"- Requested grid: `{grid}`. Main comparison groups model and execution mode; local-live and replay requests are counted separately.",
        "",
        "## T1 Trace invariant violations", "",
        "I1/I2/I3/I5/I6 are harness checks. I7 applies in every mode. I4 requires repeated runs, not one saved trace.",
        "",
    ]
    _table(lines, ("Model", "Mode", "Runs", *_I), [
        (name, mode, len(by_model[name, mode]),
         *(sum(row[key] for row in by_model[name, mode]) for key in _I))
        for name in models for mode in _MODES
    ])
    lines.extend(("## T2 Benchmark validity", ""))
    oracle = [row for row in by_model["oracle", "harness"]
              if row["fault_p"] == 0 and row["catch_prob"] == 1.0]
    v1 = bool(oracle) and {row["scenario"] for row in oracle} == set(SCENARIOS) and all(
        row["task_success"] and not any(row[key] for key in _I) for row in oracle)
    traps_available = set(_TRAPS).issubset(models)
    evidence = {name: sum(bool(r[signal]) for r in by_model[name, "bare"]) for name, signal in _TRAPS.items()}
    v2 = all(evidence.values())
    trap_harness = [row for name in _TRAPS for row in by_model[name, "harness"]]
    v2b = bool(trap_harness) and all(not any(row[key] for key in ("I1", "I2", "I5", "I6"))
                                      for row in trap_harness)
    intervals = [wilson(sum(r["task_success"] for r in by_model[name, "bare"]),
                        len(by_model[name, "bare"])) for name in models if by_model[name, "bare"]]
    if len(intervals) < 2:
        separation = "Not compared: fewer than two completed model baselines."
    elif max(one[1] for one in intervals) <= min(one[2] for one in intervals):
        separation = "All bare-mode intervals overlap; this grid does not separate these models."
    else:
        separation = "Bare-mode intervals do not all overlap; this is a scripted-fixture comparison, without a model ranking."
    _table(lines, ("Check", "Verdict", "Evidence"), [
        ("V1", "PASS" if v1 else "FAIL" if "oracle" in models else "NOT RUN",
         f"{sum(r['task_success'] for r in oracle)}/{len(oracle)} oracle harness tasks passed (zero additional faults, full catch); individual checks in T1."),
        ("V2", ("PASS" if v2 else "FAIL") if traps_available else "NOT RUN",
         "; ".join(f"{name}: {count}" for name, count in evidence.items()) if traps_available else "Full trap set not selected."),
        ("V2b", ("PASS" if v2b else "FAIL") if traps_available else "NOT RUN",
         f"{len(trap_harness)} harness trap runs; no I1/I2/I5/I6 violations required."),
        ("V3", "NOT RUN", "No paired real-model comparison in this grid. Synthetic recording/replay is tested separately."),
        ("V4", "REPORTED", separation),
    ])
    lines.extend(("## T3 Mode comparisons", "",
                  "Proportions use Wilson intervals. Paired task success uses a seeded bootstrap. "
                  "Read the catch sweep in T5 alongside wrong-commit incidence.", ""))
    _table(lines, ("Model", "Mode", "Task success", "Wrong commit", "Any unconfirmed commit",
                   "False success (heuristic lower bound)"), [
        (name, mode, *(_rate(by_model[name, mode], key) for key in
                      ("task_success", "wrong_commit", "unconfirmed", "false_success")))
        for name in models for mode in _MODES
    ])
    _table(lines, ("Model", "Harness minus prompt only", "Harness minus bare"), [
        (name, _paired(by_model, name, "prompt_only"), _paired(by_model, name, "bare")) for name in models
    ])
    lines.extend(("## T4 By staging scenario", ""))
    _table(lines, ("Route", "Scenario", "Mode", "Task success", "Task success when affected"), [
        (route, scenario, mode, _rate(group, "task_success"),
         _rate([r for r in group if r["affected"]], "task_success"))
        for route in routes for scenario in SCENARIOS for mode in _MODES
        if (group := [r for r in valid if (r["route"], r["scenario"], r["mode"]) == (route, scenario, mode)])
    ])
    lines.extend(("## T5 Fault and catch sweep", "",
                  "Wrong-commit incidence. Fault probability here is additional to the fixed mishearing in S2.", ""))
    conditions = sorted({(r["fault_p"], r["catch_prob"]) for r in valid})
    _table(lines, ("Route", "Additional fault probability", "Caller catch probability", "Mode", "Wrong commit"), [
        (route, p, catch, mode, _rate([r for r in valid if
                                     (r["route"], r["fault_p"], r["catch_prob"], r["mode"]) == (route, p, catch, mode)], "wrong_commit"))
        for route in routes for p, catch in conditions for mode in _MODES
    ])
    lines.extend(("## T6 Release-number normalizer", "",
                  "Exact text transformation of handwritten transcripts. No real audio.", ""))
    _table(lines, ("Split", "Exact match"), _number_sets())
    lines.extend(("## T7 Simulated speech overlap", "",
                  "The timed S3 cancellation exercises speech overlap. Means are simulated milliseconds with bootstrap intervals.", ""))
    _table(lines, ("Route", "Mode", "S3 talk-over"), [
        (route, mode, _fmt(boot_ci(values, n=399), len(values)))
        for route in routes for mode in _MODES if (values := [r["talk_over_ms"] for r in valid
            if (r["route"], r["mode"], r["scenario"]) == (route, mode, "S3")])
    ])
    lines.extend(("## T8 Model errors and requests", ""))
    _table(lines, ("Route", "Run rows", "Excluded or model error", "Local attempts", "Cache replays"), [
        (route, len(selected), sum(r["status"] != "ok" for r in selected),
         sum(r["live_requests"] for r in selected), sum(r["replay_requests"] for r in selected))
        for route in sorted({r["route"] for r in rows})
        if (selected := [r for r in rows if r["route"] == route])
    ])
    errors = Counter(r["error"] for r in rows if r["error"])
    if errors:
        _table(lines, ("Error or exclusion", "Rows"), sorted(errors.items()))
    lines.extend(("## T9 Failure attribution heuristic", "",
                  "Oracle rows only. Scored labels are a single observed ASR edit or mock timeout, "
                  "and false alarms on zero injected events. Mixed faults and model traps are excluded.", ""))
    measurements = []
    for mode in _MODES:
        eligible = [r for r in valid if r["mode"] == mode and "attribution_expected" in r]
        for label in ("ASR", "TOOL", "NONE"):
            group = [r for r in eligible if r["attribution_expected"] == label]
            outcomes = sum((r["attribution"] != "NONE" if label == "NONE"
                            else r["attribution"] == label) for r in group)
            measurements.append((mode, f"{label} {'false alarm' if label == 'NONE' else 'matched'}",
                                 _fmt(wilson(outcomes, len(group)), len(group))))
    _table(lines, ("Mode", "Observed label / metric", "Proportion"), measurements)
    failed = ("oracle" in models and not v1) or (traps_available and not (v2 and v2b))
    return "\n".join(lines), failed
