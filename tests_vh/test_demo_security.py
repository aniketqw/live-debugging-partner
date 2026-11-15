"""Regression checks at the boundary of the local staging demo."""

import http.client
import json
import threading
import unittest
from unittest.mock import patch

from demo.server import make_server


_REQUEST = "Roll back staging checkout-api to release one one."
_INITIAL = "12"
_TARGET = "11"
_FIXTURE_KEY = "synthetic-demo-key-not-for-authentication"


class DemoSecurityTests(unittest.TestCase):
    def setUp(self):
        key = patch.dict("os.environ", {"OLLAMA_API_KEY": _FIXTURE_KEY})
        key.start()
        self.addCleanup(key.stop)
        self.server = make_server(host="127.0.0.1", port=0)
        self.port = self.server.server_address[1]
        thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                  daemon=True)
        thread.start()

        @self.addCleanup
        def stop_server():
            self.server.shutdown()
            self.server.server_close()
            thread.join(timeout=2)

    def request(self, method, path, body=None, *, extra=None):
        headers = {} if extra is None else extra.copy()
        if body is not None:
            headers.setdefault("Content-Type", "application/json")
            body = json.dumps(body)
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, path, body, headers)
            response = connection.getresponse()
            payload = response.read()
            self.assertNotIn(_FIXTURE_KEY.encode(), payload)
            self.assertFalse(any(_FIXTURE_KEY in value for _, value in response.getheaders()))
            return response.status, payload
        finally:
            connection.close()

    def json_request(self, method, path, body=None):
        code, payload = self.request(method, path, body)
        self.assertIn(code, (200, 201), payload)
        return json.loads(payload)

    def new_session(self):
        return self.json_request("POST", "/api/session", {
            "mode": "harness", "model": "oracle", "fault_p": 0, "scenario": None,
        })["session_id"]

    def state(self, session):
        return self.json_request("GET", f"/api/state?session_id={session}")

    def release(self, session):
        return self.state(session)["backend"]["services"]["checkout-api"]["active_release"]

    def say(self, session, text, t=0):
        return self.request("POST", "/api/utterance", {
            "session_id": session, "text": text, "source": "speech", "t_ms": t,
        })

    def speech_id(self, session):
        return self.state(session)["active_speech"]["speech_id"]

    def test_client_timestamp_cannot_substitute_for_playback_completion(self):
        session = self.new_session()
        self.assertEqual(self.say(session, _REQUEST)[0], 200)
        self.assertEqual(self.release(session), _INITIAL)
        code, _ = self.say(session, "yes", 999_999)
        self.assertIn(code, (200, 400, 409))
        self.assertEqual(self.release(session), _INITIAL)
        speech_id = self.speech_id(session)
        self.json_request("POST", "/api/spoken", {
            "session_id": session, "speech_id": speech_id, "complete": True,
        })
        current_t = self.state(session).get("t_ms", 0)
        self.assertEqual(self.say(session, "yes", current_t)[0], 200)
        self.assertEqual(self.release(session), _TARGET)

    def test_wrong_prefix_and_stale_acknowledgment_do_not_complete_next_readback(self):
        session = self.new_session()
        self.assertEqual(self.say(session, _REQUEST)[0], 200)
        first_id = self.speech_id(session)
        code, _ = self.request("POST", "/api/spoken", {
            "session_id": session, "speech_id": first_id, "spoken_prefix": "fabricated", "n_words": 1,
        })
        self.assertIn(code, (400, 409))
        self.assertEqual(self.speech_id(session), first_id)
        self.json_request("POST", "/api/spoken", {
            "session_id": session, "speech_id": first_id, "spoken_prefix": "", "n_words": 0,
        })
        self.assertEqual(self.say(session, "yes", 1)[0], 200)
        next_id = self.speech_id(session)
        self.assertNotEqual(next_id, first_id)
        code, _ = self.request("POST", "/api/spoken", {
            "session_id": session, "speech_id": first_id, "complete": True,
        })
        self.assertIn(code, (400, 409))
        self.assertEqual(self.speech_id(session), next_id)
        self.assertEqual(self.release(session), _INITIAL)

    def test_foreign_origins_and_hosts_are_rejected_before_session_creation(self):
        settings = {"mode": "harness", "model": "oracle", "fault_p": 0, "scenario": None}
        for header in ({"Origin": "https://unrelated.example"}, {"Host": "unrelated.example"}):
            with self.subTest(header=header):
                code, _ = self.request("POST", "/api/session", settings, extra=header)
                self.assertIn(code, (400, 403, 421))
        code, _ = self.request("POST", "/api/session", {**settings, "model": "glm-5.3:cloud"})
        self.assertEqual(code, 400)
        self.assertEqual(self.release(self.new_session()), _INITIAL)

    def test_replay_routes_are_read_only_and_reject_non_trace_names(self):
        session = self.new_session()
        before = self.state(session)
        listed = self.json_request("GET", "/api/traces")
        traces = listed["traces"] if isinstance(listed, dict) else listed
        self.assertTrue(traces, "No saved traces to exercise replay")
        item = traces[0]
        name = item["name"] if isinstance(item, dict) else item
        replay = self.json_request("GET", f"/api/trace?name={name}")
        events = replay["trace"]
        self.assertTrue(events, "Replay did not return any events")
        self.assertEqual([event["seq"] for event in events], list(range(len(events))))
        code, _ = self.request("GET", "/api/trace?name=unknown.jsonl")
        self.assertIn(code, (400, 404))
        code, _ = self.request("GET", "/api/trace?name=..%2F.env")
        self.assertIn(code, (400, 404))
        after = self.state(session)
        self.assertEqual(after["backend"], before["backend"])
        self.assertEqual(after["ledger"], before["ledger"])

    def test_resume_cursor_excludes_played_speech_and_transcript_redacts_key(self):
        session = self.new_session()
        self.assertEqual(self.say(session, f"{_REQUEST} {_FIXTURE_KEY}")[0], 200)
        route = f"/api/events?session_id={session}&once=1"
        code, backlog = self.request("GET", route)
        self.assertEqual(code, 200)
        self.assertIn(b"[REDACTED]", backlog)
        self.assertIn(b"event: speak\n", backlog)
        before = [int(line[4:]) for line in backlog.splitlines() if line.startswith(b"id: ")]
        self.assertEqual(before, sorted(set(before)))
        self.json_request("POST", "/api/spoken", {
            "session_id": session, "speech_id": self.speech_id(session), "complete": True,
        })
        code, resume = self.request("GET", route, extra={"Last-Event-ID": str(before[-1])})
        self.assertEqual(code, 200)
        after = [int(line[4:]) for line in resume.splitlines() if line.startswith(b"id: ")]
        self.assertTrue(after)
        self.assertGreater(min(after), before[-1])
        self.assertIn(b"history", resume)
        self.assertNotIn(b"event: speak\n", resume)
