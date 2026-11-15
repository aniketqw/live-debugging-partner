"""A trace-only failure heuristic. Injected ground truth must be removed first."""

from vh.normalize import normalize


def _pair(event):
    return event["stage"], event["kind"]


def _compact(text: str) -> str:
    return "".join(normalize(text.lower())[0].split())


def _contains(text: str, args: dict) -> bool:
    return all("".join(str(value).lower().split()) in text for value in args.values())


def _verdict(stage, *events):
    return {"stage": stage, "evidence": [event["seq"] for event in events]}


def attribute(trace: list[dict]) -> dict:
    for e in trace:
        if _pair(e) == ("asr", "out") and "faults" in e["data"]:
            raise ValueError("attribution requires removal of injected fault labels")
    for e in trace:
        if _pair(e) == ("tool", "error") or (
            _pair(e) == ("tool", "exec") and e["data"].get("ok") is False
        ):
            return _verdict("TOOL", e)

    caller_times = [e["t"] for e in trace if _pair(e) == ("caller", "say")]
    speech = None
    for e in trace:
        if _pair(e) == ("tts", "start"):
            speech = e
        elif _pair(e) == ("tts", "cut") and speech:
            start = speech["data"]
            cut = e["data"]
            if (start.get("template") == "READBACK"
                    and len(cut["spoken_prefix"].split()) < len(start["text"].split())
                    and not any(start["start_ms"] < t <= cut["cut_ms"] for t in caller_times)):
                return _verdict("TTS", speech, e)
            speech = None

    heard = []
    suspicious = None
    for e in trace:
        pair, data = _pair(e), e["data"]
        if pair == ("asr", "out"):
            heard.append((e, _compact(data["transcript"])))
        elif pair == ("norm", "out"):
            normalized = (e, _compact(data["text"]))
            if heard and _pair(heard[-1][0]) == ("asr", "out"):
                heard[-1] = normalized
            else:
                heard.append(normalized)
        recent = " ".join(text for _, text in heard[-2:])
        if pair == ("model", "resp"):
            for call in data["tool_calls"]:
                if not _contains(recent, call["args"]):
                    if heard:
                        return _verdict("AGENT", heard[-1][0], e)
                    return _verdict("AGENT", e)
        elif pair == ("gate", "readback"):
            suspicious = e if _contains(recent, data["shown_args"]) else None
        elif pair in (("gate", "no"), ("gate", "other")) and suspicious:
            return _verdict("ASR", suspicious, e)
        elif pair in (("gate", "yes"), ("gate", "abort")):
            suspicious = None
    return _verdict("NONE")
