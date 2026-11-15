"""A1 trace contract tests from Architecture sections 2 and 3."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from vh.trace import read_trace, trace_hash, validate_event, write_trace
from vh.types import ModelResponse, ToolCall


def event(stage="caller", kind="say", data=None, *, seq=0, t=0):
    return {
        "seq": seq,
        "t": t,
        "stage": stage,
        "kind": kind,
        "data": {"turn": 0, "text": "Check staging"} if data is None else data,
    }


class TraceTests(unittest.TestCase):
    def test_shared_model_types(self):
        call = ToolCall("call-1", "status", {})
        response = ModelResponse("", [call], {"latency_ms": 10})
        self.assertEqual((call.id, call.name, call.args), ("call-1", "status", {}))
        self.assertEqual((response.text, response.tool_calls, response.meta),
                         ("", [call], {"latency_ms": 10}))
        with self.assertRaises(FrozenInstanceError):
            call.name = "other"

    def test_rejects_missing_envelope_fields(self):
        for name in ("seq", "t", "stage", "kind", "data"):
            with self.subTest(field=name):
                record = event()
                del record[name]
                with self.assertRaisesRegex(ValueError, name):
                    validate_event(record)

    def test_all_event_kinds_require_the_documented_data_fields(self):
        cases = [
            ("call", "start", {"scenario": "test", "mode": "harness", "seed": 7,
                               "fault_p": 0, "catch_prob": 1, "model": "scripted"}),
            ("caller", "say", {"turn": 0, "text": "Check staging"}),
            ("asr", "out", {"turn": 0, "transcript": "Check staging", "faults": []}),
            ("norm", "out", {"turn": 0, "text": "Check staging", "spans": []}),
            ("model", "resp", {"text": "", "tool_calls": []}),
            ("tool", "exec", {"call_id": "call-1", "name": "status", "args": {},
                              "tool_kind": "ro", "ok": True, "result": {}}),
            ("tool", "error", {"call_id": "call-1", "name": "status", "args": {},
                               "reason": "simulated failure"}),
            ("gate", "readback", {"call_id": "call-1", "name": "rollback",
                                  "shown_args": {"release": "11"}, "text": "Release eleven?"}),
            ("gate", "yes", {"turn": 1, "transcript": "Yes"}),
            ("gate", "no", {"turn": 1, "transcript": "No"}),
            ("gate", "other", {"turn": 1, "transcript": "Wait"}),
            ("gate", "abort", {"call_id": "call-1", "reason": "cancelled"}),
            ("tts", "start", {"text": "Check staging", "start_ms": 0, "end_ms": 10}),
            ("tts", "cut", {"cut_ms": 5, "spoken_prefix": "Check", "n_words_spoken": 1}),
            ("ledger", "transition", {"job": 1, "name": "status", "from": "proposed",
                                       "to": "running_read_only", "out": None}),
            ("history", "assistant", {"content": "Check staging"}),
            ("call", "end", {"state_hash": "fixture", "success": True}),
        ]
        for stage, kind, data in cases:
            validate_event(event(stage, kind, data))
            for name in data:
                with self.subTest(stage=stage, kind=kind, field=name):
                    missing = {key: value for key, value in data.items() if key != name}
                    with self.assertRaisesRegex(ValueError, name):
                        validate_event(event(stage, kind, missing))

    def test_named_nested_records_require_lists_and_documented_fields(self):
        cases = [
            (event("asr", "out", {"turn": 0, "transcript": "10", "faults": []}),
             "faults", {"kind": "digit_sub", "index": 0, "before": "11", "after": "10"}),
            (event("norm", "out", {"turn": 0, "text": "11", "spans": []}),
             "spans", {"orig": "eleven", "value": "11", "start": 0, "end": 6}),
            (event("model", "resp", {"text": "", "tool_calls": []}),
             "tool_calls", {"id": "call-1", "name": "status", "args": {}}),
        ]
        for record, key, entry in cases:
            record["data"][key] = [entry]
            validate_event(record)
            malformed = [{}, [None], *[
                [{name: value for name, value in entry.items() if name != required}]
                for required in entry
            ]]
            for payload in malformed:
                with self.subTest(field=key, malformed=payload):
                    record["data"][key] = payload
                    with self.assertRaisesRegex(ValueError, key):
                        validate_event(record)

    def test_rejects_invalid_envelope_types_and_unknown_event(self):
        mutations = [
            {"seq": True}, {"seq": -1}, {"seq": 0.0}, {"t": False}, {"t": "0"},
            {"stage": []}, {"kind": "unknown"}, {"data": []}, {"meta": None},
        ]
        for fields in mutations:
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                validate_event({**event(), **fields})
        with self.assertRaises(ValueError):
            validate_event([])

    def test_sequence_must_start_at_zero_and_be_contiguous(self):
        traces = [
            [event(seq=1)],
            [event(seq=0), event(seq=0)],
            [event(seq=0), event(seq=2)],
            [event(seq=0), event(seq=2), event(seq=1)],
        ]
        valid_line = b'{"seq":0,"t":0,"stage":"caller","kind":"say","data":{"turn":0,"text":"Check staging"}}\n'
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            for trace in traces:
                with self.subTest(seq=[record["seq"] for record in trace]):
                    with self.assertRaisesRegex(ValueError, "seq"):
                        trace_hash(trace)
                    with self.assertRaisesRegex(ValueError, "seq"):
                        write_trace(path, trace)
                    path.write_bytes(b"".join(
                        valid_line.replace(b'"seq":0,', f'"seq":{record["seq"]},'.encode())
                        for record in trace
                    ))
                    with self.assertRaisesRegex(ValueError, "seq"):
                        read_trace(path)

    def test_hash_ignores_only_top_level_meta(self):
        plain = event(data={"turn": 0, "text": "Check staging", "meta": {"flag": False}})
        tagged = {**plain, "meta": {"latency_ms": 100, "raw": {"text": "different"}}}
        retagged = {**plain, "meta": {"latency_ms": 200}}
        self.assertEqual(trace_hash([plain]), trace_hash([tagged]))
        self.assertEqual(trace_hash([plain]), trace_hash([retagged]))
        nested_change = deepcopy(tagged)
        nested_change["data"]["meta"]["flag"] = True
        self.assertNotEqual(trace_hash([tagged]), trace_hash([nested_change]))

    def test_hash_ignores_object_key_order_but_keeps_data_and_event_order(self):
        first = event(data={"turn": 0, "text": "Check staging", "details": {"a": 1, "z": [2, 3]}})
        second = event(data={"turn": 1, "text": "Check again"}, seq=1, t=10)
        reordered = {"data": {"details": {"z": [2, 3], "a": 1}, "text": "Check staging", "turn": 0},
                     "kind": "say", "stage": "caller", "t": 0, "seq": 0}
        expected = trace_hash([first, second])
        self.assertEqual(expected, trace_hash([reordered, second]))
        changes = {"turn": 2, "text": "Check another service", "details": {"a": 1, "z": [3, 2]}}
        for key, value in changes.items():
            with self.subTest(key=key):
                changed = {**first, "data": {**first["data"], key: value}}
                self.assertNotEqual(expected, trace_hash([changed, second]))
        self.assertNotEqual(expected, trace_hash([{**second, "seq": 0}, {**first, "seq": 1}]))

    def test_hash_matches_manually_framed_canonical_json(self):
        records = [
            event(data={"turn": 0, "text": "caf\u00e9\nOK"}),
            event("call", "end", {"state_hash": "fixture", "success": True}, seq=1, t=10),
        ]
        canonical = (
            b'{"data":{"text":"caf\\u00e9\\nOK","turn":0},"kind":"say","seq":0,"stage":"caller","t":0}\n'
            b'{"data":{"state_hash":"fixture","success":true},"kind":"end","seq":1,"stage":"call","t":10}\n'
        )
        self.assertEqual(trace_hash(records), sha256(canonical).hexdigest())

    def test_round_trip_preserves_data_meta_and_jsonl_framing(self):
        records = [
            {**event(data={"text": "Check staging\nplease", "turn": 0}),
             "meta": {"raw": {"text": "caf\u00e9"}, "latency_ms": 10}},
            event("call", "end", {"state_hash": "fixture", "success": True}, seq=1, t=10),
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            write_trace(path, records)
            self.assertEqual(
                path.read_bytes(),
                b'{"data":{"text":"Check staging\\nplease","turn":0},"kind":"say",'
                b'"meta":{"latency_ms":10,"raw":{"text":"caf\\u00e9"}},"seq":0,"stage":"caller","t":0}\n'
                b'{"data":{"state_hash":"fixture","success":true},"kind":"end","seq":1,"stage":"call","t":10}\n',
            )
            self.assertEqual(read_trace(path), records)
            self.assertEqual(trace_hash(read_trace(path)), trace_hash(records))

    def test_empty_trace_round_trips(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            write_trace(path, [])
            self.assertEqual(path.read_bytes(), b"")
            self.assertEqual(read_trace(path), [])
            self.assertEqual(trace_hash([]), sha256(b"").hexdigest())

    def test_rejects_lossy_or_non_json_values_without_overwriting_file(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            original = b"keep this contents"
            path.write_bytes(original)
            for value in ({1: "non-string key"}, ("tuple",), float("nan"), float("inf")):
                record = event(data={"turn": 1, "text": "Check staging", "detail": value}, seq=1)
                with self.subTest(value=value):
                    with self.assertRaises(ValueError):
                        write_trace(path, [event(), record])
                    self.assertEqual(path.read_bytes(), original)

    def test_read_reports_line_for_invalid_json_or_duplicate_keys(self):
        first = b'{"seq":0,"t":0,"stage":"caller","kind":"say","data":{"turn":0,"text":"Check staging"}}\n'
        malformed_lines = [
            b"not json\n",
            b'{"seq":1,"t":0,"stage":"caller","kind":"say","data":{"turn":0,"turn":1,"text":"Check staging"}}\n',
        ]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            for malformed in malformed_lines:
                with self.subTest(line=malformed):
                    path.write_bytes(first + malformed)
                    with self.assertRaisesRegex(ValueError, "line 2"):
                        read_trace(path)

    def test_rejects_surrogate_code_points_in_values_and_object_keys(self):
        for invalid in ("\ud83d\ude80", "\ud83d"):
            for detail in (invalid, {invalid: "invalid key"}):
                with self.subTest(detail=repr(detail)):
                    record = event(data={"turn": 0, "text": "Check staging", "detail": detail})
                    with self.assertRaisesRegex(ValueError, "Unicode"):
                        validate_event(record)
                    with self.assertRaisesRegex(ValueError, "Unicode"):
                        trace_hash([record])
                    with TemporaryDirectory() as directory:
                        path = Path(directory) / "trace.jsonl"
                        with self.assertRaisesRegex(ValueError, "Unicode"):
                            write_trace(path, [record])
                        self.assertFalse(path.exists())

    def test_round_trip_preserves_non_bmp_unicode_scalars(self):
        records = [event(data={"turn": 0, "text": "Ready \U0001f680", "\U0001f680": True})]
        with TemporaryDirectory() as directory:
            path = Path(directory) / "trace.jsonl"
            write_trace(path, records)
            self.assertEqual(read_trace(path), records)


if __name__ == "__main__":
    unittest.main()
