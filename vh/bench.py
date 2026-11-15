"""Generate an offline-first benchmark of the simulated staging voice harness."""

from argparse import ArgumentParser
import csv
from itertools import product
import json
from pathlib import Path

from vh.agents.ollama import CacheMiss, OllamaModel, RequestBudget
from vh.agents.scripted import MODELS
from vh.attribution import attribute
from vh.checks import check_invariants, diagnostics, task_success
from vh.normalize import normalize
from vh.report import render_report
from vh.runtime import run_call
from vh.scenarios import SCENARIOS
from vh.trace import trace_hash, write_trace


_MODES = ("bare", "prompt_only", "harness")
_GRIDS = {
    "smoke": ((0.0,), (1.0,), 1),
    "quick": ((0.15,), (1.0, 0.8), 1),
    "full": ((0.0, 0.05, 0.15), (1.0, 0.8, 0.5), 3),
}
_I = tuple(f"I{i}" for i in range(1, 8) if i != 4)
_FIELDS = (
    "run_id", "model", "scenario", "mode", "fault_p", "catch_prob", "seed", "status", "error",
    "task_success", "wrong_commit", "unconfirmed", "false_success", "duplicate_dispatches",
    "readback_mismatches", "affected", "turns", "talk_over_ms", *_I,
    "attribution", "attribution_expected",
    "route", "live_requests", "replay_requests", "trace_hash",
)


def _affected(trace: list[dict]) -> bool:
    def cleaned(text):
        return "".join(char for char in normalize(text.lower())[0] if char.isalnum())
    originals = {}
    for event in trace:
        stage, kind, data = event["stage"], event["kind"], event["data"]
        if (stage, kind) == ("caller", "say"):
            originals[data["turn"]] = cleaned(data["text"])
        if (stage, kind) == ("asr", "out") and data["faults"]:
            if cleaned(data["transcript"]) != originals[data["turn"]]:
                return True
    return False


def _report_row(result, scenario, row):
    trace = result.trace
    if result.metrics["model_error"]:
        errors = [event.get("meta", {}).get("error") for event in trace]
        row.update(status="model_error", error=next((error for error in errors if error), "model_error"))
        return
    values = diagnostics(trace, scenario)
    audit = values.pop("audit")
    row.update(**values, task_success=int(task_success(result.final_state, scenario, audit=audit)),
               affected=int(_affected(trace)), talk_over_ms=result.metrics["talk_over_ms"],
               turns=sum((event["stage"], event["kind"]) == ("caller", "say") for event in trace))
    row["wrong_commit"] = int(row["wrong_commit"])
    for key, violations in check_invariants(trace, scenario, row["mode"]).items():
        if key in _I:
            row[key] = len(violations)
    if row["model"] == "oracle":
        _score_attribution(trace, row)


def _score_attribution(trace, row):
    found = []
    stripped = []
    for event in trace:
        data = event["data"].copy()
        pair = event["stage"], event["kind"]
        if pair == ("asr", "out"):
            found.extend("ASR" for _ in data.pop("faults"))
        elif pair == ("tool", "error") and data["reason"] == "timeout":
            found.append("TOOL")
        stripped.append({**event, "data": data})
    if len(found) <= 1:
        row["attribution_expected"] = found[0] if found else "NONE"
        row["attribution"] = attribute(stripped)["stage"]


def _models(args, parser):
    if args.models == "scripted":
        return list(MODELS) if args.grid == "full" else ["oracle"]
    names = args.models.split(",")
    inventory_file = Path(__file__).resolve().parents[1] / "bench/models.json"
    inventory = {item["name"] for item in json.loads(inventory_file.read_text())["models"]
                 if item["route"] == "local-only" and item["tools_supported"]}
    if any(name not in inventory and name not in MODELS for name in names):
        parser.error("model must be a known scripted model or an approved local inventory entry")
    return names


def _run(args, names):
    output = args.output_dir
    trace_dir = output / "traces"
    trace_dir.mkdir(parents=True, exist_ok=True)
    faults, catches, repeats = _GRIDS[args.grid]
    budget = RequestBudget(args.max_requests)
    rows = []
    for i, (name, scenario_id, p, catch, seed, mode) in enumerate(
        product(names, SCENARIOS, faults, catches, range(1, repeats + 1), _MODES), 1
    ):
        scenario = SCENARIOS[scenario_id]
        row = dict(run_id=i, model=name, scenario=scenario_id, mode=mode, fault_p=p,
                   catch_prob=catch, seed=seed, status="ok", error="",
                   route="scripted" if name in MODELS else args.request_mode,
                   live_requests=0, replay_requests=0, trace_hash="")
        rows.append(row)
        if name not in MODELS and args.request_mode == "live" and budget.used >= budget.maximum:
            row.update(status="excluded", error="request_limit")
            continue
        adapter = MODELS[name]() if name in MODELS else OllamaModel(
            name, cache_dir=args.cache_dir, request_mode=args.request_mode,
            budget=budget, seed=seed, allow_local=args.allow_live_local,
        )
        before = budget.used
        try:
            result = run_call(scenario, adapter, mode, seed, p, catch)
        except CacheMiss:
            row.update(status="excluded", error="cache_miss", replay_requests=getattr(adapter, "replays", 0))
            continue
        row["live_requests"] = budget.used - before
        row["replay_requests"] = getattr(adapter, "replays", 0)
        if name not in MODELS:
            if row["live_requests"] > 0:
                row["route"] = "local-live" if not row["replay_requests"] else "mixed-local/replay"
            elif row["replay_requests"] > 0:
                row["route"] = "replay"
        _report_row(result, scenario, row)
        row["trace_hash"] = trace_hash(result.trace)
        write_trace(trace_dir / f"{i:05d}_{scenario_id}_{mode}.jsonl", result.trace)
    with (output / "runs.csv").open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, _FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    report, failed = render_report(rows, grid=args.grid)
    (output / "RESULTS.md").write_text(report, encoding="utf-8")
    print(f"Saved {len(rows)} run rows to {output}.")
    if any(row["error"] == "request_limit" for row in rows):
        print("Live request cap reached; remaining live generations were skipped.")
    print(f"Local generation attempts: {budget.used}. Hosted inference disabled.")
    return int(failed)


def main(argv=None):
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--grid", choices=_GRIDS, default="smoke")
    parser.add_argument("--models", default="scripted")
    parser.add_argument("--output-dir", type=Path, default=Path("results/vh"))
    parser.add_argument("--cache-dir", type=Path, default=Path("bench/cache"))
    parser.add_argument("--request-mode", choices=("replay", "auto", "live"), default="replay")
    parser.add_argument("--allow-live-local", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    args = parser.parse_args(argv)
    if args.max_requests < 0:
        parser.error("--max-requests must be nonnegative")
    names = _models(args, parser)
    if args.grid == "full" and any(name not in MODELS for name in names):
        parser.error("the full grid is scripted only")
    return _run(args, names)


if __name__ == "__main__":
    raise SystemExit(main())
