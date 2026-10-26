"""Decision rules for the decision points D1 to D7 (SESSIONS.md section 5)."""
from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Policy:
    name: str
    listens: bool = True                  # D1: stop talking, and stay quiet, while the user speaks
    onset_jobs: str = "pause_changing"    # D2/D3 at speech onset: "none", "pause_changing", "cancel_all"
    process_idle: bool = False            # handle a message only when the agent is idle
    force_cancel: bool = False            # a cancel ignores "keep it running"
    honour_hold: bool = True              # "don't change anything yet"
    confirm_irreversible: bool = True     # D6: ask for a spoken yes first
    ask_on_unresolved: bool = True        # D4: ask when the reference is unclear
    notify_events: bool = True            # D5: say one line when something important happens
    eager: bool = True                    # D7: act on partial speech where it is safe
    wait_marker: bool = True              # D7: wait when a correction cue is heard
    commit_delay_ms: int = 1200
    bind_at_word: bool = True             # bind "this one" to the selection at the time of the word
    truthful: bool = True                 # say plainly when it is too late to stop


LEDGER_RULES = Policy("ledger_rules")
ALWAYS_STOP = Policy("always_stop", onset_jobs="cancel_all", force_cancel=True,
                     eager=False, wait_marker=False)
NEVER_STOP = Policy("never_stop", listens=False, onset_jobs="none", process_idle=True,
                    confirm_irreversible=False, ask_on_unresolved=False,
                    eager=False, wait_marker=False)

POLICIES = {p.name: p for p in (LEDGER_RULES, ALWAYS_STOP, NEVER_STOP)}

# Trap policies: each is ledger rules with one rule broken. Tests expect each to fail
# one named check.
TRAPS = {
    "ignore_hold": replace(LEDGER_RULES, name="ignore_hold", honour_hold=False),
    "no_confirm": replace(LEDGER_RULES, name="no_confirm", confirm_irreversible=False),
    "end_bind": replace(LEDGER_RULES, name="end_bind", bind_at_word=False),
    "false_ack": replace(LEDGER_RULES, name="false_ack", truthful=False, confirm_irreversible=False),
    "end_bind_guess": replace(LEDGER_RULES, name="end_bind_guess", bind_at_word=False, ask_on_unresolved=False),
    "talk_over": replace(LEDGER_RULES, name="talk_over", listens=False),
    "quiet": replace(LEDGER_RULES, name="quiet", notify_events=False),
    "guesser": replace(LEDGER_RULES, name="guesser", ask_on_unresolved=False),
    "eager_all": replace(LEDGER_RULES, name="eager_all", wait_marker=False, commit_delay_ms=0),
}
