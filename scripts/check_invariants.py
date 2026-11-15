"""Report violations in saved staging traces; exit nonzero for a breached harness invariant."""

from argparse import ArgumentParser
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vh.checks import check_invariants
from vh.scenarios import SCENARIOS
from vh.trace import read_trace


def main() -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="A JSONL trace or directory of traces")
    source = parser.parse_args().path
    paths = sorted(source.rglob("*.jsonl")) if source.is_dir() else [source]
    if not paths:
        print("No trace files found.")
        return 1
    failed = False
    print("Trace | Mode | I1 | I2 | I3 | I5 | I6 | I7")
    print("I4 (cross-run determinism) is checked separately.")
    for path in paths:
        try:
            trace = read_trace(path)
            start = trace[0]
            if (start["stage"], start["kind"]) != ("call", "start"):
                raise ValueError("trace does not start with call.start")
            mode = start["data"]["mode"]
            if mode not in ("bare", "prompt_only", "harness"):
                raise ValueError("unknown trace mode")
            scenario = SCENARIOS[start["data"]["scenario"]]
            violations = check_invariants(trace, scenario, mode)
        except (OSError, ValueError, IndexError, KeyError) as error:
            print(f"{path}: invalid trace ({type(error).__name__})")
            failed = True
            continue
        counts = " | ".join(str(len(violations[key])) for key in ("I1", "I2", "I3", "I5", "I6", "I7"))
        print(f"{path} | {mode} | {counts}")
        if mode == "harness" and any(violations.values()):
            failed = True
            print("  " + ", ".join(f"{key}: {items}" for key, items in violations.items() if items))
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
