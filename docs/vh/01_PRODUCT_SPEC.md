# 01 — Product spec (features)

Priority: P0 must have, P1 should have, P2 nice to have. "Voice?" says why the feature exists.

## F1 Trace (P0, generic support)
Every run writes a JSONL trace: one event per line, schema in `02_ARCHITECTURE.md` section 3. `vh/trace.py` has `write_trace`, `read_trace`, `trace_hash`.
- Accept: a trace validates against the schema; the same seed and scripted model gives an identical `trace_hash` (invariant I4).

## F2 Mock backend and tools (P0)
A mock bank/insurer in memory. Tools classified read-only, reversible, or irreversible. Strict argument validation. Data in `10_SCENARIOS.md`.
- Accept: calling an irreversible tool twice with the same args changes state once only when the harness is on (I6); invalid args return a `tool.error`, never a crash.

## F3 ASR fault injection (P0, Voice? yes: text has no recognition step)
Seeded faults on the caller's transcript: digit substitution, digit drop, adjacent-digit swap, name homophone, word drop. Every fault is logged as ground truth (`asr.out.faults`).
- Accept: same seed gives the same faults; fault rate 0 gives a transcript identical to the reference; fault log lets you rebuild the reference from the transcript.

## F4 Spoken-number normaliser (P0, Voice? yes: callers say "double five", "twelve hundred", "ek lakh")
Deterministic code, no model. Converts spoken numbers and spelled letters to digits and letters (rules in `02_ARCHITECTURE.md` section 6).
- Accept: 100% exact match on `tests_vh/data/spoken_numbers_dev.csv`; also report the exact-match rate on the human-written held-out file `tests_vh/data/spoken_numbers_heldout.csv` (the human supplies it; if absent, say "no held-out set yet").

## F5 TTS mock and barge-in (P0, Voice? yes)
Mock speech output with word timings from `ldp.model.Params.tts_ms_per_word` (400 ms). The caller can start talking during agent speech. In harness mode speech is cut after `barge_cut_ms` (250 ms) and the model's history gets only the spoken prefix.
- Accept: after a cut, the assistant text in history equals the spoken prefix exactly (I3); in `bare` mode speech is not cut and talk-over milliseconds are measured.

## F6 Confirm gate with spoken read-back (P0, Voice? yes: no screen)
In harness mode an irreversible tool call is NOT executed. The harness builds a read-back from the tool call's arguments, speaks it, and waits. Yes executes; no cancels; anything else is handled as in `02_ARCHITECTURE.md` section 5.
- Accept: I1 and I2 hold for every model including trap models; a model that emits a tool call without any text still gets read back.

## F7 Ledger integration (P0, Voice? yes: speech acts on running work)
Use `ldp.ledger.Ledger` (states `St`, outcomes `Out`) for every tool call. "Stop" and "wait" from the caller go through `Ledger.stop` and `Ledger.hold`. Outcomes `TOO_LATE`, `DONE_IRREV`, `CANCELLED`, `DROPPED` map to fixed spoken templates.
- Accept: scenarios S7, S8, S9 produce the exact ledger transitions listed in `10_SCENARIOS.md`.

## F8 Model adapters (P0, generic)
One interface `ModelAdapter.respond(messages, tools) -> ModelResponse`. Adapters: `OracleModel`, trap models, `OllamaModel` (native `/api/chat`, local or cloud), plus a record/replay cache.
- Accept: the same `run_call` works for every adapter; replay mode reproduces an Ollama run's trace hash exactly.

## F9 Scenarios (P0)
Ten scripted calls with a reactive caller and an exact expected backend end-state (`10_SCENARIOS.md`).
- Accept: the oracle passes all ten at fault rate 0 in harness mode (V1).

## F10 Bench, stats, report (P0)
`python -m vh.bench` runs models x modes x scenarios x fault levels x catch probabilities x repeats, writes `results/runs.csv`, traces, and `results/RESULTS.md`.
- Accept: one command regenerates every table; every proportion has a Wilson 95% interval; means use `ldp.experiment.boot_ci`; the report states limits.

## F11 Failure attribution (P2)
A rule-based debugger that reads only the trace and names the stage that failed (ASR, AGENT, TOOL, TTS, NONE). Rules in `02_ARCHITECTURE.md` section 8.
- Accept: scored against the injected ground truth; it never reads the fault log; false-attribution rate on no-fault runs is reported.

## F12 Browser demo (Plan B, P1)
React front end, small stdlib Python server, real browser speech in and out, ledger and backend panels, harness on/off toggle, script cards with automatic scoring, replay mode, typed fallback. Details in `07_TASKS_PLAN_B.md`.

## F13 Recognizer calibration (Plan B, P2)
Compare the error types of the real browser recognizer (from demo sessions) with the injected fault types. Counts only, with a small-sample warning.
