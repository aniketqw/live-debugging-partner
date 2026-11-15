"""Unit fixtures are stripped of ASR ground truth unless testing the guard."""

import unittest

from vh.attribution import attribute


def ev(seq, t, s, k, **data):
    return {"seq": seq, "t": t, "stage": s, "kind": k, "data": data}


class AttributionTests(unittest.TestCase):
    def test_rejects_hidden_fault_field_even_if_empty(self):
        for hidden in ([], [{"kind": "synthetic"}]):
            with self.assertRaises(ValueError):
                attribute([ev(0, 0, "asr", "out", transcript="all good", faults=hidden)])

    def test_tool_error_has_priority(self):
        trace = [
            ev(0, 0, "model", "resp", tool_calls=[{"args": {"release": "99"}}]),
            ev(1, 1, "tool", "error", reason="timeout"),
        ]
        self.assertEqual(attribute(trace), {"stage": "TOOL", "evidence": [1]})

    def test_speech_truncation_requires_absence_of_caller_barge_in(self):
        trace = [
            ev(0, 0, "tts", "start", start_ms=0, end_ms=300, template="READBACK", text="I say one"),
            ev(1, 40, "tts", "cut", cut_ms=40, spoken_prefix="I"),
        ]
        self.assertEqual(attribute(trace), {"stage": "TTS", "evidence": [0, 1]})
        trace.append(ev(2, 40, "caller", "say", text="stop"))
        self.assertEqual(attribute(trace), {"stage": "NONE", "evidence": []})

    def test_disagreement_between_heard_release_and_model_args(self):
        trace = [
            ev(0, 0, "asr", "out", transcript="Staging checkout-api release eleven"),
            ev(1, 0, "model", "resp", tool_calls=[{"args": {"service": "checkout-api", "release": "10"}}]),
        ]
        self.assertEqual(attribute(trace), {"stage": "AGENT", "evidence": [0, 1]})

    def test_rejected_readback_can_suggest_asr_but_is_not_proof(self):
        trace = [
            ev(0, 0, "norm", "out", text="Staging checkout-api release 10"),
            ev(1, 0, "gate", "readback", shown_args={"service": "checkout-api", "release": "10"}),
            ev(2, 20, "norm", "out", text="No, release 11"),
            ev(3, 20, "gate", "other", transcript="No, release 11"),
        ]
        self.assertEqual(attribute(trace), {"stage": "ASR", "evidence": [1, 3]})
        self.assertEqual(attribute(trace[:3]), {"stage": "NONE", "evidence": []})
