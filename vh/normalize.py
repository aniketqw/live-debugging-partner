"""Small deterministic spoken-number grammar for synthetic release identifiers."""

import re


_DIGIT_WORDS = "zero one two three four five six seven eight nine".split()
_DIGITS = {word: str(index) for index, word in enumerate(_DIGIT_WORDS)}
_DIGITS.update({str(index): str(index) for index in range(10)})
_TEENS = {word: str(index) for index, word in enumerate(
    "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split(), 10)}
_TENS = {word: str(index * 10) for index, word in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split(), 2)}
_REPEAT = {"double": 2, "triple": 3}
_OUTSIDE = {"hundred", "thousand", "lakh", "crore", "sau", "hazaar", "point"}
_TOKEN = re.compile(r"\w+(?:-\w+)*")


def _literal(token: str) -> bool:
    return token.isascii() and token.isdigit()


def _hyphenated(word: str) -> str | None:
    tens, sep, units = word.partition("-")
    if sep and tens in _TENS and _DIGITS.get(units) not in (None, "0"):
        return _TENS[tens][0] + _DIGITS[units]
    return None


def _numeric(word: str) -> bool:
    return (word in _DIGITS or word in _TEENS or word in _TENS or word in _REPEAT
            or word in _OUTSIDE or word == "oh" or _literal(word)
            or _hyphenated(word) is not None)


def _parse(words: list[str]) -> str | None:
    if len(words) == 1:
        token = words[0]
        if _literal(token):
            return token
        return _TEENS.get(token) or _TENS.get(token) or _DIGITS.get(token) or _hyphenated(token)
    if len(words) == 2 and words[0] in _TENS and _DIGITS.get(words[1]) not in (None, "0"):
        return _TENS[words[0]][0] + _DIGITS[words[1]]
    result = []
    index = 0
    while index < len(words):
        token = words[index]
        repeats = _REPEAT.get(token, 1)
        if token in _REPEAT:
            index += 1
            if index == len(words):
                return None
            token = words[index]
        digit = "0" if token == "oh" else _DIGITS.get(token)
        if digit is None:
            return None
        result.append(digit * repeats)
        index += 1
    return "".join(result)


def normalize(text: str) -> tuple[str, list[dict]]:
    """Normalize supported runs; preserve punctuation, spacing and unparsed spans."""
    tokens = list(_TOKEN.finditer(text))
    pieces: list[str] = []
    spans: list[dict] = []
    cursor = index = 0
    while index < len(tokens):
        word = tokens[index].group().lower()
        if not _numeric(word):
            index += 1
            continue
        start = tokens[index].start()
        end = tokens[index].end()
        words = [word]
        index += 1
        while index < len(tokens) and text[end:tokens[index].start()].isspace():
            candidate = tokens[index].group().lower()
            joins_magnitude = candidate == "and" and any(word in _OUTSIDE for word in words)
            if not _numeric(candidate) and not joins_magnitude:
                break
            words.append(candidate)
            end = tokens[index].end()
            index += 1
        original = text[start:end]
        value = _parse(words)
        pieces.append(text[cursor:start])
        pieces.append(original if value is None else value)
        spans.append({"orig": original, "value": value, "start": start, "end": end})
        cursor = end
    pieces.append(text[cursor:])
    return "".join(pieces), spans


def spoken_form(value: str, kind: str) -> str:
    """Speak a release identifier digit by digit, including leading zeroes."""
    if kind != "release" or not isinstance(value, str) or len(value) != 2 or not _literal(value):
        raise ValueError("expected a two-digit release identifier")
    return " ".join(_DIGIT_WORDS[int(char)] for char in value)


def despeak(spoken: str, kind: str) -> str:
    """Invert the canonical digit-by-digit release read-back."""
    words = spoken.split()
    if kind != "release" or len(words) != 2 or any(word not in _DIGIT_WORDS for word in words):
        raise ValueError("expected two spoken release digits")
    return "".join(_DIGITS[word] for word in words)
