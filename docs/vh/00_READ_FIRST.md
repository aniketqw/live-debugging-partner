# 00 — Read first

## What this is, in plain words

A **harness** is the code around a language model. The model only reads text and writes text. The harness decides what the model sees, which tool calls actually run, what is spoken aloud, and what happens when the caller interrupts.

A **voice harness** does this for a phone-style call. We build it so that:
- any model can be plugged in (scripted test models, Ollama local models, Ollama cloud models), and
- we can measure how safe the call is, with the same scripted calls for every model.

## Why voice needs its own harness (the whole point)

| Voice fact | What the harness must do |
|---|---|
| Speech recognition (ASR) garbles digits, names and letters | Inject realistic ASR faults to test; normalise spoken numbers; read values back |
| There is no screen to check what was understood | Read back the exact values aloud and wait for a spoken yes before any irreversible action |
| Callers interrupt and correct themselves ("no wait, ...") | Cut agent speech when the caller talks; record only what was actually spoken; cancel or hold the right action |
| Agent speech takes time | Track how much the caller actually heard |
| Silence and cut-offs are failures | Measure talk-over and timing |

If a feature would matter equally for plain text chat, it is NOT a voice feature. Those generic parts (trace, model adapter, bench runner) exist only to support the voice parts.

## What this proves and what it does NOT prove

Plan A is a simulation: scripted callers, simulated speech recognition errors, simulated timing, a mock bank backend. It proves the harness logic and the bench are correct and that the checks can fail. It does NOT prove anything about real phone audio, real accents, real latency, or how people feel.
Plan B adds a browser demo with real speech from the browser. It adds a small real-recognizer sample, not a large study.

## Words you will see

- **ASR**: automatic speech recognition (speech to text). **TTS**: text to speech.
- **Barge-in**: the caller starts talking while the agent is talking.
- **Read-back**: the agent says the exact values it is about to use, e.g. "pay 12500 rupees on loan 4 8 2 9 1 3, say yes to confirm".
- **Irreversible action**: cannot be undone (paying an EMI, submitting KYC, changing a nominee).
- **Ledger**: the state machine from `ldp/ledger.py` that tracks each action (proposed, running, done, cancelled...).
- **Gate**: harness code that refuses to run an irreversible action until a read-back and a yes happened.
- **Oracle model**: a scripted model that always does the right thing. It proves each scenario can be solved.
- **Trap model**: a scripted model that does one specific wrong thing on purpose. It proves each check can fail.
- **Ablation**: run the same model with the harness feature on and off to measure what the harness adds.
- **Invariant**: a property that must hold in 100% of runs (or 0 violations).

## The three modes (this is the core comparison)

| Mode | What it is |
|---|---|
| `bare` | Model gets the raw transcript. Its tool calls run immediately. No gate, no normaliser, speech is never cut. |
| `prompt_only` | Same as `bare`, but the system prompt asks the model to read back and confirm. Nothing enforces it. |
| `harness` | Full harness: normaliser, gate with templated read-back, ledger, barge-in cutting, templated completion messages. |

`prompt_only` exists to be fair: a good prompt alone might already work. The bench shows how much the harness adds beyond a prompt.

## Target repository layout (create as the tasks say)

```
ldp/                      existing simulator, DO NOT EDIT
tests/                    existing tests, DO NOT EDIT
vh/                       new core package (stdlib only)
  types.py trace.py backend.py tools.py faults.py normalize.py
  tts.py confirm.py runtime.py caller.py checks.py attribution.py
  agents/ base.py scripted.py ollama.py
  prompts/ agent_system.txt agent_system_prompt_only.txt
  scenarios.py bench.py stats.py report.py
tests_vh/                 new tests, plus tests_vh/data/
bench/                    models.json, cache/ (Ollama record/replay cache)
results/                  generated: runs.csv, RESULTS.md, traces/
scripts/                  check_invariants.py, check_readme_numbers.py
demo/                     Plan B: server.py and web/ (React)
docs/vh/                  this kit
README_VH.md              honest project README (task A13)
```

## Plans

- **Plan A (must finish):** harness core, bench, Ollama adapter, report. Offline, about 2 days.
- **Plan B (after A is PASS):** browser demo with real speech, replay mode, small calibration. About 1 day.
- Cut order if time runs out: first F11 attribution, then Plan B calibration (B9), then the Plan B scoreboard, then multi-model grid size. Never cut the invariant checks or the harness on/off comparison.
