"""The four interaction arms. Only the input path differs; app and executor are the same."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Arm:
    name: str
    voice_in: bool    # the user speaks
    voice_out: bool   # the agent speaks (talk-over is possible)
    queue: bool       # a message reaches the agent only when its turn is over
    vad: bool         # speech onset is seen at once (barge-in)
    stream: bool      # partial transcripts and correction cues arrive while the user speaks
    bind: str         # screen reference: "send" (selection at send time), "word", "none"


TEXT = Arm("text", False, False, True, False, False, "send")
TEXT_INTERRUPT = Arm("text_interrupt", False, False, False, False, False, "send")
BASIC_VOICE = Arm("basic_voice", True, True, True, False, False, "none")
INTERACTIVE = Arm("interactive_voice", True, True, False, True, True, "word")
# Same as interactive voice with every lag set to zero. Used to prove a session can be solved.
ORACLE = Arm("oracle", True, True, False, True, True, "word")

ARMS = {a.name: a for a in (TEXT, TEXT_INTERRUPT, BASIC_VOICE, INTERACTIVE, ORACLE)}
GRID_ARMS = ["text", "text_interrupt", "basic_voice", "interactive_voice"]
