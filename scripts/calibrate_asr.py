"""Summarize opted-in script attempts; does not send or collect audio."""

from argparse import ArgumentParser
from collections import Counter
from difflib import SequenceMatcher
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from vh.normalize import normalize


_KEYS = ("digit_substitutions", "digit_drops", "digit_insertions", "digit_swaps", "service_errors")


def digits(text):
    return [c for c in normalize(text)[0] if c in "0123456789"]


def differences(reference, transcript):
    expected, heard = digits(reference), digits(transcript)
    counts = dict.fromkeys(_KEYS, 0)
    if len(expected) == len(heard):
        i = 0
        while i + 1 < len(expected):
            pair = expected[i:i+2]
            if pair[0] != pair[1] and pair[::-1] == heard[i:i+2]:
                counts["digit_swaps"] += 1
                heard[i:i+2] = pair
                i += 2
            else:
                i += 1
    for op, a, b, c, d in SequenceMatcher(a=expected, b=heard, autojunk=False).get_opcodes():
        if op == "replace":
            counts["digit_substitutions"] += min(b-a, d-c)
        if op in ("replace", "delete"):
            counts["digit_drops"] += max(0, (b-a) - (d-c))
        if op in ("replace", "insert"):
            counts["digit_insertions"] += max(0, (d-c) - (b-a))
    has_service = lambda phrase: bool(re.search(r"(?<![\w-])checkout-api(?![\w-])", phrase.lower()))
    counts["service_errors"] = int(has_service(reference) and not has_service(transcript))
    return counts


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, nargs="?", default=ROOT / "results/demo_sessions.jsonl")
    args = parser.parse_args()
    if not args.path.is_file():
        print("No opted-in voice attempts recorded; calibration was not measured.")
        return
    rows = [json.loads(line) for line in args.path.read_text(encoding="utf-8").splitlines() if line]
    if not rows:
        print("No opted-in voice attempts recorded; calibration was not measured.")
        return
    print(f"Attempts: {len(rows)}. Pseudonyms: {len({row['speaker_label'] for row in rows})}.")
    print(f"Reported browser labels: {len({row['browser'] for row in rows})}. Small sample, not a recogniser benchmark.")
    counts = Counter()
    for row in rows:
        counts.update(differences(row["reference"], row["transcript"]))
    for key in _KEYS:
        print(f"{key}: {counts[key]}")


if __name__ == "__main__":
    main()
