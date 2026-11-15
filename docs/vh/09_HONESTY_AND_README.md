# 09 — Honesty rules and the README template

## Allowed claims (after the checks pass)

- "A model-agnostic voice-agent harness with simulated speech, evaluated on 10 scripted scenarios."
- "In harness mode, 0 of N runs executed an irreversible action without a spoken read-back and a yes" (with N and the invariant name).
- "Compared with the same model with a prompt that asks for confirmation, the harness changed wrong-commit rate from X to Y (95% CI), at catch probability Z" (copy numbers from RESULTS.md; show the catch sweep).
- "Normaliser exact match: dev 100% (n rows), held-out: <rate or 'no held-out set yet'>."
- Plan B: "Demo uses the browser's speech recogniser; n attempts from k speakers; digit exact match <rate>."

## Forbidden claims

- "Voice agent", "production-ready", "works on phone calls", "improves models", anything about latency in the real world.
- Any statement that the harness "makes the caller understand". It guarantees a confirmation step, not understanding.
- Any model ranking from n < 10 cells.
- Any number not in RESULTS.md.

## Limits block (copy into README_VH.md and RESULTS.md verbatim)

```
Limits
- Plan A is a simulation: scripted callers, simulated ASR errors, simulated timing, mock backend.
- The scripted caller notices read-back mismatches with a set probability; real callers differ.
- Only 10 scenarios, 5 fault kinds, synthetic data.
- Safety invariants hold because harness code enforces them; they say nothing about whether callers understood.
- Models are tested at temperature 0 with a small number of repeats; results vary by model version.
- The real-recogniser sample (Plan B) is small, from one browser, and is not a recogniser benchmark.
```

## README_VH.md structure

1. One-sentence description (use the allowed wording).
2. Why voice (the table from `00_READ_FIRST.md`, short).
3. How to run: tests, smoke bench, full scripted bench, Ollama quick bench (env vars, `--max-requests`).
4. Results: paste tables FROM RESULTS.md (copy, do not retype), with the limits block directly above them.
5. What the harness guarantees (I1 to I7) and what it does not.
6. How it was built: "Implemented with an AI coding agent; the design, acceptance tests, and evaluation were specified and reviewed by <human name>." (The human decides the final wording. Do not hide AI assistance if asked.)
7. Known issues and BLOCKED items from STATUS.md.
8. Files map.

## Resume safety (for the human, not for the agent)

Add this project to a resume only when: the repo has commits in your own name, `check_readme_numbers.py` passes, and you can explain every module and every number. Describe it as a harness with simulated speech unless Plan B calibration actually exists.
