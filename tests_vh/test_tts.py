"""Simulated word boundaries are anchored to the injected clock."""

import unittest

from ldp.model import Params
from vh.tts import MockTTS


class SpeechTests(unittest.TestCase):
    def test_words_follow_the_imported_parameter(self):
        tts = MockTTS(Params(tts_ms_per_word=73))
        self.assertEqual(tts.speak("rollback staging now", 30), (
            249, [("rollback", 30, 103), ("staging", 103, 176), ("now", 176, 249)],
        ))

    def test_cut_only_counts_completed_words(self):
        tts = MockTTS(Params())
        end, spans = tts.speak("Rollback staging now.", 20)
        for t, expected in (
            (19, ("", 0)), (20, ("", 0)), (419, ("", 0)),
            (420, ("Rollback", 1)), (619, ("Rollback", 1)),
            (820, ("Rollback staging", 2)), (end, ("Rollback staging now.", 3)),
            (end + 1, ("Rollback staging now.", 3)),
        ):
            with self.subTest(t=t):
                self.assertEqual(tts.cut(spans, t), expected)
        self.assertEqual(tts.cut(spans, 619), tts.cut(spans, 619))

    def test_empty_speech_spends_no_simulated_time(self):
        tts = MockTTS(Params())
        self.assertEqual(tts.speak(" \t", 100), (100, []))
        self.assertEqual(tts.cut([], 130), ("", 0))
