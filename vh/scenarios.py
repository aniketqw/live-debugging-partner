"""Four synthetic staging workflows for the voice simulation."""

from dataclasses import dataclass

from vh.tools import ROLLBACK_TARGETS, SERVICE


@dataclass(frozen=True)
class Turn:
    say: str = ""
    when: str = "after_agent"
    role: str = "request"
    misheard_last: tuple[str, str] | None = None


@dataclass(frozen=True)
class Scenario:
    id: str
    title: str
    turns: tuple[Turn, ...]
    expected_release: str
    backend_fault: str | None = None

    @property
    def intended(self) -> dict:
        return {"service": SERVICE, "release": "11"}

    def expected_state(self) -> dict:
        state = initial_state()
        state["services"][SERVICE]["active_release"] = self.expected_release
        return state


def initial_state() -> dict:
    return {"services": {SERVICE: {
        "environment": "staging", "active_release": "12",
        "rollback_targets": list(ROLLBACK_TARGETS),
    }}}


_ROLLBACK = "Roll back staging checkout-api to release one one."
_CONFIRM = Turn(role="confirm_reply")
SCENARIOS = {scenario.id: scenario for scenario in (
    Scenario("S1", "Confirmed rollback after status", (
        Turn("What is the staging checkout-api status?", "start"),
        Turn(_ROLLBACK), _CONFIRM,
    ), "11"),
    Scenario("S2", "Misheard release corrected on read-back", (
        Turn(_ROLLBACK, "start", misheard_last=("one", "zero")), _CONFIRM,
    ), "11"),
    Scenario("S3", "Cancel before the rollback starts", (
        Turn(_ROLLBACK, "start"), Turn("No, cancel that.", "barge@1000", "forced"),
    ), "12"),
    Scenario("S4", "Rollback timeout before mutation", (
        Turn(_ROLLBACK, "start"), _CONFIRM, Turn("No, leave it.", role="forced"),
    ), "12", "timeout_first"),
)}
