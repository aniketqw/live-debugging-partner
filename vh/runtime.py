"""Stepwise staging voice simulation and its code-enforced confirmation gate."""

from copy import deepcopy
from dataclasses import dataclass
import json
from pathlib import Path

from ldp.ledger import Job, Ledger, Out
from ldp.model import Params

from vh.agents.base import ModelAdapter
from vh.backend import Backend
from vh.caller import ScriptedCaller, hear_turn, random_streams
from vh.confirm import classify_confirm, classify_control, render
from vh.faults import FaultConfig
from vh.normalize import normalize, spoken_form
from vh.scenarios import Scenario, Turn, initial_state
from vh.tools import TOOLS, summary, tool_schemas, validate_args
from vh.tts import MockTTS
from vh.types import ToolCall


_MODES = ("bare", "prompt_only", "harness")
_ROLLBACK = "rollback_deployment"
_EXPLANATION = (
    "A staging rollback selects an earlier release. The simulator checks the service and release "
    "before it asks for confirmation. A status lookup reads the current release without changing it. "
    "You can stop the assistant talking while that lookup continues."
)


@dataclass
class CallResult:
    trace: list[dict]
    final_state: dict
    success: bool
    wrong_commit: bool
    metrics: dict


@dataclass
class _Pending:
    call: ToolCall
    job: Job
    shown_args: dict
    readback: str
    ready: bool = False
    reasks: int = 0


@dataclass
class _Speech:
    text: str
    start: int
    end: int
    words: list[tuple[str, int, int]]
    template: str | None
    call_id: str | None
    readback: bool
    speech_id: int


class CallSession:
    """Accept simulated input and advance independently of the scripted caller."""

    def __init__(self, model: ModelAdapter, mode: str, seed: int, backend: Backend,
                 params: Params | None = None, scenario: Scenario | None = None,
                 fault_p: float = 0.0, *, catch_prob: float = 1.0, external_speech: bool = False):
        if mode not in _MODES:
            raise ValueError("unknown run mode")
        self.model = model
        self.mode = mode
        self.backend = backend
        self.params = params or Params()
        self.external_speech = external_speech
        self.tts = MockTTS(self.params)
        self.ledger = Ledger()
        self.scenario = scenario
        self.trace: list[dict] = []
        self.now = 0
        self.turn = 0
        self.pending: _Pending | None = None
        self.retry_offer: ToolCall | None = None
        self._jobs: dict[int, tuple[Job, ToolCall]] = {}
        self._results: dict[int, dict] = {}
        self._attempted: set[str] = set()
        self._active: _Speech | None = None
        self._queue: list[tuple[str, str | None, str | None, bool]] = []
        self._out: list[dict] = []
        self.last_spoken = ""
        self.talk_over_ms = 0
        self.model_error = False
        self._faults = FaultConfig(fault_p)
        self._caller_rng, self._asr_rng = random_streams(seed)
        prompt = "agent_system_prompt_only.txt" if mode == "prompt_only" else "agent_system.txt"
        self.history = [{"role": "system", "content": (
            Path(__file__).with_name("prompts") / prompt).read_text(encoding="utf-8")}]
        self._emit("call", "start", scenario=scenario.id if scenario else "manual", mode=mode,
                   seed=seed, fault_p=fault_p, catch_prob=catch_prob, model=model.name)

    def _emit(self, stage: str, kind: str, *, meta: dict | None = None, **data) -> None:
        event = {"seq": len(self.trace), "t": self.now, "stage": stage, "kind": kind, "data": deepcopy(data)}
        if meta:
            event["meta"] = deepcopy(meta)
        self.trace.append(event)

    def _say(self, text: str, template: str | None = None, call_id: str | None = None,
             *, readback: bool = False) -> None:
        if not text.strip():
            return
        request = (text, template, call_id, readback)
        if self._active:
            self._queue.append(request)
        else:
            self._start_speech(*request)

    def _start_speech(self, text, template, call_id, readback) -> None:
        end, words = self.tts.speak(text, self.now)
        self._active = _Speech(text, self.now, end, words, template, call_id, readback, len(self.trace))
        item = {"text": text, "start_ms": self.now, "end_ms": end}
        self._out.append(item.copy())
        self._emit("tts", "start", **item, template=template, call_id=call_id)

    def _record_spoken(self, text: str) -> None:
        self.last_spoken = text
        self.history.append({"role": "assistant", "content": text})
        self._emit("history", "assistant", content=text)

    def _complete_speech(self) -> None:
        spoken, self._active = self._active, None
        self._record_spoken(spoken.text)
        if spoken.readback and self.pending and self.pending.call.id == spoken.call_id:
            self.pending.ready = True
        if self._queue:
            self._start_speech(*self._queue.pop(0))

    def _cut(self, prefix: str, count: int, cut_ms: int) -> None:
        spoken, self._active = self._active, None
        self._queue.clear()
        if self.pending and (spoken.call_id == self.pending.call.id or not self.pending.ready):
            self.pending.ready = False
        self._emit("tts", "cut", cut_ms=cut_ms, spoken_prefix=prefix, n_words_spoken=count)
        self._record_spoken(prefix)

    def speech_cut(self, spoken_prefix: str, n_words: int, t_ms: int) -> None:
        """Record an externally reported cut, limited to the phrase's actual prefix."""
        self._out = []
        self._advance(t_ms)
        if (self.mode != "harness" and not self.external_speech) or self._active is None:
            return
        if not 0 <= n_words <= len(self._active.words):
            raise ValueError("invalid spoken word count")
        expected = " ".join(word for word, _, _ in self._active.words[:n_words])
        if spoken_prefix != expected:
            raise ValueError("reported speech is not a prefix of the active phrase")
        self._cut(expected, n_words, t_ms)

    def active_speech(self) -> dict | None:
        if self._active is None:
            return None
        s = self._active
        return {"speech_id": s.speech_id, "text": s.text, "start_ms": s.start, "end_ms": s.end}

    def acknowledge_speech(self, speech_id: int, *, complete: bool,
                           prefix: str = "", n_words: int = 0) -> None:
        """Accept a client playback signal for exactly the current phrase."""
        if not self.external_speech or self._active is None or self._active.speech_id != speech_id:
            raise LookupError("stale playback")
        self._out = []
        if complete:
            self._advance(max(self.now, self._active.end))
            self._complete_speech()
        else:
            self.speech_cut(prefix, n_words, self.now)

    def _transition(self, job: Job, old, out=None) -> None:
        data = {"job": job.id, "name": job.name, "from": old.value if old else None,
                "to": job.state.value, "out": out.value if isinstance(out, Out) else out,
                "call_id": job.meta["call_id"]}
        self._emit("ledger", "transition", **data)

    def _new_job(self, call: ToolCall) -> Job:
        tool = TOOLS[call.name]
        irrev = tool.kind == "irrev"
        job = self.ledger.add(call.name, "chg" if irrev else "ro", tool.dur_ms,
                              reversible=not irrev, commit_ms=0 if irrev else None,
                              needs_yes=irrev and self.mode == "harness",
                              meta={"call_id": call.id})
        self._transition(job, None)
        return job

    def _stop(self, job: Job) -> Out:
        old = job.state
        outcome = self.ledger.stop(job, self.now)
        self._transition(job, old, outcome)
        if outcome in (Out.DROPPED, Out.CANCELLED):
            self._jobs.pop(job.id, None)
        return outcome

    def _tool_error(self, call: ToolCall, reason: str, *, dispatched: bool) -> None:
        self._emit("tool", "error", call_id=call.id, name=call.name,
                   args=call.args, reason=reason, dispatched=dispatched)
        self.history.append({"role": "tool", "tool_name": call.name,
                             "content": json.dumps({"ok": False, "error": reason}, sort_keys=True)})

    def _apply(self, job: Job, call: ToolCall) -> bool:
        try:
            result = self.backend.apply(call.name, call.args)
        except (TimeoutError, ValueError) as error:
            self._tool_error(call, str(error), dispatched=True)
            self._stop(job)
            if self.mode == "harness":
                if job.needs_yes:
                    self.retry_offer = call
                self._say(render("EXEC_ERROR"), "EXEC_ERROR", call.id)
            return False
        if job.kind == "chg":
            job.committed = True
            job.t_commit = self.now
        self._results[job.id] = result
        self._emit("tool", "exec", call_id=call.id, name=call.name, args=call.args,
                   tool_kind=TOOLS[call.name].kind, ok=True, result=result)
        self.history.append({"role": "tool", "tool_name": call.name,
                             "content": json.dumps({"ok": True, "result": result}, sort_keys=True)})
        if self.mode == "harness":
            observed = summary(call.name, call.args, result)
            if job.kind == "chg":
                self._say(render("EXEC_OK", summary=observed), "EXEC_OK", call.id)
            else:
                self._say(observed + ".", "STATUS", call.id)
        return True

    def _dispatch(self, job: Job, call: ToolCall) -> None:
        old = job.state
        self.ledger.start(job, self.now)
        self._transition(job, old)
        if job.kind == "chg" and not self._apply(job, call):
            return
        self._jobs[job.id] = (job, call)

    def _next_due(self) -> int | None:
        due = [job.t_start + job.dur_ms for job, _ in self._jobs.values()]
        if self._active and not self.external_speech:
            due.append(self._active.end)
        return min(due) if due else None

    def _advance(self, t: int) -> None:
        if type(t) is not int or t < self.now:
            raise ValueError("simulated time must be a nondecreasing integer")
        due = self._next_due()
        while due is not None and due <= t:
            self.now = due
            if self._active and not self.external_speech and self._active.end == due:
                self._complete_speech()
            for job, call in list(self._jobs.values()):
                if job.t_start + job.dur_ms != due:
                    continue
                self._jobs.pop(job.id)
                if job.kind == "ro" and not self._apply(job, call):
                    continue
                old = job.state
                self.ledger.finish(job, self.now)
                self._transition(job, old)
            due = self._next_due()
        self.now = t

    def tick(self, t_ms: int) -> list[dict]:
        self._out = []
        self._advance(t_ms)
        return self._out

    def drain(self) -> None:
        """Finish scheduled work and speech; used only by the offline runner."""
        next_time = self._next_due()
        while next_time is not None:
            self.tick(next_time)
            next_time = self._next_due()

    def _speak_readback(self, pending: _Pending, prefix: str = "") -> None:
        pending.ready = False
        call = pending.call
        self._emit("gate", "readback", call_id=call.id, name=call.name,
                   shown_args=pending.shown_args, text=pending.readback)
        text = prefix + pending.readback
        self._say(text, "READBACK", call.id, readback=True)

    def _propose(self, call: ToolCall, prefix: str = "") -> None:
        if call.id in self._attempted:
            self._tool_error(call, "duplicate_call", dispatched=False)
            return
        shown = deepcopy(call.args)
        readback = render("READBACK_rollback_deployment", service=shown["service"],
                          release=spoken_form(shown["release"], "release"))
        job = self._new_job(call)
        old = job.state
        self.ledger.announce(job)
        self._transition(job, old)
        self.pending = _Pending(call, job, shown, readback)
        self._speak_readback(self.pending, prefix)

    def _confirm(self, text: str, ready_at_turn_start: bool) -> None:
        pending = self.pending
        result = classify_confirm(text)
        if result == "yes" and not ready_at_turn_start:
            result = "other"
        self._emit("gate", result, turn=self.turn, transcript=text, call_id=pending.call.id)
        if result == "yes":
            self.pending = None
            confirmed = ToolCall(pending.call.id, pending.call.name, deepcopy(pending.shown_args))
            if confirmed.id not in self._attempted:
                self._attempted.add(confirmed.id)
                pending.job.confirmed = True
                self._dispatch(pending.job, confirmed)
        elif result == "no":
            self.pending = None
            self._stop(pending.job)
            self._say(render("CANCELLED"), "CANCELLED", pending.call.id)
        elif any(char.isdigit() for char in text):
            self.pending = None
            self._stop(pending.job)
            self._emit("gate", "abort", call_id=pending.call.id, reason="superseded")
            self.history.insert(len(self.history) - 1, {
                "role": "system", "content": "The caller corrected the previous request.",
            })
            self._respond(text, prefix=render("SUPERSEDED") + " ")
        elif pending.reasks == 0:
            pending.reasks = 1
            self._speak_readback(pending, render("REASK"))
        else:
            self.pending = None
            self._stop(pending.job)
            self._emit("gate", "abort", call_id=pending.call.id, reason="unclear")
            self._say(render("ABORT"), "ABORT", pending.call.id)

    def _control(self, controls: set[str]) -> None:
        jobs = self.ledger.live() or [job for job in self.ledger.jobs if job.done]
        if not jobs:
            return
        job = jobs[-1]
        if "protect" in controls:
            lookup = next((job for job in reversed(jobs) if job.kind == "ro" and job.running), None)
            if lookup:
                self.ledger.protected.add(lookup.name)
        if "hold" in controls:
            old = job.state
            self._transition(job, old, self.ledger.hold(job))
        if "stop_job" not in controls:
            return
        result = self._stop(job)
        call_id = job.meta["call_id"]
        if result in (Out.DROPPED, Out.CANCELLED):
            if self.pending and self.pending.job is job:
                self.pending = None
                self._emit("gate", "abort", call_id=call_id, reason="stopped")
            self._say(render("CANCELLED"), "CANCELLED", call_id)
        elif result in (Out.TOO_LATE, Out.DONE_IRREV) and job.id in self._results:
            observed = summary(job.name, {}, self._results[job.id])
            self._say(render("TOO_LATE", summary=observed), "TOO_LATE", call_id)

    def _safe_reply(self, text: str) -> str:
        if "explain" in text.lower():
            return _EXPLANATION
        if "roll" in text.lower():
            return "Which eligible release should staging use?"
        return "I can check staging status or prepare a rollback."

    def _respond(self, text: str, *, prefix: str = "") -> None:
        response = self.model.respond(deepcopy(self.history), tool_schemas())
        self._emit("model", "resp", text=response.text,
                   tool_calls=[{"id": c.id, "name": c.name, "args": c.args} for c in response.tool_calls],
                   meta=response.meta)
        if response.meta.get("error"):
            self.model_error = True
            if self.mode == "harness":
                self._say("The model did not respond. Nothing was changed.", "MODEL_ERROR")
                return
        proposed = False
        accepted = False
        for call in response.tool_calls:
            if self.mode == "harness" and call.name == _ROLLBACK:
                if proposed:
                    self._tool_error(call, "one_rollback_at_a_time", dispatched=False)
                    continue
                proposed = True
            issues = validate_args(call.name, call.args)
            if issues:
                self._tool_error(call, issues[0], dispatched=False)
                continue
            accepted = True
            if self.mode == "harness" and call.name == _ROLLBACK:
                self._propose(call, prefix)
            else:
                self._dispatch(self._new_job(call), call)
        if self.mode != "harness":
            self._say(response.text)
        elif not accepted:
            self._say(prefix + self._safe_reply(text), "SAFE_REPLY")

    def user_turn(self, transcript: str, t_ms: int, *, source: str = "speech") -> list[dict]:
        return self._user_turn(Turn(transcript), t_ms, source=source)

    def _user_turn(self, scripted: Turn, t_ms: int, *, source: str = "speech") -> list[dict]:
        self._out = []
        self._advance(t_ms)
        ready = bool(self.pending and self.pending.ready)
        if self._active and (source == "speech" or (self.external_speech and self.mode == "harness")):
            speaker_ms = len(scripted.say.split()) * self.params.speak_ms_per_word
            if self.mode == "harness":
                if self.external_speech:
                    # Without an explicit browser cut, do not invent words it heard.
                    self._cut("", 0, self.now)
                else:
                    end = min(self._active.end, self.now + self.params.barge_cut_ms)
                    self.talk_over_ms += min(speaker_ms, end - self.now)
                    prefix, words = self.tts.cut(self._active.words, end)
                    self._cut(prefix, words, end)
            else:
                self.talk_over_ms += min(speaker_ms, max(0, self._active.end - self.now))
        self.turn += 1
        self._emit("caller", "say", turn=self.turn, text=scripted.say)
        heard, edits = (hear_turn(scripted, self._asr_rng, self._faults)
                         if source == "speech" else (scripted.say, []))
        self._emit("asr", "out", turn=self.turn, transcript=heard, faults=edits)
        text = heard
        if self.mode == "harness":
            text, spans = normalize(heard)
            self._emit("norm", "out", turn=self.turn, text=text, spans=spans)
        self.history.append({"role": "user", "content": text})
        if self.mode == "harness":
            controls = classify_control(text)
            if controls and not any(char.isdigit() for char in text):
                self._control(controls)
                return self._out
            if self.pending:
                self._confirm(text, ready)
                return self._out
            if self.retry_offer:
                failed, self.retry_offer = self.retry_offer, None
                if classify_confirm(text) == "yes":
                    self._propose(ToolCall(f"{failed.id}-retry-{self.turn}", failed.name, failed.args))
                return self._out
        self._respond(text)
        return self._out

    def _finish_call(self) -> CallResult:
        self.drain()
        final = self.backend.snapshot()
        success = bool(self.scenario and final == self.scenario.expected_state())
        wrong_commit = bool(self.scenario and any(
            item["tool"] == _ROLLBACK and item["args"] != self.scenario.intended
            for item in self.backend.audit
        ))
        self._emit("call", "end", state_hash=self.backend.state_hash(), success=success,
                   model_error=self.model_error, talk_over_ms=self.talk_over_ms,
                   final_state=final)
        return CallResult(self.trace, final, success, wrong_commit, {
            "model_error": self.model_error, "talk_over_ms": self.talk_over_ms,
        })


def run_call(scenario: Scenario, model: ModelAdapter, mode: str, seed: int,
             fault_p: float = 0.0, catch_prob: float = 1.0,
             backend_fault: str | None = None, params: Params | None = None) -> CallResult:
    fault = scenario.backend_fault if backend_fault is None else backend_fault
    session = CallSession(model, mode, seed, Backend(initial_state(), fault=fault), params,
                          scenario, fault_p, catch_prob=catch_prob)
    caller = ScriptedCaller(scenario, session._caller_rng, catch_prob)
    for turn in scenario.turns:
        if turn.when == "after_agent":
            session.drain()
        elif turn.when.startswith("barge@"):
            if session._active:
                start = session._active.start + int(turn.when.split("@", 1)[1])
                session.tick(max(session.now, start))
            else:
                session.drain()
        if turn.role == "confirm_reply":
            while "say yes to confirm" in session.last_spoken.lower():
                reply = caller.reply(session.last_spoken)
                session.user_turn(reply, session.now)
                session.drain()
                if reply in ("yes", "cancel"):
                    break
        else:
            session._user_turn(turn, session.now)
    return session._finish_call()
