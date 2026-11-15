"""Synthetic caller decisions and independent fault and correction streams."""

from random import Random
import re

from vh.faults import FaultConfig, inject
from vh.normalize import normalize, spoken_form
from vh.scenarios import Scenario, Turn


def random_streams(seed: int) -> tuple[Random, Random]:
    return Random(seed * 1000 + 17), Random(seed * 1000 + 31)


def hear_turn(turn: Turn, rng: Random, cfg: FaultConfig) -> tuple[str, list[dict]]:
    """Apply the fixed scenario edit before any seeded random edits."""
    reference = turn.say
    fixed = []
    if turn.misheard_last is not None:
        before, after = turn.misheard_last
        index = reference.rindex(before)
        reference = reference[:index] + after + reference[index + len(before):]
        fixed.append({"kind": "digit_sub", "index": index, "before": before, "after": after})
    transcript, edits = inject(reference, rng, cfg)
    return transcript, fixed + edits


class ScriptedCaller:
    def __init__(self, scenario: Scenario, rng: Random, catch_prob: float):
        if not 0 <= catch_prob <= 1:
            raise ValueError("catch probability must be in [0, 1]")
        self.scenario = scenario
        self.rng = rng
        self.catch_prob = catch_prob
        self.corrections = 0

    def reply(self, spoken: str) -> str:
        """React to actual speech; continue after at most three corrections."""
        if self.corrections >= 3:
            return "cancel"
        intended = self.scenario.intended
        text, _ = normalize(spoken.lower())
        pattern = rf"\bstaging\s+{re.escape(intended['service'])}\s+to\s+release\s+([0-9]{{2}})\b"
        heard = re.search(pattern, text)
        if heard and heard[1] == intended["release"] and "say yes to confirm" in text:
            return "yes"
        if self.rng.random() >= self.catch_prob:
            return "yes"
        self.corrections += 1
        return f"No, it is {spoken_form(intended['release'], 'release')}."
