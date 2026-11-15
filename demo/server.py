"""Loopback-only server for the synthetic staging voice demo."""

from argparse import ArgumentParser
import csv
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import sys
from threading import Condition, RLock
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if __package__ in (None, ""):
    sys.path.insert(0, str(ROOT))

from vh.agents.scripted import MODELS, NoConfirmModel
from vh.backend import Backend
from vh.runtime import CallSession, run_call
from vh.scenarios import SCENARIOS, initial_state
from vh.trace import read_trace


MODES = {"harness", "bare", "prompt_only"}
MAX_TEXT = 1000


def clean(text):
    key = os.environ.get("OLLAMA_API_KEY", "")
    return text.replace(key, "[REDACTED]") if key else text


def encode(data):
    return json.dumps(data, separators=(",", ":"), allow_nan=False).encode("utf-8")


def comparison():
    scenario = SCENARIOS["S2"]
    def summarize(mode):
        result = run_call(scenario, NoConfirmModel(), mode, 1)
        return {"initial_release": "12",
                "final_release": result.final_state["services"]["checkout-api"]["active_release"],
                "commits": [e["data"]["args"]["release"] for e in result.trace
                            if (e["stage"], e["kind"]) == ("tool", "exec") and e["data"]["tool_kind"] == "irrev"],
                "trace": result.trace}
    return {"scenario": "S2", "reference": scenario.turns[0].say,
            "heard": "Roll back staging checkout-api to release one zero.",
            "bare": summarize("bare"), "harness": summarize("harness")}


class Room:
    def __init__(self, runtime):
        self.runtime = runtime
        self.ready = Condition(RLock())

    def frames_after(self, cursor):
        frames = []
        for event in self.runtime.trace[max(0, cursor // 2 - 1):]:
            base = event["seq"] * 2 + 1
            if base > cursor:
                frames.append((base, "trace", event))
            if (event["stage"], event["kind"]) == ("tts", "start") and base + 1 > cursor:
                speech = {key: event["data"][key] for key in ("text", "start_ms", "end_ms")}
                frames.append((base + 1, "speak", {**speech, "speech_id": event["seq"]}))
        return frames


class DemoServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, *, trace_dir, web_dir, score_path):
        super().__init__(address, Handler)
        self.rooms = {}
        self.lock = RLock()
        self.trace_dir = Path(trace_dir).resolve()
        self.web_dir = Path(web_dir).resolve()
        self.score_path = Path(score_path)

    def room(self, token):
        with self.lock:
            return self.rooms.get(token) if isinstance(token, str) else None


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass

    def _reply(self, status, data):
        self._bytes(status, "application/json; charset=utf-8", encode(data))

    def _bytes(self, status, kind, body):
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _trusted(self):
        try:
            base = urlsplit("//" + self.headers.get("Host", ""))
            hosts = {"127.0.0.1", "localhost", "::1"}
            ports = {None, self.server.server_port, 5173}
            if base.hostname not in hosts or base.port not in ports or base.username or base.path:
                return False
            origin = self.headers.get("Origin")
            if origin:
                origin = urlsplit(origin)
                return (origin.scheme == "http" and origin.hostname in hosts and origin.port in ports
                        and not origin.username and not origin.path and not origin.query and not origin.fragment)
            return True
        except ValueError:
            return False

    def _body(self):
        if self.headers.get_content_type() != "application/json" or self.headers.get("Transfer-Encoding"):
            raise ValueError
        size = int(self.headers.get("Content-Length", "0"))
        if not 0 < size <= 16384:
            self.close_connection = True
            raise ValueError
        data = json.loads(self.rfile.read(size))
        if not isinstance(data, dict):
            raise ValueError
        return data

    def do_POST(self):
        if not self._trusted():
            self.close_connection = True
            self._reply(403, {"error": "loopback requests only"})
            return
        try:
            data = self._body()
            path = urlsplit(self.path).path
            if path == "/api/session":
                return self._create(data)
            if path == "/api/score":
                return self._score(data)
            if path not in ("/api/spoken", "/api/utterance"):
                return self._reply(404, {"error": "unknown path"})
            room = self.server.room(data.get("session_id"))
            if room is None:
                return self._reply(404, {"error": "unknown session"})
            with room.ready:
                runtime = room.runtime
                if path == "/api/utterance":
                    text, source, t = data.get("text"), data.get("source"), data.get("t_ms")
                    if (not isinstance(text, str) or not text.strip() or len(text) > MAX_TEXT
                            or source not in ("speech", "typed") or type(t) is not int or not 0 <= t <= 2**53 - 1):
                        raise ValueError
                    text.encode("utf-8")
                    if runtime.turn >= 80:
                        return self._reply(409, {"error": "start a new session"})
                    runtime.user_turn(clean(text), runtime.now, source=source)
                else:
                    marker, complete = data.get("speech_id"), data.get("complete", False)
                    prefix, words = data.get("spoken_prefix", ""), data.get("n_words", 0)
                    if type(marker) is not int or type(complete) is not bool or not isinstance(prefix, str) or type(words) is not int:
                        raise ValueError
                    runtime.acknowledge_speech(marker, complete=complete, prefix=clean(prefix), n_words=words)
                runtime.drain()
                room.ready.notify_all()
            self._reply(200, {"ok": True})
        except LookupError:
            self._reply(409, {"error": "stale speech or unavailable fixture"})
        except (ValueError, TypeError, UnicodeError):
            self.close_connection = True
            self._reply(400, {"error": "invalid input"})

    def _create(self, data):
        mode, model = data.get("mode", "harness"), data.get("model", "oracle")
        fault, scenario_id = data.get("fault_p", 0.0), data.get("scenario")
        if (mode not in MODES or model not in MODELS or type(fault) not in (int, float)
                or not 0 <= fault <= 1 or (scenario_id is not None and scenario_id not in SCENARIOS)):
            raise ValueError
        scenario = SCENARIOS.get(scenario_id)
        runtime = CallSession(MODELS[model](), mode, 1,
                              Backend(initial_state(), fault=scenario.backend_fault if scenario else None),
                              scenario=scenario, fault_p=fault, external_speech=True)
        token = uuid4().hex
        with self.server.lock:
            if len(self.server.rooms) >= 64:
                self.server.rooms.pop(next(iter(self.server.rooms)))
            self.server.rooms[token] = Room(runtime)
        self._reply(201, {"session_id": token})

    def _score(self, data):
        from vh.demo_score import score
        with self.server.lock:
            result = score(data, self.server.score_path, redact=clean)
        self._reply(200, result)

    def do_GET(self):
        if not self._trusted():
            self._reply(403, {"error": "loopback requests only"})
            return
        try:
            url = urlsplit(self.path)
            params = parse_qs(url.query, max_num_fields=8)
            key = lambda name: params.get(name, [""])[0]
            path = url.path
            if path == "/api/models":
                inventory = json.loads((ROOT / "bench/models.json").read_text())
                models = [{"name": name, "kind": "scripted", "available": True} for name in MODELS]
                models.extend({"name": record["name"], "kind": "ollama", "available": False}
                              for record in inventory["models"])
                return self._reply(200, {"models": models})
            if path == "/api/scenarios":
                return self._reply(200, {"scenarios": [
                    {"id": item.id, "title": item.title,
                     "reference": next(turn.say for turn in item.turns if "Roll back" in turn.say),
                     "turns": [{"say": turn.say, "role": turn.role, "when": turn.when} for turn in item.turns]}
                    for item in SCENARIOS.values()
                ]})
            if path == "/api/compare":
                return self._reply(200, comparison())
            if path == "/api/summary":
                return self._reply(200, self._summary())
            if path in ("/api/traces", "/api/trace"):
                return self._replay(path, key("name"))
            if path in ("/api/state", "/api/events"):
                room = self.server.room(key("session_id"))
                if room is None:
                    return self._reply(404, {"error": "unknown session"})
                if path == "/api/events":
                    cursor = int(self.headers.get("Last-Event-ID") or key("after") or 0)
                    return self._events(room, max(0, cursor), key("once") == "1")
                with room.ready:
                    runtime = room.runtime
                    return self._reply(200, {"backend": runtime.backend.snapshot(), "mode": runtime.mode,
                        "t_ms": runtime.now, "active_speech": runtime.active_speech(),
                        "ledger": [{"id": j.id, "job": j.id, "name": j.name, "state": j.state.value,
                                    "kind": j.kind, "committed": j.committed} for j in runtime.ledger.jobs]})
            if path.startswith("/api"):
                return self._reply(404, {"error": "unknown path"})
            self._static(path)
        except (ValueError, OSError, TypeError, KeyError):
            self._reply(400, {"error": "invalid input"})

    def _events(self, room, cursor, once):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True
        try:
            while True:
                with room.ready:
                    frames = room.frames_after(cursor)
                    if not frames and not once:
                        room.ready.wait(timeout=5)
                        frames = room.frames_after(cursor)
                if frames:
                    for frame_id, kind, data in frames:
                        self.wfile.write(f"id: {frame_id}\nevent: {kind}\ndata: ".encode() + encode(data) + b"\n\n")
                        cursor = frame_id
                elif not once:
                    self.wfile.write(b": keep-alive\n\n")
                self.wfile.flush()
                if once:
                    return
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return

    def _replay(self, path, name):
        allowed = {p.name: p for p in self.server.trace_dir.glob("*.jsonl") if not p.is_symlink()}
        if path.endswith("/trace"):
            if name not in allowed:
                return self._reply(404, {"error": "unknown trace"})
            return self._reply(200, {"trace": read_trace(allowed[name])})
        result = []
        for key, file in sorted(allowed.items()):
            start = read_trace(file)[0]["data"]
            result.append({"name": key, "scenario": start["scenario"], "mode": start["mode"]})
        self._reply(200, {"traces": result})

    @staticmethod
    def _summary():
        with (ROOT / "results/vh/runs.csv").open(newline="", encoding="utf-8") as file:
            rows = list(csv.DictReader(file))
        groups = []
        for mode in ("bare", "prompt_only", "harness"):
            group = [r for r in rows if r["mode"] == mode and r["status"] == "ok" and r["route"] == "scripted"]
            groups.append({"mode": mode, "runs": len(group), "successful": sum(int(r["task_success"]) for r in group),
                           "wrong_commits": sum(int(r["wrong_commit"]) for r in group),
                           "unconfirmed": sum(int(r["unconfirmed"]) for r in group)})
        return {"total": sum(group["runs"] for group in groups), "modes": groups, "grid": "full-scripted"}

    def _static(self, path):
        candidate = (self.server.web_dir / unquote(path).lstrip("/")).resolve()
        if not candidate.is_relative_to(self.server.web_dir):
            return self._reply(404, {"error": "unknown path"})
        if candidate == self.server.web_dir:
            candidate = candidate / "index.html"
        if not candidate.is_file():
            return self._reply(404, {"error": "build the frontend or use the Vite dev server"})
        mime = mimetypes.guess_type(candidate)[0] or "application/octet-stream"
        self._bytes(200, mime, candidate.read_bytes())


def make_server(host="127.0.0.1", port=8765, *, trace_dir=ROOT / "results/vh/traces",
                web_dir=ROOT / "demo/web/dist", score_path=ROOT / "results/demo_sessions.jsonl"):
    if host != "127.0.0.1":
        raise ValueError("the demo binds only to IPv4 loopback")
    return DemoServer((host, port), trace_dir=trace_dir, web_dir=web_dir, score_path=score_path)


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    with make_server(port=args.port) as server:
        print(f"Staging simulator: http://127.0.0.1:{server.server_port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
