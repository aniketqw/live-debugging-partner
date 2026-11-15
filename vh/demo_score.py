"""Compare recognized release digits to a fixed synthetic reference."""

import json
import re
from pathlib import Path

from vh.normalize import normalize
from vh.scenarios import SCENARIOS


_REQUIRED = ("scenario", "speaker_label", "browser", "lang", "transcript", "source", "consent")
_PSEUDONYM = re.compile(r"[A-Za-z][0-9]{0,2}")
_BROWSER = re.compile(r"[A-Za-z][A-Za-z0-9 ._+/-]{0,39}")
_LANGUAGE = re.compile(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}")


def _digits(text):
    return "".join(c for c in normalize(text)[0] if c.isascii() and c.isdigit())


def score(data: dict, path: Path, *, redact=lambda text: text) -> dict:
    if any(key not in data for key in _REQUIRED):
        raise ValueError("missing scoring field")
    key, label, browser, lang, text, source, consent = (data[k] for k in _REQUIRED)
    if (not all(isinstance(x, str) for x in (key, label, browser, lang, text, source))
            or key not in (*SCENARIOS, "free") or source not in ("speech", "typed")
            or type(consent) is not bool or len(text) > 1000
            or (label and not _PSEUDONYM.fullmatch(label))
            or not _BROWSER.fullmatch(browser) or not _LANGUAGE.fullmatch(lang)):
        raise ValueError("invalid scoring field")
    text.encode("utf-8")
    text = redact(text)
    reference = next((turn.say for turn in SCENARIOS[key].turns if "Roll back" in turn.say), "") if key in SCENARIOS else ""
    expected, heard = _digits(reference), _digits(text)
    exact = expected == heard if reference else None
    recorded = bool(source == "speech" and consent and reference and label and text.strip())
    if recorded:
        record = {"speaker_label": label, "browser": browser, "lang": lang, "reference": reference,
                  "transcript": text, "digit_exact": exact, "n_tokens": len(expected)}
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, separators=(",", ":")) + "\n")
    return {"recorded": recorded, "digit_exact": exact, "expected_digits": expected,
            "heard_digits": heard}
