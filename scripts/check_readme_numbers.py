"""Check that numerical claims in the harness README appear in generated results."""

from argparse import ArgumentParser
import json
from pathlib import Path
import re


_ROOT = Path(__file__).resolve().parents[1]
_NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)*%?")
_LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\n]*)\)")


def numerals(text: str) -> set[str]:
    # The label is rendered as prose; the hidden link path can contain a trace ID.
    rendered = _LINK.sub(r"\1", text)
    return set(_NUMBER.findall(rendered))


def main(argv=None) -> int:
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--readme", type=Path, default=_ROOT / "README_VH.md")
    parser.add_argument("--results", type=Path, default=_ROOT / "results/vh/RESULTS.md")
    parser.add_argument("--allowlist", type=Path, default=_ROOT / "scripts/readme_number_allowlist.json")
    args = parser.parse_args(argv)
    allow = set(json.loads(args.allowlist.read_text(encoding="utf-8")))
    readme = numerals(args.readme.read_text(encoding="utf-8"))
    generated = numerals(args.results.read_text(encoding="utf-8"))
    extra = sorted(readme - generated - allow)
    if extra:
        print("README numbers absent from generated results: " + ", ".join(extra))
        return 1
    print("PASS: README numerals are present in generated results or the version allowlist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
