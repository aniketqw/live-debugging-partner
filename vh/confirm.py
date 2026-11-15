"""Confirm and control vocabulary, plus code-owned staging speech templates."""

import re


_YES = frozenset("yes yeah yep haan han ha correct confirm confirmed right ok okay sure".split())
_NO = frozenset("no nope nahi nahin cancel stop wrong incorrect dont don't never".split())
_TOKENS = re.compile(r"[^\W_]+(?:'[^\W_]+)*")


def _tokens(text: str) -> list[str]:
    return _TOKENS.findall(text.lower().replace("’", "'"))


def classify_confirm(norm_text: str) -> str:
    if any(char.isdigit() for char in norm_text):
        return "other"
    tokens = set(_tokens(norm_text))
    if tokens & _NO:
        return "no"
    if "not" in tokens:
        return "other"
    if tokens & _YES:
        return "yes"
    return "other"


def classify_control(text: str) -> set[str]:
    tokens = _tokens(text)
    phrase = " " + " ".join(tokens) + " "
    protect = any(form in phrase for form in (
        " dont cancel ", " don't cancel ", " dont kill ", " don't kill ", " keep it ",
    ))
    stops_speech_only = " stop talking " in phrase
    controls = set()
    if protect:
        controls.add("protect")
    if stops_speech_only or "enough" in tokens or "stop" in tokens:
        controls.add("stop_speech")
    if "stop" in tokens and not stops_speech_only and not protect:
        controls.add("stop_job")
    if "wait" in tokens or " hold on " in phrase:
        controls.add("hold")
    return controls


TEMPLATES = {
    "READBACK_rollback_deployment": (
        "I will roll back staging {service} to release {release}. Say yes to confirm or no to cancel."
    ),
    "EXEC_OK": "Done. {summary}.",
    "EXEC_ERROR": "That did not go through. Nothing was changed. Do you want to try again?",
    "CANCELLED": "Okay, I cancelled it. Nothing was changed.",
    "TOO_LATE": "That change has already committed. {summary}.",
    "REASK": "Sorry, I need a clear yes or no. ",
    "ABORT": "I could not get a clear answer, so I did not do it.",
    "SUPERSEDED": "Okay, I dropped the earlier request.",
}


def render(template_key: str, **values) -> str:
    return TEMPLATES[template_key].format(**values)
