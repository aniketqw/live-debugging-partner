"""Handwritten confirmation and control expectations; no model is involved."""

import unittest

from vh.confirm import TEMPLATES, classify_confirm, classify_control, render
from vh.normalize import spoken_form


class ConfirmTests(unittest.TestCase):
    def test_classify_confirm_handwritten_cases(self):
        groups = {
            "yes": (
                "yes", "yeah okay", "Yep.", "HAAN", "han", "ha", "correct", "confirm",
                "confirmed", "right!", "ok", "okay", "sure", "yes okay", "yes, do it",
            ),
            "no": (
                "no", "Nope.", "nahi", "nahin", "cancel", "stop", "wrong", "incorrect",
                "dont", "don't", "don’t", "never", "okay no", "no cancel that",
                "yes, stop", "sure but never", "yes no",
            ),
            "other": (
                "", " ", "maybe", "yes 48", "no it is 4 8 2", "what", "certainly",
                "why", "yesterday", "nothing", "nope 11", "yes ١١", "…", "oh",
            ),
        }
        for outcome, phrases in groups.items():
            for text in phrases:
                with self.subTest(text=text):
                    self.assertEqual(classify_confirm(text), outcome)

    def test_classify_control_keeps_stop_speech_separate(self):
        cases = [
            ("Stop, that is enough.", {"stop_speech", "stop_job"}),
            ("Stop talking, don't cancel the lookup.", {"stop_speech", "protect"}),
            ("Don't kill it. Stop.", {"stop_speech", "protect"}),
            ("Stop talking.", {"stop_speech"}),
            ("Wait, stop that rollback.", {"hold", "stop_speech", "stop_job"}),
            ("Hold on.", {"hold"}),
            ("Keep it.", {"protect"}),
            ("Unstoppable checkout.", set()),
            ("debugging without cancel", set()),
            ("enough", {"stop_speech"}),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(classify_control(text), expected)

    def test_readback_is_built_from_service_and_exact_spoken_release(self):
        release = spoken_form("11", "release")
        text = render("READBACK_rollback_deployment", service="checkout-api", release=release)
        self.assertEqual(text, (
            "I will roll back staging checkout-api to release one one. "
            "Say yes to confirm or no to cancel."
        ))
        with self.assertRaises(KeyError):
            render("READBACK_rollback_deployment", service="checkout-api")

    def test_all_staging_templates_render_with_expected_fields(self):
        expected_keys = {
            "READBACK_rollback_deployment", "EXEC_OK", "EXEC_ERROR", "CANCELLED",
            "TOO_LATE", "REASK", "ABORT", "SUPERSEDED",
        }
        self.assertEqual(TEMPLATES.keys(), expected_keys)
        for key in expected_keys:
            with self.subTest(key=key):
                rendered = render(key, service="checkout-api", release="one zero", summary="verified state")
                self.assertTrue(rendered.strip())
                self.assertNotIn("{", rendered)
        with self.assertRaises(KeyError):
            render("EXEC_OK")
        with self.assertRaises(KeyError):
            render("NO_SUCH_TEMPLATE")
