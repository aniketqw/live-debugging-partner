# Staging voice harness

This is a **simulation with no real audio**. It tests a model-independent confirmation layer for checking a simulated staging deployment and rolling it back to a prior release. It never runs an actual deployment command or connects to a real cluster.

In the [misheard release trace](results/vh/traces/00084_S2_harness.jsonl), the caller says “one one,” but the harness receives “one zero.” It reads back what it is about to execute. The caller corrects it, the earlier proposal is dropped, and the corrected release needs a new read-back and confirmation. The trace shows what was heard, what was spoken, and what the mock tool changed.

The benchmark runs each script in three modes: a plain model, the same model given confirmation instructions, and the model with code enforcing confirmation. The mock tool only accepts allowlisted arguments. The harness uses the arguments it actually read back, respects interruption before approval, and speaks success only after a recorded mock success. These rules do not guarantee that a caller notices a wrong read-back.

## Run locally

From the repository root, using Python 3.12:

```sh
python3.12 -m unittest discover -s tests_vh -t .
python3.12 -m unittest discover -s tests -t .
python3.12 -m vh.bench --grid smoke --output-dir /tmp/staging-voice-smoke
python3.12 scripts/check_invariants.py /tmp/staging-voice-smoke/traces
python3.12 -m vh.bench --grid full --models scripted --output-dir /tmp/staging-voice-full
python3.12 scripts/check_readme_numbers.py
```

Use a fresh output directory for a new grid. Scripted runs do not contact Ollama. Ollama recording/replay is supported separately. The runner defaults to replay for that adapter, refuses hosted inference, and requires both an explicit local opt-in and a request cap to run the allowed local model. The [local verification](results/a11/local_smoke.txt) returned a reply and replayed it, but did not observe the requested tool call.

## Results

The [generated report](results/vh/RESULTS.md) includes the mode comparisons, confidence intervals, catch-probability sweep, and failure attribution. The [CSV](results/vh/runs.csv) backs those tables. The review traces are a small subset; the full grid command recreates the full trace set.

### Limits

- Scripted callers, simulated recognition errors and timing, and a mock staging service.
- A caller can confirm the wrong release if they miss a bad read-back.
- Confidence intervals describe these scripted cases. They are not estimates of real caller behavior.
- Failure attribution is a separate heuristic with measurable false alarms; it does not affect the gate.
- No held-out transcript set or real audio evaluation. The [local browser demo](demo/README.md) has a separate manual speech checklist.

### Validity checks (from the generated report)

| Check | Verdict | Evidence |
| --- | --- | --- |
| V1 | PASS | 12/12 oracle harness tasks passed (zero additional faults, full catch); individual checks in T1. |
| V2 | PASS | no_confirm: 69; wrong_arg: 64; false_success: 24; double_call: 93; readback_liar: 93 |
| V2b | PASS | 540 harness trap runs; no I1/I2/I5/I6 violations required. |
| V3 | NOT RUN | No paired real-model comparison in this grid. Synthetic recording/replay is tested separately. |
| V4 | REPORTED | Bare-mode intervals do not all overlap; this is a scripted-fixture comparison, without a model ranking. |

## Where to look

- `vh/runtime.py`: stepwise call simulator and confirmation gate.
- `vh/checks.py`: independent trace checks.
- `vh/scenarios.py`: synthetic staging cases.
- [STATUS.md](docs/vh/STATUS.md): task evidence and known limits.

Implemented with an AI coding agent. Human review of this README is pending.
