# 07 — Plan B tasks (browser demo with real speech). Start only when Plan A tasks A0 to A12 are PASS.

Goal: a person speaks into a browser; the harness listens, confirms by voice, handles interruptions; the screen shows what the recogniser heard, the ledger, and the backend state; a toggle shows harness on versus off.

The demo is NOT a phone line and NOT a study. It shows the harness on real recognition errors and real interruptions, using the browser's speech APIs. Say so on the screen and in the README.

Architecture decisions (change only via DECISIONS.md):
- Python server, standard library only: `http.server.ThreadingHTTPServer`. Browser to server: `fetch` POST. Server to browser: Server-Sent Events (SSE). No WebSocket package.
- Front end: Vite + React (plain JavaScript), pinned exact versions, in `demo/web/`.
- Speech in: browser `SpeechRecognition`. Speech out: browser `speechSynthesis`.
- The server uses `vh.runtime.CallSession` (the same code Plan A tested).

---
## B0 — Research and decisions
**Research:** R7, R8, R9 (and R10 optional, read only). Browser claims stay PARTIAL until the human runs `demo/MANUAL_TEST.md`.
**Output:** RESEARCH_NOTES entries, DECISIONS entries (how SSE is done, which browsers are supported, the pinned versions).

## B1 — Server
**Files:** `demo/server.py`, `tests_vh/test_demo_server.py`.
**Endpoints:**
- `GET /api/models` -> list from `bench/models.json` plus `oracle`.
- `POST /api/session` body `{mode, model, fault_p, scenario|null}` -> `{session_id}`.
- `POST /api/utterance` body `{session_id, text, source: "speech"|"typed", t_ms}` -> `{ok}`; the effects arrive over SSE.
- `POST /api/spoken` body `{session_id, spoken_prefix, n_words}`: the browser reports what was actually spoken when it cut the speech; the server calls `CallSession.speech_cut` (I3 over HTTP).
- `GET /api/events?session_id=...` -> SSE stream of trace events and `speak` instructions.
- `GET /api/state?session_id=...` -> backend state, ledger jobs.
- `GET /api/traces` and `GET /api/trace?name=...` -> saved traces for replay mode.
**Tests (stdlib `http.client`, server on port 0 in a thread):** session creation; utterance leads to events in the right order over SSE; `spoken` makes the history contain exactly the prefix; with `NoConfirmModel`, harness mode does not execute an irreversible call until a yes arrives, and `bare` mode does; bad input returns 400 and the server keeps running; the API key never appears in any response.
**Done when:** all pass.

## B2 — Front end skeleton
**Files:** `demo/web/` (Vite + React), components: `MicPanel`, `TranscriptPanel` (heard versus script), `ScriptCards`, `LedgerPanel`, `BackendPanel`, `Controls` (model dropdown, mode toggle bare / prompt_only / harness, fault slider), `Scoreboard` (reads `results/summary.json` written by the bench), `ReplayPlayer`.
**Tests:** `npm run build` succeeds; a component test or a simple render check if a test runner is already configured (do not add heavy tooling).
**Done when:** the page loads, talks to the server, and shows events from a typed utterance (B6 comes later, but a minimal typed box is allowed here for development).

## B3 — Browser speech adapters
**Files:** `demo/web/src/speech.js`, `demo/web/src/speech.test.js` (run with `node --test`).
**What:** `startRecognition(lang, onInterim, onFinal, onEnd)` with auto-restart when the recogniser stops on silence; `speak(text, {onBoundary, onEnd})`; `cancelSpeech()` returns the spoken prefix computed from `boundary` character indices; barge-in: when interim recognition text arrives while the agent is speaking and the mode is `harness`, cancel speech and `POST /api/spoken`.
**Tests (node):** the prefix function with fake boundary events: cut before the first word, mid-sentence, after the end; it never returns a prefix that includes an unspoken word.
**Manual:** `demo/MANUAL_TEST.md` steps for Chrome and one other browser: mic permission, interim text, barge-in, headphones note (echo). The human runs it; the agent only writes it.
**Done when:** node tests pass; the manual checklist exists.

## B4 — Script cards and automatic scoring
**Files:** `vh/demo_score.py`, `demo/web/src/ScriptCards.jsx`, `tests_vh/test_demo_score.py`.
**What:** cards show the reference script (from scenarios S1, S2, S4, S5 digit-heavy text, plus a free-speech card). After each attempt the server compares `normalize(reference)` with `normalize(transcript)` and stores `{speaker_label, browser, lang, reference, transcript, digit_exact, n_tokens}` in `results/demo_sessions.jsonl`. The speaker label is typed by the person (a pseudonym such as "A"), no real names.
**Tests:** scoring on hand-written pairs; typed attempts are excluded from M10; missing fields are rejected.
**Done when:** all pass.

## B5 — Replay mode
**What:** the player loads a saved trace (a bench trace or a demo session) and replays events with their `t` timing. Same ledger and backend panels. No microphone needed.
**Tests:** the server returns a trace in order; the player module (pure functions) schedules events at the right offsets (test the scheduler with a fake clock).

## B6 — Typed fallback
**What:** a text box that sends the same `/api/utterance` with `source:"typed"`. Used for demo-day failures. The UI shows a visible "typed" badge.

## B7 — Harness on/off demo flow
**What:** one-click flow: choose the S1 card, run the same spoken request with `bare`, then with `harness`, and show side by side what the backend did (for example, the misheard value committed or not). Use the model dropdown for an Ollama model or `NoConfirmModel` as a clear demonstration of the gate.
**Rule:** the demo may show one example; the README must not present it as a result. Results come only from the bench.

## B8 — Recogniser calibration (P2, skip if short on time)
**Files:** `scripts/calibrate_asr.py`, table T10 in RESULTS.
**What:** read `results/demo_sessions.jsonl`; align reference and transcript tokens with `difflib`; count digit substitutions, drops, swaps, and name errors; print the counts next to the injected fault kinds. Print n (attempts, speakers) and the warning "small sample, one browser, not a recogniser benchmark".
**Tests:** the aligner on hand-written pairs.

## B9 — Demo README
**Files:** `demo/README.md`: how to run (`python demo/server.py`, `cd demo/web && npm run dev`), env vars, browser support (as VERIFIED), limits, how to record a screen demo, the manual test checklist. No numbers except those in RESULTS.md.

---
## Plan B order and cut list
B0 -> B1 -> B2 -> B3 -> B6 -> B4 -> B7 -> B5 -> B8 -> B9.
If time is short, cut B8, then B5, then the Scoreboard. Never cut B6 (typed fallback) or the harness on/off toggle.
