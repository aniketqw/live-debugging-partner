# RESEARCH NOTES

Plan A is a SIMULATION (no real audio). These are engineering observations, not benchmark results. A0 used no Ollama inference; the later connection check is recorded separately under R2.

### R4-environment-and-urllib (date read: 2026-11-15)
Question: Which Python and OS are available, and can the selected Python's standard-library urllib fetch a researched host with certificate verification?
Claim: `/usr/local/bin/python3.12` runs Python 3.12.8 on macOS arm64. Its urllib can fetch the official documentation outside the restricted network sandbox when explicitly using the existing OS CA bundle. Default HTTPS trust is broken in this interpreter; unrestricted/default connectivity must not be assumed.
Sources: [Python sys reference](https://docs.python.org/3.12/library/sys.html), [platform reference](https://docs.python.org/3.12/library/platform.html), [urllib reference](https://docs.python.org/3.12/library/urllib.request.html), [independently authored urllib HOWTO](https://docs.python.org/3.12/howto/urllib2.html), [ssl reference](https://docs.python.org/3.12/library/ssl.html). The urllib reference and HOWTO independently describe fetching URLs; the ssl reference explains CA loading. Environment identity itself is established by the local probe, not a web claim.
Probe (repository cwd; executed exactly):
```sh
command -v python python3 python3.12
python3 -c 'import sys,platform; print("EXECUTABLE", sys.executable); print("VERSION", sys.version); print("OS", platform.platform())'
python3.12 -c 'import sys,platform; print("EXECUTABLE", sys.executable); print("VERSION", sys.version); print("OS", platform.platform())'
python -c 'import sys; print(sys.version); print(sys.executable)'
```
Probe result (trimmed):
```text
/opt/anaconda3/bin/python
/opt/homebrew/bin/python3
/usr/local/bin/python3.12
EXECUTABLE /opt/homebrew/opt/python@3.14/bin/python3.14
VERSION 3.14.4 (main, Apr  7 2026, 13:13:20) [Clang 21.0.0 (clang-2100.0.123.102)]
OS macOS-27.0.1-arm64-arm-64bit-Mach-O
EXECUTABLE /usr/local/bin/python3.12
VERSION 3.12.8 (v3.12.8:2dc476bcb91, Dec  3 2024, 14:43:19) [Clang 13.0.0 (clang-1300.0.29.30)]
OS macOS-27.0.1-arm64-arm-64bit
3.10.16 (main, Dec 11 2024, 10:22:29) [Clang 14.0.6 ]
/opt/anaconda3/bin/python
```
Probe (initial sandbox attempt):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
import sys, platform, urllib.request
print('executable:', sys.executable)
print('version:', platform.python_version())
print('platform:', platform.platform())
print('stdlib modules:', all(name in sys.stdlib_module_names for name in ('urllib', 'ssl', 'json', 'unittest')))
url = 'https://docs.python.org/3.12/library/urllib.request.html'
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        print('urllib target:', response.url)
        print('urllib status:', response.status)
        print('urllib content-type:', response.headers.get('Content-Type'))
        print('urllib prefix:', response.read(15))
except Exception as error:
    print('urllib failed:', type(error).__name__, str(error))
PY
```
Probe result:
```text
executable: /usr/local/bin/python3.12
version: 3.12.8
platform: macOS-27.0.1-arm64-arm-64bit
stdlib modules: True
urllib failed: URLError <urlopen error [Errno 8] nodename nor servname provided, or not known>
```
Probe (same URL, approved network escalation; default TLS context):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
import urllib.request
url = 'https://docs.python.org/3.12/library/urllib.request.html'
try:
    with urllib.request.urlopen(url, timeout=10) as response:
        print('urllib target:', response.url)
        print('urllib status:', response.status)
        print('urllib content-type:', response.headers.get('Content-Type'))
        print('urllib prefix:', response.read(15))
except Exception as error:
    print('urllib failed:', type(error).__name__, str(error))
PY
```
Probe result:
```text
urllib failed: URLError <urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate (_ssl.c:1000)>
```
Probe (inspect only known CA bundle candidates; no package installed or system file changed):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
import ssl
from pathlib import Path
print('verify paths:', ssl.get_default_verify_paths())
for path in ('/etc/ssl/cert.pem', '/opt/homebrew/etc/openssl@3/cert.pem', '/usr/local/etc/openssl@3/cert.pem'):
    print('CA bundle candidate:', path, 'exists:', Path(path).is_file())
PY
```
Probe result:
```text
verify paths: DefaultVerifyPaths(cafile=None, capath=None, openssl_cafile_env='SSL_CERT_FILE', openssl_cafile='/Library/Frameworks/Python.framework/Versions/3.12/etc/openssl/cert.pem', openssl_capath_env='SSL_CERT_DIR', openssl_capath='/Library/Frameworks/Python.framework/Versions/3.12/etc/openssl/certs')
CA bundle candidate: /etc/ssl/cert.pem exists: True
CA bundle candidate: /opt/homebrew/etc/openssl@3/cert.pem exists: True
CA bundle candidate: /usr/local/etc/openssl@3/cert.pem exists: False
```
Probe (approved network escalation; existing OS CA bundle and TLS validation retained):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
import ssl, urllib.request
url = 'https://docs.python.org/3.12/library/urllib.request.html'
context = ssl.create_default_context(cafile='/etc/ssl/cert.pem')
print('tls hostname check:', context.check_hostname)
print('tls CERT_REQUIRED:', context.verify_mode == ssl.CERT_REQUIRED)
try:
    with urllib.request.urlopen(url, timeout=10, context=context) as response:
        print('urllib target:', response.url)
        print('urllib status:', response.status)
        print('urllib content-type:', response.headers.get('Content-Type'))
        print('urllib prefix:', response.read(15))
except Exception as error:
    print('urllib failed:', type(error).__name__, str(error))
PY
```
Probe result:
```text
tls hostname check: True
tls CERT_REQUIRED: True
urllib target: https://docs.python.org/3.12/library/urllib.request.html
urllib status: 200
urllib content-type: text/html
urllib prefix: b'<!DOCTYPE html>'
```
Status: VERIFIED for the explicit interpreter, observed OS and conditional docs-host HTTPS reachability. Live Ollama host/API behavior is UNVERIFIED and was not attempted; no endpoint/model name is inferred.
Used by task: A0; the network limitation must be rechecked at A11.
Fallback if wrong: run offline contract tests with the explicit interpreter. Fail network operations clearly, or use verified record/replay fixtures in the future adapter task. Never disable certificate/hostname verification. The unspecified “target host” is resolved conservatively in D1; this probe does not establish Ollama connectivity.

### R5-ldp-contract (date read: 2026-11-15)
Question: What are the existing ledger, parameter, bootstrap, commit and cancellation contracts?
Claim: The local source and actual object probes agree on the A0 contract. Ledger transitions do not execute backend effects; Engine owns callback execution and cancellation accounting.
Sources: local `ldp/ledger.py`, `ldp/model.py`, `ldp/experiment.py::boot_ci`, `ldp/engine.py::_commit`, `_stop_job`, `_step_jobs`, `_start_ready`. These are repository contracts, not external APIs; source inspection and independent executable assertions are the evidence. No second external source can define this checkout's behavior.

Digest in own words:
- `St` is the string-valued state enum; it distinguishes planned/announced/running read-only/running changing/paused/completed reversible/completed irreversible/cancelled/undone jobs. `Out` separately describes what a stop or undo request returned.
- `Job` holds identity, name, kind (`ro` or `chg`), duration, commit threshold, reversibility, confirmation and pause flags, dependencies, callbacks, metadata, state and simulated timestamps. A changing job defaults its commit threshold to its duration. `running`, `live` and `done` derive from state; these properties do not perform transitions.
- `Ledger.add` assigns increasing ids and stores jobs; `named` and `live` filter them. `announce` affects proposed jobs; `start` accepts only proposed/announced jobs and chooses the running state from kind. A pausable running changing job can pause/resume. `finish` sets the end timestamp and classifies completion by kind/reversibility; it does not set `committed` or invoke callbacks.
- `Ledger.stop` drops proposed/announced work, protects a running read-only job when its name is in `protected` unless forced, cancels uncommitted running/paused work, and returns too-late for committed changing work. Too-late and protected preserve state. Completed work returns its completion category; other terminal states give no-op. `undo` only marks completed reversible changing work undone; it does not restore a backend itself.
- `Params` is a dataclass of simulated timing assumptions, not measured real speech latency. The observed defaults are in the output below; downstream code should import this class instead of copying defaults.
- `boot_ci(xs, n=2000, seed=7)` removes `None`, uses its own `random.Random(seed)` to sample with replacement, sorts sample means, and returns the input mean with entries at `int(0.025*n)` and `int(0.975*n)`. Empty filtered input returns three `None` values. Equal seeds/inputs repeat. It does not validate `n`: nonempty input with `n=0` raises `IndexError`; callers must use a positive sample count. This is descriptive, not approval of a general statistical method for every future use.
- `Engine._start_ready` waits for successful dependencies, honors edit holds and policy-controlled confirmation, then starts work. `_step_jobs` advances running work by the imported tick; it calls `_commit` once through its `not job.committed` guard when the threshold is met, then finishes and calls completion hooks at duration. `_commit` itself is not idempotent: it marks committed, records a commit event and simulated timestamp, records unwanted-action reasons from ground truth, then calls `on_commit`. Harness code must enforce execution-once rather than repeatedly call `_commit`.
- `_stop_job` delegates to ledger with explicit force OR policy `force_cancel`. Only cancelled work increments wasted simulated time and logs `job_cancel`; dropped work logs `job_drop`. Protected/too-late requests do not become cancellations. Cancellation does not invoke an undo callback.

Probe (exact script; real objects, no edits to protected code):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
from types import SimpleNamespace
from ldp.ledger import Ledger, Job, St, Out
from ldp.model import Params, SessionSpec
from ldp.experiment import boot_ci
from ldp.engine import Engine
from ldp.channels import ARMS
from ldp.policies import POLICIES
ledger = Ledger()
a = ledger.add('announced', 'chg', 100)
ledger.announce(a)
print('announced stop:', ledger.stop(a, 10).value, a.state.value, a.t_end)
b = ledger.add('committed', 'chg', 100, reversible=False)
ledger.start(b, 0); b.committed = True
print('committed stop:', ledger.stop(b, 10).value, b.state.value, b.t_end)
c = ledger.add('protected', 'ro', 100)
ledger.start(c, 0); ledger.protected.add(c.name)
print('protected stop:', ledger.stop(c, 10).value, c.state.value, c.t_end)
d = ledger.add('irreversible', 'chg', 100, reversible=False)
ledger.start(d, 0); ledger.finish(d, 100)
print('irreversible finish:', d.state.value, d.committed, d.t_end)
print('job changing default:', Job(99, 'direct', 'chg', 125).commit_ms)
print('params:', Params())
print('bootstrap empty:', boot_ci([]))
print('bootstrap constant:', boot_ci([2, None, 2], n=20, seed=7))
print('bootstrap seeded:', boot_ci([0, 1, 3], n=100, seed=17))
print('bootstrap repeat equal:', boot_ci([0, 1, 3], n=100, seed=17) == boot_ci([0, 1, 3], n=100, seed=17))
try: boot_ci([1], n=0)
except Exception as error: print('bootstrap n=0:', type(error).__name__)
callbacks = []
app = SimpleNamespace(on_job_done=lambda eng, job: callbacks.append(('done', job.name)))
spec = SessionSpec('probe', 0, [], [], [], lambda: app, 1000, truth={})
engine = Engine(spec, ARMS['interactive_voice'], POLICIES['ledger_rules'])
j = engine.ledger.add('effect', 'chg', 100, reversible=False, on_commit=lambda eng, job: callbacks.append(('commit', job.name)))
engine.ledger.start(j, 0)
engine._step_jobs(); engine._step_jobs()
print('engine step:', j.state.value, j.committed, j.t_commit, callbacks)
print('engine log:', engine.log)
k = engine.ledger.add('wasted', 'ro', 1000)
engine.ledger.start(k, 0); k.run_ms = 300
print('engine cancel:', engine._stop_job(k).value, engine.wasted_ms, engine.log[-1])
p = engine.ledger.add('pending', 'chg', 100)
print('engine drop:', engine._stop_job(p).value, engine.wasted_ms, engine.log[-1])
q = engine.ledger.add('critical', 'ro', 1000)
engine.ledger.start(q, 0); engine.ledger.protected.add(q.name)
print('engine protect:', engine._stop_job(q).value, q.state.value)
PY
```
Probe result:
```text
announced stop: dropped cancelled 10
committed stop: too_late running_changing None
protected stop: protected running_read_only None
irreversible finish: done_irreversible False 100
job changing default: 125
params: Params(tick_ms=100, speak_ms_per_word=400, tts_ms_per_word=400, type_ms_per_word=1200, send_ms=800, switch_ms=1500, typed_ratio=0.6, vad_lag_ms=150, stream_lag_ms=300, final_lag_ms=400, asr_lag_ms=700, barge_cut_ms=250, reply_delay_ms=1500, oracle=False)
bootstrap empty: (None, None, None)
bootstrap constant: (2.0, 2.0, 2.0)
bootstrap seeded: (1.3333333333333333, 0.3333333333333333, 3.0)
bootstrap repeat equal: True
bootstrap n=0: IndexError
engine step: done_irreversible True 0 [('commit', 'effect'), ('done', 'effect')]
engine log: [(0, 'job_commit', {'job': 'effect', 'target': None}), (0, 'job_done', {'job': 'effect'})]
engine cancel: cancelled 300 (0, 'job_cancel', {'job': 'wasted', 'run_ms': 300})
engine drop: dropped 300 (0, 'job_drop', {'job': 'pending'})
engine protect: protected running_read_only
```
Status: VERIFIED for the checked local contracts; the code reading covers the remaining digest details. These probes are not a claim that the future harness safety invariants exist yet.
Used by task: A0; reread at A9.
Fallback if wrong: stop relying on the affected contract, add an attacking test outside `tests/`, record the contradiction and block dependent work. Do not modify `ldp/` to suit the harness.

Implementer may rely on: explicit Python 3.12 executable above; the four A0 transitions observed above; importing `Params` instead of duplicating timing defaults; ledger return values and engine side effects are separate. No live model behavior has been verified.

### R2 — Ollama Cloud via the local app (preflight; date read: 2026-11-15)

Question: Can the existing Ollama app run a cloud chat request without a separate project API key?

Claim: The local Ollama app successfully submitted a short cloud chat request using its existing setup. This establishes a working route from this Mac, not direct hosted API-key authentication, tool calling, or quota limits.

Sources: [Ollama authentication](https://docs.ollama.com/api/authentication), [native chat schema](https://docs.ollama.com/api/chat), [generation options](https://docs.ollama.com/modelfile#valid-parameters-and-values), and the local model list. `ollama list` returned `glm-5.3:cloud`. The account setup was used through the app; no credential value was read or logged.

Probe (repository cwd; approved local network access):
```sh
PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 - <<'PY'
import json
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
request = urllib.request.Request(
    "http://127.0.0.1:11434/api/chat",
    data=json.dumps({
        "model": "glm-5.3:cloud",
        "messages": [{"role": "user", "content": "Reply with exactly: OLLAMA_OK"}],
        "stream": False,
        "think": False,
        "options": {"num_predict": 24},
    }).encode(),
    headers={"Content-Type": "application/json"},
)
try:
    with opener.open(request, timeout=45) as response:
        result = json.load(response)
        print("HTTP:", response.status)
        print("Expected model:", result.get("model") == "glm-5.3:cloud")
        print("Completed:", result.get("done") is True)
        print("Reply matched OLLAMA_OK:", result.get("message", {}).get("content", "").strip() == "OLLAMA_OK")
except urllib.error.HTTPError as error:
    print("HTTP:", error.code)
    raise SystemExit(1)
except (urllib.error.URLError, TimeoutError, ValueError) as error:
    print("Probe failure:", type(error).__name__)
    raise SystemExit(1)
PY
```

Probe result (one synthetic chat request):
```text
HTTP: 200
Expected model: False
Completed: True
Reply matched OLLAMA_OK: True
```

Status: VERIFIED for cloud chat through this app and the requested local tag. The response `model` field did not exactly equal the requested tag; the returned value was deliberately not logged, so no alias mapping is assumed. Direct `https://ollama.com/api` bearer authentication, other models, tool calling, and limits remain unverified.

Used by task: user-requested connectivity preflight only. A11 remains pending.

Fallback if wrong: recheck the app's login and model list. A separate hosted runner would need its own approved credential setup. Use scripted or replay mode if offline or out of quota.

### R6-Spoken release identifiers (date read: 2026-11-15)
Question: Which spoken-number forms are useful test inputs for the synthetic staging demo?
Claim: Example material documents digit-by-digit forms, “double” for repeated digits, and contextual “oh” for zero. A4 uses a small deterministic staging grammar instead of claiming general speech recognition.
Sources: [Google Cloud class tokens, English (India) digit sequences](https://docs.cloud.google.com/speech-to-text/docs/class-tokens), [Cambridge dictionary usage of double](https://dictionary.cambridge.org/us/dictionary/english/double), and [Microsoft SSML examples of oh as zero](https://learn.microsoft.com/en-us/previous-versions/office/developer/communication-server-2007/bb858317%28v%3Doffice.12%29). These examples inform fixtures; the project does not call these services.
Probe: exact, manually specified transcript cases and synthetic release formatting tests in `tests_vh.test_normalize`; run with `PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 -m unittest tests_vh.test_normalize -v`.
Probe result: `Ran 6 tests`, `OK`, `no held-out set yet`; changing the double rule in memory failed the independent CSV test, then restoration passed (`results/a4/`).
Status: VERIFIED for the synthetic staging grammar and local formatter, not for real recognizer behavior or held-out coverage (UNVERIFIED). Used by A4. If an input is unsupported, preserve it without manufacturing a usable release value (D13).

### R1/R3 Native chat contract and reproducibility (date read: 2026-11-15)
Claim: native chat examples use JSON messages and function `tools`, a non-streaming request, a returned `message.tool_calls[*].function` with object arguments, and `tool_name` for tool replies. The client will accept JSON-encoded arguments as a defensive fallback. It requests a fixed seed and temperature; only recording and replay are relied on for identical output.
Sources: [native chat reference](https://docs.ollama.com/api/chat), [tool-call exchange](https://docs.ollama.com/capabilities/tool-calling), [model parameters](https://docs.ollama.com/modelfile#valid-parameters-and-values). These documents do not establish that our installed or cloud models return identical independent responses.
Probe: `python -m unittest tests_vh.test_ollama -v` against a synthetic transport and serialized cache. Native model tool-calling and sampling determinism are PARTIAL pending model-specific live evidence; no extra cloud generation to establish it under D7.
Probe result: `Ran 8 tests`, `OK`. A separate one-attempt loopback probe completed and its recorded response replayed, but the requested tool call was not observed. Real tool behavior and independent-sampling determinism are not established. See `results/a11/local_smoke.txt`.

### R2 Local model inventory follow-up (date read: 2026-11-15)
Sources: [model list](https://docs.ollama.com/api/tags), [local and hosted authentication](https://docs.ollama.com/api/authentication), [usage and balance](https://docs.ollama.com/cloud/usage).
Probe: `ollama list`; `ollama show llama3.1:latest` (capabilities only); standard-library GET to `http://127.0.0.1:11434/api/tags` with the proxy handler disabled, printing each name, whether size is positive, and its formats only.
Probe result: `llama3.1:latest` listed tools capability and `gguf` format. The two `:cloud` entries had blank formats; positive size alone did not distinguish them. No model was run. D7's cloud cost bound remains UNVERIFIED; no default live cloud transport.
Status: VERIFIED for the local inventory observation and the read-only loopback API path. Used by A11.

### R7 Browser speech adapters (date read: 2026-11-15)

Question: How should the demo collect interim/final recognition results, handle recognizer disconnects, and report a conservative synthesized speech prefix when interrupted?

Claim: Feature detect `SpeechRecognition` or `webkitSpeechRecognition`, configure `lang`, `continuous`, and `interimResults`, and read `results` from `resultIndex`. Interim text is provisional; send only final results as user turns. Recognition `end` means the recognition service disconnected, not that a fixed silence timeout elapsed. Restart after `end` only while listening remains explicitly enabled and no terminal error occurred. Synthesis provides a `boundary` event with an approximate `charIndex`; retain only fully preceding words. If there is no boundary evidence before a cut, report the empty prefix rather than guessing from elapsed time. `speechSynthesis.cancel()` cancels the queued utterances and the current utterance; clear callbacks or guard against callbacks arriving after cancellation.

Sources: [Web Speech API specification](https://webaudio.github.io/web-speech-api/), [MDN recognition interface](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition), [recognition resultIndex](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognitionEvent/resultIndex), [recognition end event](https://developer.mozilla.org/en-US/docs/Web/API/SpeechRecognition/end_event), [synthesis boundary event](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesisUtterance/boundary_event), [synthesis cancellation](https://developer.mozilla.org/en-US/docs/Web/API/SpeechSynthesis/cancel), and the [MDN compatibility dataset](https://github.com/mdn/browser-compat-data/blob/main/api/SpeechRecognition.json). Chrome and Safari are manual test candidates, not an app compatibility promise. Some user agents may send audio to their recognition service; only synthetic script speech is suitable for this demo. No microphone use before an explicit user action.

Probe: B3 should run `node --test` with fake boundary and recognition events, followed by the human-run `demo/MANUAL_TEST.md` on Chrome and Safari where available. No live microphone, silence restart, or browser speech boundary test was performed during B0.

Status: PARTIAL for actual browser/voice behavior. Use the typed fallback if recognition is absent, denied, or fails. Keep an explicit stop and a way to disable spoken output; never infer a read-back was heard solely from the duration estimate. Browser APIs do not use the project's Ollama account.

### R8 Stdlib HTTP and SSE (date read: 2026-11-15)

Question: Can an open SSE response send a flushed frame and remain open while a separate HTTP request is processed by the same local server?

Claim: A loopback-only `ThreadingHTTPServer` with a separate stream handler can serve SSE concurrently with mutating POSTs. Emit UTF-8 `text/event-stream` named frames terminated by an empty line, flush each frame, use a cursor/event ID for reconnects, and avoid holding session locks while writing to sockets. Comment frames can keep a quiet stream open. Browser requests can be same-origin through the Vite dev proxy or through the built UI served by Python.

Sources: [Python http.server](https://docs.python.org/3.12/library/http.server.html), [HTML SSE standard](https://html.spec.whatwg.org/multipage/server-sent-events.html), and [MDN SSE framing and reconnects](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events).

Probe: inline Python on an ephemeral loopback port. A `BaseHTTPRequestHandler` under `ThreadingHTTPServer(("127.0.0.1", 0), Handler)` calls `end_headers()`, writes and flushes `b'id: 0\\nevent: ready\\ndata: {"ok":true}\\n\\n'`, waits on a threading `Event`, then writes and flushes a second frame. The test reads the first complete frame with `http.client`, sends a concurrent POST from a second connection (returns 204 and sets the event), then reads the second frame. All connections and the server close in the probe.

Probe result: Default workspace sandbox blocked `socket.bind` with `PermissionError: [Errno 1] Operation not permitted`. Retrying the same loopback-only test with the network permission succeeded: `PASS initial flushed frame and subsequent frame around concurrent POST.`

Status: VERIFIED for this Python transport and read-side framing, not for actual browser proxy behavior until the UI is exercised. Used by B1/B2. Re-run the HTTP integration suite on loopback with network permission if the default sandbox blocks it. The server is not intended for public hosting.

### R9 Exact React/Vite pins (date read: 2026-11-15)

Question: Which versions satisfy the project age rule and run the requested JSX build with the installed Node?

Claim: `vite@7.3.7` (2026-10-06), `react@19.3.0` and `react-dom@19.3.0` (2026-09-09) are older than the minimum age at the research date. Use exact package versions and a lockfile. Vite's core JSX transform works with an explicit React import; no React plugin is required for this demo. This setup does not assume React Fast Refresh.

Sources: [Vite tag](https://github.com/vitejs/vite/releases/tag/v7.3.7), [Vite v7 guide](https://v7.vite.dev/guide/), [React tag](https://github.com/react/react/releases/tag/v19.3.0), [React client mount](https://react.dev/reference/react-dom/client/createRoot), and npm registry package metadata for [Vite](https://registry.npmjs.org/vite), [React](https://registry.npmjs.org/react), and [React DOM](https://registry.npmjs.org/react-dom).

Probe: `node -v; npm -v` gave `v26.13.0` and `11.20.0`. A read-only Node fetch of npm registry `time[version]` and `versions[version].engines` verified the dates above and Vite's Node requirement `^20.19.0 || >=22.12.0`. In a disposable directory, `npm install --prefer-offline --no-audit --no-fund` installed a manifest with only those exact dependencies. A minimal `index.html` loaded an explicit `import React from 'react'` and `createRoot(...).render(<p>Probe</p>)` from JSX. Re-run `npm run build && test -s dist/index.html` passed; its lockfile reports `vite 7.3.7, react 19.3.0, react-dom 19.3.0`. The demo build and functional UI checks remain B2.

Status: VERIFIED for pins, engine and client-only build. Used by B2. If the workspace sandbox blocks registry access, use the approved registry route or install the committed lockfile on a networked development machine. No hosting, Ollama requests, or credentials were used.
