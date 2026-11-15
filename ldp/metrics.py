"""The eight measures (SESSIONS.md section 6), computed from the engine's event log."""
from __future__ import annotations

from typing import Dict, List


def overlap_ms(a: List[tuple], b: List[tuple]) -> int:
    total = 0
    for s0, s1 in a:
        for u0, u1 in b:
            total += max(0, min(s1, u1) - max(s0, u0))
    return total


def compute(e) -> Dict:
    spec = e.spec
    checks = e.app.finalize(e)                      # list of (name, kind, passed)
    task = [c for c in checks if c[1] == "task"]
    intent = [c for c in checks if c[1] == "intent"]
    extra = e.app.extra_waste_ms(e) if hasattr(e.app, "extra_waste_ms") else 0
    rec = []
    for u in spec.utts:
        if u.correction:
            done = e.applied.get(u.uid)
            rec.append(((done if done is not None else e.t) - u.t))
    ans = []
    for topic, tq in e.query_t.items():
        ans.append((e.answer_t.get(topic, e.t) - tq))
    out = {
        "completion": float(all(c[2] for c in task)),
        "task_frac": sum(c[2] for c in task) / max(1, len(task)),
        "latest_intent": float(all(c[2] for c in intent)),
        "intent_frac": sum(c[2] for c in intent) / max(1, len(intent)),
        "unwanted_n": len(e.unwanted),
        "unwanted_w": sum(x["w"] for x in e.unwanted),
        "recovery_s": (sum(rec) / len(rec) / 1000) if rec else None,
        "wasted_s": (e.wasted_ms + extra) / 1000,
        "talk_over_s": overlap_ms(e.speech_log, e.user_speech) / 1000 if e.arm.voice_out else 0.0,
        "words": e.words_in,
        "repeats": e.repeats,
        "asks": e.asks,
        "input_s": e.input_ms / 1000,
        "off_app_s": e.off_app_ms / 1000,
        "compute_s": sum(j.run_ms for j in e.ledger.jobs) / 1000,
        "agent_words": e.agent_words,
        "answer_delay_s": (sum(ans) / len(ans) / 1000) if ans else None,
        "checks": {c[0]: bool(c[2]) for c in checks},
        "check_kind": {c[0]: c[1] for c in checks},
    }
    return out
