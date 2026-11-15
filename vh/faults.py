"""Seeded fault injection for simulated speech, with reversible edit records."""

from dataclasses import dataclass
from random import Random
import re


_ORDER = ("digit_sub", "digit_drop", "digit_swap", "name_homophone", "word_drop")
_DIGITS = "0123456789"
_DIGIT_WORDS = frozenset("zero one two three four five six seven eight nine".split())
_CONFUSABLE = {
    "five": "nine", "nine": "five", "one": "won", "two": "to",
    "four": "for", "eight": "ate", "three": "tree", "six": "sicks",
}
_NAMES = {"checkout-api": "check-out-api"}


@dataclass(frozen=True)
class FaultConfig:
    p: float
    kinds: tuple[str, ...] = _ORDER

    def __post_init__(self):
        if not 0 <= self.p <= 1:
            raise ValueError("fault probability must be in [0, 1]")
        if any(kind not in _ORDER for kind in self.kinds):
            raise ValueError("unknown fault kind")


def _number(token: str) -> bool:
    return token.lower() in _DIGIT_WORDS or token.isascii() and token.isdigit()


def inject(reference: str, rng: Random, cfg: FaultConfig) -> tuple[str, list[dict]]:
    """Alter whitespace-delimited tokens and log exact edits in application order."""
    if not cfg.p or not cfg.kinds:
        return reference, []
    parts = re.findall(r"\s+|\S+", reference)
    faults = []
    offset = 0
    for index, token in enumerate(parts):
        if token.isspace():
            offset += len(token)
            continue
        lower = token.lower()
        numeric = _number(token)
        literal = token.isascii() and token.isdigit()
        partner = None
        if numeric and "digit_swap" in cfg.kinds:
            partner = next((i for i in range(index + 1, len(parts)) if _number(parts[i])), None)
        applicable = {
            "digit_sub": literal or lower in _CONFUSABLE,
            "digit_drop": numeric,
            "digit_swap": partner is not None and token != parts[partner],
            "name_homophone": lower in _NAMES,
            "word_drop": not numeric and lower not in _NAMES,
        }
        choices = [kind for kind in _ORDER if kind in cfg.kinds and applicable[kind]]
        # Draw probability first, then choose the kind, then a numeric
        # replacement (if needed). A digit swap visits the later slot normally.
        if choices and rng.random() < cfg.p:
            kind = rng.choice(choices)
            before = token
            if kind == "digit_swap":
                before = "".join(parts[index:partner + 1])
                parts[index], parts[partner] = parts[partner], parts[index]
                after = "".join(parts[index:partner + 1])
            else:
                if kind == "digit_sub" and literal:
                    position, replacement = rng.choice([
                        (i, value) for i, current in enumerate(token)
                        for value in _DIGITS if current != value
                    ])
                    after = token[:position] + replacement + token[position + 1:]
                elif kind == "digit_sub":
                    after = _CONFUSABLE[lower]
                elif kind == "name_homophone":
                    after = _NAMES[lower]
                else:
                    after = ""
                parts[index] = after
            faults.append({"kind": kind, "index": offset, "before": before, "after": after})
        offset += len(parts[index])
    return "".join(parts), faults
