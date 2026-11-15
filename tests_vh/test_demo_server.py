"""Integration tests for the mock staging browser server."""

import http.client
import json
from threading import Thread
import unittest

from demo.server import make_server


class DemoHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = make_server(port=0)
        cls.thread = Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def call(self, method, path, data=None):
        client = http.client.HTTPConnection(*self.server.server_address, timeout=3)
        try:
            client.request(method, path, None if data is None else json.dumps(data),
                           {} if data is None else {"Content-Type": "application/json"})
            response = client.getresponse()
            raw = response.read().decode()
            return response.status, json.loads(raw) if path.split("?")[0] != "/api/events" else raw
        finally:
            client.close()

    def session(self, mode="harness"):
        code, body = self.call("POST", "/api/session", {"mode": mode, "model": "no_confirm", "fault_p": 0})
        self.assertEqual(code, 201)
        return body["session_id"]

    def send(self, session, text, *, t=0, source="typed"):
        code, _ = self.call("POST", "/api/utterance", {"session_id": session, "text": text,
                                                      "source": source, "t_ms": t})
        self.assertEqual(code, 200)

    def state(self, session):
        code, state = self.call("GET", "/api/state?session_id=" + session)
        self.assertEqual(code, 200)
        return state

    def test_stream_order_and_explicit_confirmation(self):
        sid = self.session()
        self.send(sid, "Rollback staging checkout-api to release eleven.")
        state = self.state(sid)
        self.assertEqual(state["backend"]["services"]["checkout-api"]["active_release"], "12")
        status, stream = self.call("GET", "/api/events?session_id=" + sid + "&once=1")
        self.assertEqual(status, 200)
        self.assertLess(stream.index("call"), stream.index("readback"))
        self.assertIn("event: speak", stream)
        self.assertNotIn('"kind":"exec"', stream)
        code, _ = self.call("POST", "/api/spoken", {"session_id": sid, "complete": True,
                                                    "speech_id": state["active_speech"]["speech_id"]})
        self.assertEqual(code, 200)
        self.send(sid, "yes")
        self.assertEqual(self.state(sid)["backend"]["services"]["checkout-api"]["active_release"], "11")

    def test_exact_cut_prefix_and_bare_execution(self):
        sid = self.session()
        self.send(sid, "Rollback staging checkout-api to release eleven.")
        aid = self.state(sid)["active_speech"]["speech_id"]
        status, _ = self.call("POST", "/api/spoken", {"session_id": sid, "speech_id": aid,
                                                     "spoken_prefix": "I will", "n_words": 2})
        self.assertEqual(status, 200)
        _, stream = self.call("GET", "/api/events?session_id=" + sid + "&once=1")
        self.assertIn('"content":"I will"', stream)
        sid2 = self.session("bare")
        self.send(sid2, "Rollback staging checkout-api to release eleven.")
        self.assertEqual(self.state(sid2)["backend"]["services"]["checkout-api"]["active_release"], "11")

    def test_replay_trace_order_and_comparison(self):
        _, listing = self.call("GET", "/api/traces")
        record = listing["traces"][0]["name"]
        _, body = self.call("GET", "/api/trace?name=" + record)
        self.assertEqual([d["seq"] for d in body["trace"]], list(range(len(body["trace"]))))
        _, comparison = self.call("GET", "/api/compare")
        self.assertEqual(comparison["bare"]["final_release"], "10")
        self.assertEqual(comparison["harness"]["final_release"], "11")
