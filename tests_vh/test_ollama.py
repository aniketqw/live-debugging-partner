"""Ollama request and cache contracts using only local synthetic responses."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.error import URLError

from vh.agents.ollama import CacheMiss, OllamaModel, RequestBudget
from vh.runtime import run_call
from vh.scenarios import SCENARIOS
from vh.tools import tool_schemas
from vh.trace import trace_hash, write_trace


_MESSAGES = [{"role": "user", "content": "Check staging"}]
_SAMPLE = {"message": {"role": "assistant", "content": "Checking.", "tool_calls": [
    {"function": {"name": "get_deployment_status", "arguments": {"service": "checkout-api"}}},
    {"function": {"name": "rollback_deployment",
                  "arguments": '{"service":"checkout-api","release":"11"}'}},
]}, "done": True, "eval_count": 3}
_MODEL = "llama3.1:latest"


class OllamaTests(unittest.TestCase):
    def setUp(self):
        scratch = TemporaryDirectory()
        self.addCleanup(scratch.cleanup)
        self.root = Path(scratch.name)

    def test_native_request_and_two_argument_shapes(self):
        recorded = []

        def fake(request, timeout):
            recorded.append((request.full_url, json.loads(request.data), request.get_header("Authorization")))
            return _SAMPLE

        adapter = OllamaModel(_MODEL, cache_dir=self.root, request_mode="live", transport=fake, seed=7)
        result = adapter.respond(_MESSAGES, tool_schemas())
        self.assertEqual(result.text, "Checking.")
        self.assertEqual([call.args for call in result.tool_calls], [
            {"service": "checkout-api"}, {"service": "checkout-api", "release": "11"},
        ])
        self.assertEqual(len({call.id for call in result.tool_calls}), 2)
        self.assertEqual(result.tool_calls, adapter.respond(_MESSAGES, tool_schemas()).tool_calls)
        url, payload, auth = recorded[0]
        self.assertTrue(url.endswith("/api/chat"))
        self.assertEqual(payload, {"model": _MODEL, "messages": _MESSAGES,
                                   "tools": tool_schemas(), "stream": False,
                                   "options": {"temperature": 0, "seed": 7}})
        self.assertIsNone(auth)

    def test_cache_key_ignores_object_key_order_and_auto_replays(self):
        model = OllamaModel(_MODEL, cache_dir=self.root, request_mode="auto", transport=lambda *_: _SAMPLE)
        a = [{"role": "user", "content": "Check staging"}]
        b = [{"content": "Check staging", "role": "user"}]
        self.assertEqual(model.cache_key(a, []), model.cache_key(b, []))
        self.assertNotEqual(model.cache_key(a, []), model.cache_key(a, tool_schemas()))
        self.assertEqual(model.respond(a, []).meta["source"], "live")
        self.assertEqual(model.respond(b, []).meta["source"], "replay")
        self.assertEqual(model.budget.used, 1)
        self.assertEqual(len(list(self.root.glob("*.json"))), 1)

    def test_replay_miss_never_calls_transport(self):
        def forbid(*_):
            self.fail("cache miss made a transport request")
        model = OllamaModel(_MODEL, cache_dir=self.root, transport=forbid)
        with self.assertRaises(CacheMiss):
            model.respond(_MESSAGES, [])
        self.assertEqual(model.budget.used, 0)

    def test_every_retry_consumes_the_hard_request_budget(self):
        calls = []

        def intermittently(request, timeout):
            calls.append(request)
            if len(calls) <= 2:
                raise URLError("synthetic failure")
            return _SAMPLE

        budget = RequestBudget(2)
        model = OllamaModel(_MODEL, cache_dir=self.root, request_mode="live", transport=intermittently,
                            budget=budget, retry_delay=0)
        self.assertEqual(model.respond(_MESSAGES, []).meta["error"], "request_limit")
        self.assertEqual((len(calls), budget.used), (2, 2))
        budget = RequestBudget(1)
        model = OllamaModel(_MODEL, cache_dir=self.root, request_mode="live", transport=intermittently,
                            budget=budget, retry_delay=0)
        self.assertTrue(model.respond(_MESSAGES, []).tool_calls)
        self.assertEqual(budget.used, 1)

    def test_failed_response_does_not_echo_provider_body(self):
        model = OllamaModel(_MODEL, cache_dir=self.root, request_mode="live",
                            transport=lambda *_: {"error": "private provider body"})
        reply = model.respond(_MESSAGES, [])
        self.assertEqual(reply.text, "")
        self.assertEqual(reply.tool_calls, [])
        self.assertEqual(reply.meta["error"], "invalid_response")
        self.assertFalse(list(self.root.glob("*.json")))

    def test_real_network_path_blocks_hosted_and_cloud_tags_before_chat(self):
        hosts = ("https://ollama.com", "http://127.0.0.1:11434")
        for model, host in ((_MODEL, hosts[0]), ("glm-5.3:cloud", hosts[1])):
            with self.subTest(model=model, host=host):
                adapter = OllamaModel(model, host=host, cache_dir=self.root, request_mode="live", allow_local=True)
                self.assertEqual(adapter.respond(_MESSAGES, []).meta["error"], "live_disabled")
                self.assertEqual(adapter.budget.used, 0)

    def test_hypothetical_hosted_request_never_logs_fake_key(self):
        fake_key = "fixture-secret-not-a-real-credential"

        def fake(request, timeout):
            self.assertEqual(request.get_header("Authorization"), "Bearer " + fake_key)
            return {"message": {"content": "echo " + fake_key}, "done": True, "raw": fake_key}

        with patch.dict(os.environ, {"OLLAMA_API_KEY": fake_key}):
            adapter = OllamaModel(_MODEL, host="https://ollama.com", request_mode="live",
                                  cache_dir=self.root, transport=fake)
            run = run_call(SCENARIOS["S3"], adapter, "harness", 7)
            path = self.root / "trace.jsonl"
            write_trace(path, run.trace)
            self.assertTrue(list(self.root.glob("*.json")))
            self.assertFalse(any(fake_key in p.read_text() for p in self.root.iterdir()))
            self.assertFalse(run.metrics["model_error"])

    def test_fixture_record_and_replay_have_identical_runtime_hashes(self):
        scenario = SCENARIOS["S3"]
        def fake(*_):
            return {"message": {"content": "", "tool_calls": [{"function": {
                "name": "rollback_deployment", "arguments": {"service": "checkout-api", "release": "11"}
            }}]}, "done": True}
        record = OllamaModel(_MODEL, cache_dir=self.root, request_mode="live", transport=fake)
        replay = OllamaModel(_MODEL, cache_dir=self.root)
        one = run_call(scenario, record, "harness", 7)
        two = run_call(scenario, replay, "harness", 7)
        self.assertEqual(trace_hash(one.trace), trace_hash(two.trace))
        self.assertEqual(record.budget.used, 1)
        self.assertEqual(replay.budget.used, 0)
