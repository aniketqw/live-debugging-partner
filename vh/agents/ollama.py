"""Native Ollama JSON and record/replay. Hosted inference is disabled by policy."""

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from time import sleep
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from vh.types import ModelResponse, ToolCall


_LOCAL_MODEL = "llama3.1:latest"
_LOCAL_HOST = "http://127.0.0.1:11434"
_HOSTED = "https://ollama.com"


class CacheMiss(LookupError):
    """No recording exists for an offline request."""


@dataclass
class RequestBudget:
    maximum: int = 0
    used: int = 0

    def __post_init__(self):
        if type(self.maximum) is not int or self.maximum < 0:
            raise ValueError("request limit must be a nonnegative integer")

    def take(self) -> bool:
        if self.used >= self.maximum:
            return False
        self.used += 1
        return True


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _urllib_json(request: Request, timeout: float) -> dict:
    opener = build_opener(ProxyHandler({}), _NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        return json.load(response)


def _scrub(value, secret: str):
    if not secret:
        return value
    if isinstance(value, str):
        return value.replace(secret, "[REDACTED]")
    if isinstance(value, list):
        return [_scrub(item, secret) for item in value]
    if isinstance(value, dict):
        return {_scrub(k, secret): _scrub(v, secret) for k, v in value.items()}
    return value


def _record(raw: dict, count: int) -> dict:
    message = raw["message"]
    if raw.get("done") is not True or not isinstance(message, dict):
        raise ValueError("invalid response")
    text = message.get("content", "")
    calls = message.get("tool_calls", [])
    if not isinstance(text, str) or not isinstance(calls, list):
        raise ValueError("invalid message")
    if not text.strip() and not calls:
        raise ValueError("empty response")
    result = {"text": text, "calls": [], "counts": {}}
    for offset, call in enumerate(calls):
        function = call["function"]
        name, args = function["name"], function["arguments"]
        if isinstance(args, str):
            args = json.loads(args)
        call_id = call.get("id") or f"ollama-{count}-{offset}"
        if not isinstance(args, dict) or not isinstance(name, str) or not isinstance(call_id, str):
            raise ValueError("invalid tool call")
        result["calls"].append({"id": call_id, "name": name, "args": args})
    for key in ("prompt_eval_count", "eval_count"):
        if type(raw.get(key)) is int:
            result["counts"][key] = raw[key]
    return result


def _response(record: dict, source: str) -> ModelResponse:
    return ModelResponse(record["text"], [ToolCall(**call) for call in record["calls"]],
                         {**record["counts"], "source": source})


class OllamaModel:
    def __init__(self, model: str, *, cache_dir: str | Path = "bench/cache",
                 request_mode: str = "replay", host: str | None = None, seed: int = 0,
                 budget: RequestBudget | None = None, allow_local: bool = False,
                 timeout: float = 30, retry_delay: float = 0.25, transport=None):
        if request_mode not in ("replay", "auto", "live"):
            raise ValueError("unknown request mode")
        self.model = model
        self.name = f"ollama:{model}"
        self.cache_dir = Path(cache_dir)
        self.request_mode = request_mode
        self.host = (host or os.environ.get("OLLAMA_HOST") or _LOCAL_HOST).rstrip("/")
        self.options = {"temperature": 0, "seed": seed}
        self.budget = budget if budget is not None else RequestBudget(3 if transport else 0)
        self.allow_local = allow_local
        self.timeout = timeout
        self.retry_delay = retry_delay
        self._test_transport = transport
        self._local_verified = False
        self.replays = 0

    def _payload(self, messages, tools, secret):
        return _scrub({"model": self.model, "messages": messages, "tools": tools,
                       "options": self.options}, secret)

    def cache_key(self, messages: list[dict], tools: list[dict]) -> str:
        payload = self._payload(messages, tools, os.environ.get("OLLAMA_API_KEY", ""))
        return sha256(_canonical(payload)).hexdigest()

    def _local_allowed(self) -> bool:
        url = urlsplit(self.host)
        if (not self.allow_local or self.model != _LOCAL_MODEL or url.scheme != "http"
                or url.hostname not in {"127.0.0.1", "::1"} or url.username is not None
                or url.password is not None or url.path or url.query or url.fragment):
            return False
        if not self._local_verified:
            try:
                inventory = _urllib_json(Request(self.host + "/api/tags"), min(5, self.timeout))
                self._local_verified = any(
                    item["name"] == self.model and item["details"]["format"] == "gguf"
                    and type(item["size"]) is int and item["size"] > 0
                    for item in inventory["models"]
                )
            except (HTTPError, URLError, TimeoutError, KeyError, TypeError, ValueError):
                return False
        return self._local_verified

    @staticmethod
    def _error(label: str) -> ModelResponse:
        return ModelResponse("", [], {"error": label})

    def respond(self, messages: list[dict], tools: list[dict]) -> ModelResponse:
        secret = os.environ.get("OLLAMA_API_KEY", "")
        payload = self._payload(messages, tools, secret)
        key = sha256(_canonical(payload)).hexdigest()
        path = self.cache_dir / f"{key}.json"
        if self.request_mode != "live":
            if path.is_file():
                try:
                    record = json.loads(path.read_bytes())
                    result = _response(_scrub(record, secret), "replay")
                except (OSError, ValueError, TypeError, KeyError):
                    return self._error("invalid_cache")
                self.replays += 1
                return result
            if self.request_mode == "replay":
                raise CacheMiss("no matching offline cache record")
        if self._test_transport is None and not self._local_allowed():
            return self._error("live_disabled")
        request_data = _canonical({**payload, "stream": False})
        headers = {"Content-Type": "application/json"}
        # This path is for the synthetic contract probe. A real hosted endpoint
        # is rejected by the project gate above, before building its request.
        if self._test_transport is not None and self.host == _HOSTED and secret:
            headers["Authorization"] = "Bearer " + secret
        request = Request(self.host + "/api/chat", data=request_data, headers=headers)
        transport = self._test_transport or _urllib_json
        for attempt in range(3):
            if not self.budget.take():
                return self._error("request_limit")
            try:
                raw = transport(request, self.timeout)
            except HTTPError as error:
                if error.code < 500:
                    return self._error("http_error")
            except (URLError, TimeoutError):
                pass
            except (ValueError, TypeError):
                return self._error("invalid_response")
            else:
                try:
                    record = _scrub(_record(raw, len(messages)), secret)
                    contents = _canonical(record)
                except (ValueError, KeyError, AttributeError, TypeError):
                    return self._error("invalid_response")
                path.parent.mkdir(parents=True, exist_ok=True)
                with NamedTemporaryFile(dir=path.parent, delete=False) as file:
                    temporary = Path(file.name)
                    file.write(contents)
                try:
                    temporary.replace(path)
                finally:
                    temporary.unlink(missing_ok=True)
                return _response(record, "live")
            if attempt < 2 and self.budget.used < self.budget.maximum:
                sleep(self.retry_delay)
        return self._error("network_error")
