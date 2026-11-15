"""Independent behavior tests for staged scripted models and prompt contrast."""

from pathlib import Path
import unittest

from vh.agents.scripted import (
    DoubleCallModel, FalseSuccessModel, NoConfirmModel, OracleModel,
    ReadbackLiarModel, WrongArgModel,
)


_PROMPTS = Path(__file__).resolve().parents[1] / "vh/prompts"
_REQUEST = {"role": "user", "content": "Roll back staging checkout-api to release one one."}
_EXPECTED = {"service": "checkout-api", "release": "11"}


class ModelTests(unittest.TestCase):
    def test_prompt_only_adds_one_confirmation_paragraph(self):
        base = (_PROMPTS / "agent_system.txt").read_text()
        contrast = (_PROMPTS / "agent_system_prompt_only.txt").read_text()
        self.assertTrue(contrast.startswith(base))
        extra = contrast[len(base):].strip()
        self.assertTrue(extra)
        self.assertNotIn("\n", extra)
        self.assertIn("read back", extra.lower())
        self.assertIn("wait", extra.lower())
        self.assertIn("confirm", extra.lower())

    def test_oracle_reads_status_and_proposes_exact_unambiguous_release(self):
        model = OracleModel()
        request = model.respond([_REQUEST], [])
        self.assertEqual([(c.name, c.args) for c in request.tool_calls],
                         [("rollback_deployment", _EXPECTED)])
        self.assertEqual(request, model.respond([_REQUEST], []))
        status = model.respond([{"role": "user", "content": "Check staging checkout-api status."}], [])
        self.assertEqual([(c.name, c.args) for c in status.tool_calls],
                         [("get_deployment_status", {"service": "checkout-api"})])
        for ambiguous in ("eleven and ten", "eleven hundred", "-11", "11.2", "one"):
            with self.subTest(release=ambiguous):
                self.assertEqual(model.respond([{"role": "user",
                                                 "content": f"Rollback staging checkout-api to release {ambiguous}."}],
                                               []).tool_calls, [])

    def test_oracle_prompt_only_waits_for_yes_after_readback(self):
        prompt = {"role": "system", "content": (_PROMPTS / "agent_system_prompt_only.txt").read_text()}
        model = OracleModel()
        waiting = model.respond([prompt, _REQUEST], [])
        self.assertEqual(waiting.tool_calls, [])
        self.assertIn("release one one", waiting.text)
        heard = {"role": "assistant", "content": waiting.text}
        yes = {"role": "user", "content": "yes"}
        approved = model.respond([prompt, _REQUEST, heard, yes], [])
        self.assertEqual([c.args for c in approved.tool_calls], [_EXPECTED])
        self.assertEqual(model.respond([prompt, _REQUEST, yes], []).tool_calls, [])

    def test_no_confirm_skips_readback(self):
        response = NoConfirmModel().respond([_REQUEST], [])
        self.assertEqual([c.args for c in response.tool_calls], [_EXPECTED])
        self.assertEqual(response.text, "")

    def test_wrong_argument_is_another_valid_target(self):
        response = WrongArgModel().respond([_REQUEST], [])
        self.assertEqual([c.args for c in response.tool_calls],
                         [{"service": "checkout-api", "release": "10"}])

    def test_double_call_repeats_same_identity(self):
        first, second = DoubleCallModel().respond([_REQUEST], []).tool_calls
        self.assertEqual(first, second)
        self.assertEqual(first.args, _EXPECTED)

    def test_liar_readback_disagrees_with_its_actual_tool_call(self):
        response = ReadbackLiarModel().respond([_REQUEST], [])
        self.assertIn("release one zero", response.text)
        self.assertEqual([c.args for c in response.tool_calls], [_EXPECTED])

    def test_false_success_claims_done_even_after_error(self):
        model = FalseSuccessModel()
        tool_error = {"role": "tool", "content": '{"ok":false,"error":"timeout"}'}
        reply = model.respond([_REQUEST, tool_error], [])
        self.assertEqual(reply.tool_calls, [])
        self.assertEqual(reply.text, "Done, the rollback is complete.")
        self.assertTrue(model.respond([_REQUEST], []).text.startswith("Done"))
