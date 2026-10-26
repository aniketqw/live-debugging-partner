"""The action ledger: what state each agent action is in, and what speech may do to it.

Rows follow SESSIONS.md section 2. Stopping speech is nearly free. Stopping work
depends on the state of the action.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Set


class St(str, Enum):
    PROPOSED = "proposed"              # in the agent's plan, not said
    ANNOUNCED = "announced"            # said aloud, not started
    RUNNING_RO = "running_read_only"
    RUNNING_CHG = "running_changing"
    PAUSED = "paused"
    DONE_REV = "done_reversible"
    DONE_IRREV = "done_irreversible"
    CANCELLED = "cancelled"
    UNDONE = "undone"


class Out(str, Enum):
    """Result of a stop or undo command."""
    DROPPED = "dropped"            # was pending: removed for free
    CANCELLED = "cancelled"        # was running: stopped, work lost
    TOO_LATE = "too_late"          # changing job past its commit point: the step will finish
    PROTECTED = "protected"        # the user said to keep it
    DONE_REV = "done_reversible"   # already done: offer undo
    DONE_IRREV = "done_irreversible"  # already done: say it cannot be undone, offer repair
    UNDO_OK = "undo_ok"
    NOOP = "noop"


@dataclass
class Job:
    id: int
    name: str
    kind: str                          # "ro" read-only, "chg" changing
    dur_ms: int
    commit_ms: Optional[int] = None    # run time when a changing job's effect becomes permanent
    reversible: bool = True
    pausable: bool = False
    edit: bool = False                 # the edit hold applies to it
    needs_yes: bool = False            # irreversible: ask for a spoken yes first
    announce: str = ""
    after: List["Job"] = field(default_factory=list)
    target: Optional[str] = None
    key: Optional[tuple] = None        # (utterance id, segment) that created it
    on_commit: Optional[Callable] = None
    on_done: Optional[Callable] = None
    meta: dict = field(default_factory=dict)
    state: St = St.PROPOSED
    run_ms: int = 0
    t_start: Optional[int] = None
    t_commit: Optional[int] = None
    t_end: Optional[int] = None
    committed: bool = False
    confirmed: bool = False
    announced: bool = False
    pause_reason: Optional[str] = None

    def __post_init__(self):
        if self.kind == "chg" and self.commit_ms is None:
            self.commit_ms = self.dur_ms

    @property
    def running(self) -> bool:
        return self.state in (St.RUNNING_RO, St.RUNNING_CHG)

    @property
    def live(self) -> bool:
        return self.state in (St.PROPOSED, St.ANNOUNCED, St.RUNNING_RO, St.RUNNING_CHG, St.PAUSED)

    @property
    def done(self) -> bool:
        return self.state in (St.DONE_REV, St.DONE_IRREV)


class Ledger:
    def __init__(self):
        self.jobs: List[Job] = []
        self.protected: Set[str] = set()
        self._n = 0

    def add(self, name, kind, dur_ms, **kw) -> Job:
        self._n += 1
        job = Job(self._n, name, kind, dur_ms, **kw)
        self.jobs.append(job)
        return job

    def named(self, name) -> List[Job]:
        return [j for j in self.jobs if j.name == name]

    def live(self) -> List[Job]:
        return [j for j in self.jobs if j.live]

    # -- transitions -------------------------------------------------
    def announce(self, job: Job):
        if job.state == St.PROPOSED:
            job.state = St.ANNOUNCED
            job.announced = True

    def start(self, job: Job, t: int):
        assert job.state in (St.PROPOSED, St.ANNOUNCED), job.state
        job.state = St.RUNNING_RO if job.kind == "ro" else St.RUNNING_CHG
        job.t_start = t

    def pause(self, job: Job, reason: str) -> bool:
        if job.state == St.RUNNING_CHG and job.pausable:
            job.state = St.PAUSED
            job.pause_reason = reason
            return True
        return False

    def resume(self, job: Job):
        if job.state == St.PAUSED:
            job.state = St.RUNNING_CHG
            job.pause_reason = None

    def finish(self, job: Job, t: int):
        job.t_end = t
        if job.kind == "ro" or job.reversible:
            job.state = St.DONE_REV
        else:
            job.state = St.DONE_IRREV

    # -- speech commands ---------------------------------------------
    def hold(self, job: Job) -> str:
        """'Wait' or 'hold': what happens to the job."""
        if job.state in (St.PROPOSED, St.ANNOUNCED):
            return "kept_pending"
        if job.state == St.RUNNING_RO:
            return "continue"
        if job.state == St.RUNNING_CHG:
            return "paused" if self.pause(job, "hold") else "finish_step"
        if job.state == St.PAUSED:
            return "paused"
        return "n/a"

    def stop(self, job: Job, t: int, force: bool = False) -> Out:
        """'Stop' or 'cancel': what happens to the job."""
        s = job.state
        if s in (St.PROPOSED, St.ANNOUNCED):
            job.state, job.t_end = St.CANCELLED, t
            return Out.DROPPED
        if s == St.RUNNING_RO or (s == St.PAUSED and job.kind == "ro"):
            if job.name in self.protected and not force:
                return Out.PROTECTED
            job.state, job.t_end = St.CANCELLED, t
            return Out.CANCELLED
        if s in (St.RUNNING_CHG, St.PAUSED):
            if job.committed:
                return Out.TOO_LATE
            job.state, job.t_end = St.CANCELLED, t
            return Out.CANCELLED
        if s == St.DONE_REV:
            return Out.DONE_REV
        if s == St.DONE_IRREV:
            return Out.DONE_IRREV
        return Out.NOOP

    def undo(self, job: Job) -> Out:
        if job.state == St.DONE_REV and job.kind == "chg":
            job.state = St.UNDONE
            return Out.UNDO_OK
        if job.state == St.DONE_IRREV:
            return Out.DONE_IRREV
        return Out.NOOP
