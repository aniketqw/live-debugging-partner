"""Validate, persist, and hash simulated voice harness event traces."""

from collections.abc import Iterable, Iterator
from hashlib import sha256
import json
from math import isfinite
from pathlib import Path


_EVENT_FIELDS = ("seq", "t", "stage", "kind", "data")
_REQUIRED_DATA = {
    ("call", "start"): ("scenario", "mode", "seed", "fault_p", "catch_prob", "model"),
    ("caller", "say"): ("turn", "text"),
    ("asr", "out"): ("turn", "transcript", "faults"),
    ("norm", "out"): ("turn", "text", "spans"),
    ("model", "resp"): ("text", "tool_calls"),
    ("tool", "exec"): ("call_id", "name", "args", "tool_kind", "ok", "result"),
    ("tool", "error"): ("call_id", "name", "args", "reason"),
    ("gate", "readback"): ("call_id", "name", "shown_args", "text"),
    ("gate", "yes"): ("turn", "transcript"),
    ("gate", "no"): ("turn", "transcript"),
    ("gate", "other"): ("turn", "transcript"),
    ("gate", "abort"): ("call_id", "reason"),
    ("tts", "start"): ("text", "start_ms", "end_ms"),
    ("tts", "cut"): ("cut_ms", "spoken_prefix", "n_words_spoken"),
    ("ledger", "transition"): ("job", "name", "from", "to", "out"),
    ("history", "assistant"): ("content",),
    ("call", "end"): ("state_hash", "success"),
}
_NESTED_RECORDS = {
    ("asr", "out"): ("faults", ("kind", "index", "before", "after")),
    ("norm", "out"): ("spans", ("orig", "value", "start", "end")),
    ("model", "resp"): ("tool_calls", ("id", "name", "args")),
}


def _require_fields(record: object, fields: tuple[str, ...], label: str) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{label} must be a JSON object")
    missing = [field for field in fields if field not in record]
    if missing:
        raise ValueError(f"{label} missing field(s): {', '.join(missing)}")


def _validate_string(value: str) -> None:
    # JSON escapes for adjacent surrogate code points decode as a single
    # scalar, so accepting such strings would collapse distinct trace values.
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("JSON strings must contain valid Unicode scalar values") from None


def _validate_json(value: object) -> None:
    # json.dumps accepts tuples and coerces certain object keys; a trace must
    # preserve its JSON values through a write/read round trip.
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError("JSON object keys must be strings")
            _validate_string(key)
            _validate_json(item)
    elif isinstance(value, list):
        for item in value:
            _validate_json(item)
    elif isinstance(value, float):
        if not isfinite(value):
            raise ValueError("JSON numbers must be finite")
    elif isinstance(value, str):
        _validate_string(value)
    elif value is not None and not isinstance(value, (int, bool)):
        raise ValueError("trace values must be JSON objects, arrays, or scalars")


def validate_event(event: dict) -> None:
    """Raise ValueError if an event does not match the documented shape."""
    _require_fields(event, _EVENT_FIELDS, "event")
    if type(event["seq"]) is not int or event["seq"] < 0:
        raise ValueError("seq must be a nonnegative integer")
    if type(event["t"]) is not int:
        raise ValueError("t must be an integer simulated timestamp")
    stage, kind = event["stage"], event["kind"]
    if not isinstance(stage, str) or not isinstance(kind, str):
        raise ValueError("stage and kind must be strings")
    event_kind = (stage, kind)
    if event_kind not in _REQUIRED_DATA:
        raise ValueError("unknown stage.kind pair")
    data = event["data"]
    _require_fields(data, _REQUIRED_DATA[event_kind], f"{stage}.{kind} data")
    if "meta" in event:
        _require_fields(event["meta"], (), "meta")
    if event_kind in _NESTED_RECORDS:
        name, fields = _NESTED_RECORDS[event_kind]
        if not isinstance(data[name], list):
            raise ValueError(f"{name} must be a JSON array")
        for index, entry in enumerate(data[name]):
            _require_fields(entry, fields, f"{name}[{index}]")
    _validate_json(event)


def _validate_record(event: dict, index: int) -> None:
    validate_event(event)
    if event["seq"] != index:
        raise ValueError(f"expected seq {index}, got {event['seq']}")


def _lines(trace: Iterable[dict], *, include_meta: bool) -> Iterator[str]:
    for index, event in enumerate(trace):
        _validate_record(event, index)
        if not include_meta:
            event = {key: value for key, value in event.items() if key != "meta"}
        yield json.dumps(event, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=True, allow_nan=False) + "\n"


def trace_hash(trace: Iterable[dict]) -> str:
    """Return the SHA-256 hex digest of canonical JSONL without top-level meta."""
    digest = sha256()
    for line in _lines(trace, include_meta=False):
        digest.update(line.encode("utf-8"))
    return digest.hexdigest()


def write_trace(path: str | Path, trace: Iterable[dict]) -> None:
    """Write canonical JSONL, including any metadata, after validating the trace."""
    contents = "".join(_lines(trace, include_meta=True))
    with Path(path).open("w", encoding="utf-8", newline="\n") as file:
        file.write(contents)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def read_trace(path: str | Path) -> list[dict]:
    """Read JSONL in file order, rejecting malformed records and sequences."""
    trace = []
    with Path(path).open(encoding="utf-8") as file:
        for index, line in enumerate(file):
            try:
                event = json.loads(line, object_pairs_hook=_unique_object)
                _validate_record(event, index)
            except ValueError as exc:
                raise ValueError(f"invalid trace at line {index + 1}: {exc}") from exc
            trace.append(event)
    return trace
