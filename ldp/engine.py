"""Discrete-event engine. One run = one session x one arm x one policy.

Time is in milliseconds on a 100 ms tick. Every run is deterministic for a given
session variant: lag jitter is a hash of the variant, never of the arm or policy.
"""
from __future__ import annotations

import heapq
import random
from dataclasses import replace
from typing import Dict, List, Optional

from .channels import Arm
from .ledger import Ledger, Out, St
from .model import Intent, Params, Part, SessionSpec, Utterance, make_utt
from .policies import Policy

UNRES = "?"
# Meanings the agent may act on while the user is still speaking (all cheap to undo).
ALWAYS_EARLY = {"STOP_SPEECH", "HOLD_EDITS", "LIFT_HOLD", "KEEP_JOB", "CANCEL",
                "CONSTRAINT", "REQUIREMENT", "FOCUS"}


class Engine:
    def __init__(self, spec: SessionSpec, arm: Arm, policy: Policy, params: Params = None):
        self.spec, self.arm, self.policy = spec, arm, policy
        self.P = params or Params()
        if arm.name == "oracle":
            self.P = replace(self.P, oracle=True)
        self.t = 0
        self.heap: list = []
        self._seq = 0
        self.ledger = Ledger()
        self.app = spec.app_factory()
        self.log: List[tuple] = []
        # agent state
        self.edit_hold = False
        self.constraints: set = set()
        self.requirements: set = set()
        self.focus: Optional[str] = None
        self.cur_key = None
        self.cur_utt: Optional[Utterance] = None
        self.speech_q: List[str] = []
        self.speech_cur: Optional[list] = None
        self.speech_log: List[tuple] = []
        self.inbox: List[Utterance] = []
        self.pending_ask: Dict[str, tuple] = {}
        self.commit_timers: Dict[tuple, object] = {}
        self.seg_done: set = set()
        self.pending_segs: Dict[str, set] = {}
        self.applied: Dict[str, int] = {}
        self.t_send: Dict[str, int] = {}
        self.user_speech: List[tuple] = []
        self.yes_ms: Optional[int] = None
        self._reply_n = 0
        # counters for metrics
        self.wasted_ms = 0
        self.unwanted: List[dict] = []
        self.repeats = 0
        self.asks = 0
        self.words_in = 0
        self.input_ms = 0
        self.off_app_ms = 0
        self.agent_words = 0
        self.answer_t: Dict[str, int] = {}
        self.query_t: Dict[str, int] = {}
        self.late_reports: List[int] = []

    # -- plumbing ----------------------------------------------------
    def at(self, t: int, fn):
        tick = self.P.tick_ms
        t = max(self.t, -(-int(t) // tick) * tick)
        self._seq += 1
        heapq.heappush(self.heap, (t, self._seq, fn))

    def lag(self, name: str, u: Utterance, key) -> int:
        if self.P.oracle:
            return 0
        base = getattr(self.P, name)
        r = random.Random(f"{self.spec.sid}:{self.spec.variant}:{u.uid.split('~')[0]}:{key}").uniform(0.85, 1.15)
        return int(base * r)

    def event(self, ev: str, **kw):
        self.log.append((self.t, ev, kw))

    # -- API used by the apps ---------------------------------------
    def say(self, text: str):
        self.agent_words += len(text.split())
        if self.arm.voice_out:
            self.speech_q.append(text)
        else:
            self.event("say_start", text=text)

    def notify(self, text: str):
        if self.policy.notify_events:
            self.say(text)

    def new_job(self, name, kind, dur_ms, **kw):
        kw.setdefault("key", self.cur_key)
        job = self.ledger.add(name, kind, dur_ms, **kw)
        self.event("job_new", job=name, id=job.id, kind=kind)
        return job

    def flag_unwanted(self, job, why: str):
        w = 1 if job.reversible else 3
        self.unwanted.append({"t": self.t, "job": job.name, "why": [why], "w": w})
        self.event("unwanted", job=job.name, why=[why])

    def mark_answer(self, topic: str):
        self.answer_t.setdefault(topic, self.t)

    def running(self, name: str):
        return [j for j in self.ledger.named(name) if j.running]

    def busy(self) -> bool:
        if any(j.state in (St.RUNNING_RO, St.RUNNING_CHG, St.PAUSED) for j in self.ledger.jobs):
            return True
        return bool(self.arm.voice_out and (self.speech_cur or self.speech_q))

    # -- scheduling the user's side ---------------------------------
    def schedule_utt(self, u: Utterance):
        A, P = self.arm, self.P
        self.pending_segs[u.uid] = set(u.final_idx())
        if A.voice_in:
            t0, t1 = u.t, u.t + u.dur_ms
            self.user_speech.append((t0, t1))
            self.words_in += len(u.words)
            self.input_ms += u.dur_ms
            self.at(t0, lambda: self.event("user_speech", uid=u.uid, text=u.text, end=t1))
            if A.vad:
                self.at(t0 + self.lag("vad_lag_ms", u, "vad"), lambda: self._onset(u))
            if A.stream:
                for j in range(len(u.segs)):
                    self.at(u.seg_end(j) + self.lag("stream_lag_ms", u, j),
                            lambda j=j: self._deliver_segment(u, j))
                t_fin = t1 + self.lag("final_lag_ms", u, "fin")
            else:
                t_fin = t1 + self.lag("asr_lag_ms", u, "fin")
            t_in_end = t1
        else:
            typing = u.typed_words * P.type_ms_per_word + P.send_ms
            switch = P.switch_ms if u.hands_on else 0
            t_fin = t_in_end = u.t + switch + typing
            self.words_in += u.typed_words
            self.input_ms += typing
            if u.hands_on:
                self.off_app_ms += switch + typing
            self.at(u.t, lambda: self.event("user_typing", uid=u.uid, text=u.text, end=t_fin))
        self.t_send[u.uid] = t_fin
        self.at(t_fin, lambda: self._deliver_final(u))
        if u.must_apply and not u.dup_of:
            self.at(t_in_end + u.patience_ms, lambda: self._patience(u))

    def _patience(self, u: Utterance):
        if u.uid in self.applied:
            return
        rep = replace(u, uid=u.uid + "~r", t=self.t + 500, dup_of=u.uid, must_apply=False)
        self.repeats += 1
        self.event("user_repeats", uid=rep.uid)
        self.schedule_utt(rep)

    # -- deliveries --------------------------------------------------
    def _onset(self, u: Utterance):
        self.event("onset", uid=u.uid)
        p = self.policy
        if p.listens:
            self._cut_speech(self.lag("barge_cut_ms", u, "cut"), flush=True)
        if p.onset_jobs == "pause_changing":
            for job in self.ledger.jobs:
                if job.state == St.RUNNING_CHG and self.ledger.pause(job, "onset"):
                    self.event("job_pause", job=job.name, why="onset")
        elif p.onset_jobs == "cancel_all":
            for job in list(self.ledger.live()):
                self._stop_job(job, force=True)

    def _deliver_segment(self, u: Utterance, j: int):
        """Interactive voice: one clause of the sentence is understood."""
        seg, p = u.segs[j], self.policy
        if seg.marker:
            if p.wait_marker:
                for key in list(self.commit_timers):
                    if key[0] == u.uid and self.commit_timers[key] != "held":
                        self.commit_timers[key] = "held"
                        self.event("marker_hold", key=key)
            return
        if not p.eager or seg.intent is None or u.uid in self.applied:
            return
        if seg.replaces is not None:
            self._revoke((u.uid, seg.replaces))
        it = seg.intent
        if it.kind in ALWAYS_EARLY:
            self._process(u, j)
        elif it.kind in ("TASK", "QUERY") and it.args.get("ro"):
            key = (u.uid, j)
            self.commit_timers[key] = self.t + p.commit_delay_ms
            self.at(self.t + p.commit_delay_ms, lambda: self._commit_timer(u, j))

    def _commit_timer(self, u: Utterance, j: int):
        v = self.commit_timers.get((u.uid, j))
        if v is None or v == "held":
            return
        self.commit_timers.pop((u.uid, j))
        self._process(u, j)

    def _revoke(self, key):
        self.commit_timers.pop(key, None)
        for job in list(self.ledger.jobs):
            if job.key == key and job.live:
                self._stop_job(job, force=True)
                self.event("revoke", job=job.name)

    def _deliver_final(self, u: Utterance):
        if u.uid in self.applied:
            self.event("duplicate_dropped", uid=u.uid)
            self._resume_onset()
            return
        if (self.arm.queue or self.policy.process_idle) and (self.inbox or self.busy()):
            self.inbox.append(u)
            self.event("queued", uid=u.uid)
            return
        self._process_final(u)

    def _drain(self):
        while self.inbox and not self.busy():
            u = self.inbox.pop(0)
            if u.uid not in self.applied:
                self._process_final(u)

    def _process_final(self, u: Utterance):
        for s in u.segs:
            if s.replaces is not None:
                self._revoke((u.uid, s.replaces))
        # constraints and holds in the same sentence apply before any task starts
        for j in sorted(u.final_idx(), key=lambda j: u.segs[j].intent.kind not in ALWAYS_EARLY):
            self._process(u, j)
        self._resume_onset()

    def _resume_onset(self):
        for job in self.ledger.jobs:
            if job.state == St.PAUSED and job.pause_reason == "onset":
                self.ledger.resume(job)
                self.event("job_resume", job=job.name)

    # -- understanding one meaning ------------------------------------
    def _bind(self, u: Utterance, j: int) -> str:
        mode = self.arm.bind
        if mode == "none":
            return UNRES
        if mode == "word" and not self.policy.bind_at_word:
            mode = "end"
        seg = u.segs[j]
        ref = seg.intent.ref
        if mode == "send" and seg.typed_ref is not None:
            ref = seg.typed_ref
        return self._resolve(u, ref, seg, mode)

    def _resolve(self, u, ref, seg, mode) -> str:
        if ref.kind == "deictic":
            if mode == "word":
                tb = u.word_time(seg.w0 + ref.word)
            elif mode == "send":
                tb = self.t_send[u.uid]
            else:
                tb = u.t + u.dur_ms
            return self.spec.selection_at(tb) or UNRES
        base_seg = u.segs[ref.base]
        base = self._resolve(u, base_seg.intent.ref, base_seg, mode)
        order = self.spec.truth["order"]
        if base not in order:
            return UNRES
        k = order.index(base) + ref.rel
        return order[k] if 0 <= k < len(order) else UNRES

    def _process(self, u: Utterance, j: int):
        key = (u.uid, j)
        if key in self.seg_done:
            return
        self.seg_done.add(key)
        self.commit_timers.pop(key, None)
        self.cur_key, self.cur_utt = key, u
        it = u.segs[j].intent
        target = None
        if it.ref is not None:
            target = self._bind(u, j)
            if target == UNRES:
                if self.policy.ask_on_unresolved:
                    self._ask(u, j, it)
                    return
                target = self.spec.truth.get("default_guess")
        self._apply(it, target)
        self._mark(u, j)

    def _mark(self, u: Utterance, j: int):
        left = self.pending_segs.get(u.uid, set())
        left.discard(j)
        if not left and u.uid not in self.applied:
            base = u.uid.split("~")[0]
            for uid in (u.uid, base, base + "~r"):   # a repeat and its original count as one
                self.applied.setdefault(uid, self.t)

    def _ask(self, u: Utterance, j: int, it: Intent):
        key = it.args.get("ask_key", it.kind)
        self.asks += 1
        q = "Which one do you mean?"
        self.pending_ask[key] = (u, j, it)
        self.say(q)
        text, target = self.spec.truth["answers"][key]
        self._schedule_reply(key, text, target, hands_on=u.hands_on, after_words=len(q.split()))

    def _schedule_reply(self, key, text, target, hands_on, after_words=0):
        self._reply_n += 1
        when = self.t + (after_words * self.P.tts_ms_per_word if self.arm.voice_out else 0) + self.P.reply_delay_ms
        rep = make_utt(f"reply.{key}.{self._reply_n}", when,
                       [Part(text, Intent("ANSWER", {"key": key, "target": target}))],
                       hands_on=hands_on, params=self.P)
        self.schedule_utt(rep)

    def _apply(self, it: Intent, target):
        k, a = it.kind, it.args
        self.event("intent", kind=k, args=a, target=target)
        if target is not None:
            a = {**a, "target": target}
            it = replace(it, args=a)
        if k == "STOP_SPEECH":
            self._cut_speech(0, flush=True)
        elif k == "HOLD_EDITS":
            if self.policy.honour_hold:
                self.edit_hold = True
                for job in self.ledger.jobs:
                    if job.edit and job.state == St.RUNNING_CHG:
                        self.ledger.hold(job)
                self.say("Edits paused.")
        elif k == "LIFT_HOLD":
            self.edit_hold = False
            for job in self.ledger.jobs:
                if job.state == St.PAUSED and job.pause_reason == "hold":
                    self.ledger.resume(job)
        elif k == "CONSTRAINT":
            self.constraints.add(a["tag"])
        elif k == "REQUIREMENT":
            self.requirements.add(a["tag"])
        elif k == "KEEP_JOB":
            self.ledger.protected.add(a["job"])
        elif k == "CONFIRM":
            self.yes_ms = self.t
            for job in self.ledger.live():
                if job.needs_yes:
                    job.confirmed = True
        elif k == "CANCEL":
            self._cancel_target(a["target"])
        elif k == "ANSWER":
            pend = self.pending_ask.pop(a["key"], None)
            if pend:
                u0, j0, it0 = pend
                self.cur_key, self.cur_utt = (u0.uid, j0), u0
                self._apply(it0, a.get("target"))
                self._mark(u0, j0)
                return
        elif k == "QUERY":
            self.query_t[a["topic"]] = self.cur_utt.t if self.cur_utt else self.t
        self.app.on_intent(self, it, target)

    # -- cancelling ---------------------------------------------------
    def _stop_job(self, job, force=False) -> Out:
        out = self.ledger.stop(job, self.t, force=force or self.policy.force_cancel)
        if out == Out.CANCELLED:
            self.wasted_ms += job.run_ms
            self.event("job_cancel", job=job.name, run_ms=job.run_ms)
        elif out == Out.DROPPED:
            self.event("job_drop", job=job.name)
        return out

    def _cancel_target(self, target: str):
        if target == "all":
            for job in list(self.ledger.live()):
                self._stop_job(job)
            return
        name = target.split(":", 1)[1]
        jobs = [j for j in self.ledger.jobs if j.name == name]
        if not jobs:
            self.say("Nothing to cancel.")
            return
        live = [j for j in jobs if j.live]
        job = live[-1] if live else jobs[-1]
        out = self._stop_job(job)
        if out == Out.DROPPED:
            self.say("OK, I will not do that step.")
        elif out == Out.CANCELLED:
            self.say("Stopped.")
        elif out == Out.PROTECTED:
            self.say("Keeping it running.")
        elif out == Out.TOO_LATE:
            self.say(f"Too late to stop {name.replace('_', ' ')}. This step will finish." if self.policy.truthful else "Stopped.")
        elif out == Out.DONE_REV:
            self.say("That is already done. I can undo it.")
        elif out == Out.DONE_IRREV:
            if self.policy.truthful:
                self.say("That is already done and cannot be undone. I can restore from the snapshot. Do you want that?")
                self.late_reports.append(self.t)
                ans = self.spec.truth.get("answers", {}).get("offer_restore")
                if ans:
                    self._schedule_reply("offer_restore", ans[0], ans[1], hands_on=False, after_words=18)
            else:
                self.say("Stopped.")

    # -- speech output ------------------------------------------------
    def _cut_speech(self, delay_ms: int, flush: bool):
        if flush:
            self.speech_q.clear()
        if self.speech_cur:
            end = min(self.speech_cur[1], self.t + delay_ms)
            if end < self.speech_cur[1]:
                self.speech_cur[1] = end
                self.event("speech_cut", at=end)

    def _user_speaking(self) -> bool:
        return any(a <= self.t < b for a, b in self.user_speech)

    def _step_speech(self):
        if not self.arm.voice_out:
            return
        if self.speech_cur and self.t >= self.speech_cur[1]:
            self.speech_log.append((self.speech_cur[0], self.speech_cur[1]))
            self.speech_cur = None
        if self.speech_cur is None and self.speech_q:
            if self.policy.listens and self.arm.vad and self._user_speaking():
                return  # wait politely until the user stops
            text = self.speech_q.pop(0)
            dur = len(text.split()) * self.P.tts_ms_per_word + 200
            self.speech_cur = [self.t, self.t + dur, text]
            self.event("say_start", text=text)

    # -- jobs ----------------------------------------------------------
    def _start_ready(self):
        p = self.policy
        for job in self.ledger.jobs:
            if job.state not in (St.PROPOSED, St.ANNOUNCED):
                continue
            if any(a.state in (St.CANCELLED, St.UNDONE) for a in job.after):
                self.ledger.stop(job, self.t)
                continue
            if not all(a.done for a in job.after):
                continue
            if job.edit and self.edit_hold and p.honour_hold:
                continue
            if job.needs_yes and p.confirm_irreversible and not job.confirmed:
                if not job.announced:
                    self.ledger.announce(job)
                    if job.announce:
                        self.say(job.announce)
                continue
            self.ledger.start(job, self.t)
            self.event("job_start", job=job.name)

    def _step_jobs(self):
        for job in list(self.ledger.jobs):
            if not job.running:
                continue
            job.run_ms += self.P.tick_ms
            if job.kind == "chg" and not job.committed and job.run_ms >= job.commit_ms:
                self._commit(job)
            if job.run_ms >= job.dur_ms:
                self.ledger.finish(job, self.t)
                self.event("job_done", job=job.name)
                if job.on_done:
                    job.on_done(self, job)
                self.app.on_job_done(self, job)

    def _commit(self, job):
        job.committed, job.t_commit = True, self.t
        self.event("job_commit", job=job.name, target=job.target)
        tr, why = self.spec.truth, []
        if job.edit:
            for a, b in tr.get("hold_windows", []):
                if a <= self.t <= b:
                    why.append("hold")
        if job.name in tr.get("requires_yes", []):
            yes = tr.get("yes_ms")
            if yes is None or self.t < yes:
                why.append("no_yes")
            obj = tr.get("objection_ms")
            if obj is not None and self.t >= obj:
                why.append("objected")
        if job.target and tr.get("target") and job.target != tr["target"]:
            why.append("wrong_target")
        if why:
            w = 1 if job.reversible else 3
            self.unwanted.append({"t": self.t, "job": job.name, "why": why, "w": w})
            self.event("unwanted", job=job.name, why=why)
        if job.on_commit:
            job.on_commit(self, job)

    # -- main loop ------------------------------------------------------
    def _quiescent(self) -> bool:
        if self.heap or self.inbox:
            return False
        if any(j.running for j in self.ledger.jobs):
            return False
        return not (self.speech_cur or self.speech_q)

    def run(self):
        for u in self.spec.utts:
            self.schedule_utt(u)
        for t, name, data in self.spec.sys_events:
            self.at(t, lambda n=name, d=data: self._sys(n, d))
        self.app.start(self)
        while self.t <= self.spec.end_ms:
            while self.heap and self.heap[0][0] <= self.t:
                _, _, fn = heapq.heappop(self.heap)
                fn()
            self._step_jobs()
            self._start_ready()
            self._step_speech()
            self._drain()
            self._start_ready()
            self.app.tick(self)
            if self._quiescent():
                break
            self.t += self.P.tick_ms
        if self.speech_cur:
            self.speech_log.append((self.speech_cur[0], self.speech_cur[1]))
            self.speech_cur = None
        return self

    def _sys(self, name, data):
        self.event("sys", name=name)
        self.app.on_sys(self, name, data)
