"""Data model: parameters, meanings (intents), utterances and session specs."""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple


@dataclass
class Params:
    """Timing assumptions. All values are guesses and can be swept."""
    tick_ms: int = 100
    speak_ms_per_word: int = 400      # user speech, about 150 words per minute
    tts_ms_per_word: int = 400        # agent speech
    type_ms_per_word: int = 1200      # typing, about 50 words per minute
    send_ms: int = 800                # press send, message arrives
    switch_ms: int = 1500             # leave the app to type (only when hands are on the app)
    typed_ratio: float = 0.6          # a typed message is shorter than the spoken one
    vad_lag_ms: int = 150             # speech onset detected
    stream_lag_ms: int = 300          # partial transcript lag (interactive voice)
    final_lag_ms: int = 400           # final transcript lag (interactive voice)
    asr_lag_ms: int = 700             # final transcript lag (basic voice)
    barge_cut_ms: int = 250           # agent needs this long to stop talking
    reply_delay_ms: int = 1500        # user answers a question after this delay
    oracle: bool = False              # zero lags: used to prove a session can be solved


@dataclass
class Ref:
    """A reference to something on screen."""
    kind: str            # "deictic" ("this one") or "relative" ("the one above it")
    word: int = 0        # deictic: index of the pointing word inside the segment
    base: int = 0        # relative: segment whose target is the starting point
    rel: int = 0         # relative: -1 means the item above


@dataclass
class Intent:
    """What the user means. The scripted language understanding returns these."""
    kind: str
    args: dict = field(default_factory=dict)
    ref: Optional[Ref] = None


@dataclass
class Part:
    text: str
    intent: Optional[Intent] = None
    replaces: Optional[int] = None   # index of an earlier part this part corrects
    marker: bool = False             # a correction cue such as "no wait"
    typed_ref: Optional[Ref] = None  # how the reference reads in a typed message


@dataclass
class Segment:
    w0: int
    w1: int
    intent: Optional[Intent]
    replaces: Optional[int]
    marker: bool
    typed_ref: Optional[Ref]


@dataclass
class Utterance:
    uid: str
    t: int                                   # absolute start time, ms
    words: List[Tuple[str, int, int]]        # (word, start, end), relative to t
    segs: List[Segment]
    typed_words: int
    hands_on: bool = False                   # the user is operating the app
    correction: bool = False                 # changes what the agent already does
    must_apply: bool = False                 # the user repeats it if nothing happens
    patience_ms: int = 6000
    dup_of: Optional[str] = None

    @property
    def dur_ms(self) -> int:
        return self.words[-1][2]

    @property
    def text(self) -> str:
        return " ".join(w[0] for w in self.words)

    def word_time(self, i: int) -> int:
        return self.t + self.words[i][1]

    def seg_end(self, j: int) -> int:
        return self.t + self.words[self.segs[j].w1 - 1][2]

    def final_idx(self) -> List[int]:
        """Segments that still count after self-corrections."""
        replaced = {s.replaces for s in self.segs if s.replaces is not None}
        return [j for j, s in enumerate(self.segs)
                if s.intent is not None and not s.marker and j not in replaced]


def make_utt(uid, t, parts, speed=1.0, hands_on=False, correction=False,
             must_apply=False, patience_ms=6000, params: Params = None) -> Utterance:
    P = params or Params()
    rng = random.Random(uid)
    words, segs, clock = [], [], 0
    for part in parts:
        w0 = len(words)
        for tok in part.text.split():
            d = int(P.speak_ms_per_word * speed * rng.uniform(0.85, 1.15))
            words.append((tok, clock, clock + d))
            clock += d
        clock += 200  # short pause between parts
        segs.append(Segment(w0, len(words), part.intent, part.replaces, part.marker, part.typed_ref))
    replaced = {p.replaces for p in parts if p.replaces is not None}
    content = sum(len(p.text.split()) for i, p in enumerate(parts) if not p.marker and i not in replaced)
    typed = max(1, round(P.typed_ratio * content))
    return Utterance(uid, int(t), words, segs, typed, hands_on, correction, must_apply, patience_ms)


@dataclass
class SessionSpec:
    sid: str
    variant: int
    utts: List[Utterance]
    selection: List[Tuple[int, str]]            # (time, selected item)
    sys_events: List[Tuple[int, str, dict]]
    app_factory: Callable
    end_ms: int
    truth: dict = field(default_factory=dict)   # hidden ground truth used for scoring

    def selection_at(self, t: int) -> Optional[str]:
        cur = None
        for ts, item in self.selection:
            if ts <= t:
                cur = item
        return cur
