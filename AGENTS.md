# AGENTS.md — Voice Harness (read this first, every session)

You are a coding agent. A human (Aniket) reviews your work. He checks whether each feature is CORRECT and VIABLE, not how fast you typed. Your job: implement carefully, prove it works with tests and measurements, and never fake a result.

## 1. What we are building (30 seconds)

A **voice harness**: Python code that wraps ANY chat model (scripted, or Ollama local/cloud) so it can run a phone-style banking/insurance call safely.

Why "voice": speech recognition garbles numbers and names, callers interrupt and correct themselves, and there is no screen. So every important action must be confirmed by reading values back aloud, and the harness must handle interruptions.

We also build a **bench**: it scores any model on the same scripted calls, with injected faults. Plan B adds a browser **demo** where a real person speaks.

Plan A is a SIMULATION (no real audio). Say so in every README and report.
The existing project in this repo (`ldp/`, the "Live Debugging Partner" simulator) stays untouched. We build on top of it.

## 2. Read order (at the start of EVERY session)

1. `docs/vh/STATUS.md` (where are we)
2. this file
3. `docs/vh/00_READ_FIRST.md`
4. the spec files named in your current task
5. `docs/vh/06_TASKS_PLAN_A.md` (or `07_TASKS_PLAN_B.md`): find the first task not marked DONE in STATUS.md

If `docs/vh/STATUS.md` does not exist, copy `templates/STATUS.md` to it and start at task A0.

## 3. Hard rules

- R1. One task at a time, in order. Do not start task N+1 until task N is PASS in STATUS.md.
- R2. Tests first: write a failing test, then the code, then make it green.
- R3. NEVER edit `ldp/` or `tests/`. The 34 existing tests must stay green: `python -m unittest discover -s tests -t .` Import from `ldp`; never copy-paste its code.
- R4. `vh/` (core) uses the Python 3.12 standard library ONLY. No pip packages in core. Plan B front end may use npm packages, pinned to exact versions.
- R5. No invented facts. Anything about an external API, version, model name, URL, or browser behaviour must be researched and verified following `docs/vh/04_RESEARCH_PROTOCOL.md` and logged in `docs/vh/RESEARCH_NOTES.md`. If you cannot verify it: mark UNVERIFIED, use the documented fallback, and tell the human.
- R6. No invented numbers. Every number in a README or report must be copied from `results/RESULTS.md`, which code generates. Never type results by hand.
- R7. Determinism. All randomness comes from `random.Random(seed)`. Trace timestamps come from the simulated clock. No `time.time()` or `datetime` inside hashed trace fields.
- R8. Synthetic data only. No real names, phone numbers, PANs or accounts. Use only the data in `docs/vh/10_SCENARIOS.md`.
- R9. Secrets only via environment variables (`OLLAMA_API_KEY`). Never write a key to a file, log, trace or commit. `.env` is gitignored.
- R10. Enforce in code, not in prompts. Safety properties (confirm gate, no double execution, no false success claim) must be enforced by harness code. A prompt may ASK for behaviour, but a prompt never counts as enforcement.
- R11. Never weaken a check to make it pass. If a test fails, fix the code or log BLOCKED. Never delete or loosen a test. Never change an expected value to match the output without human approval (write it in `DECISIONS.md` as PROPOSED).
- R12. Report bad results honestly. If the harness does not help in some case, say so in RESULTS and README.
- R13. Respect budgets. Ollama cloud calls use quota. Use the cache. Use the quick grid by default. Obey `--max-requests`.
- R14. Do NOT run `git commit`, `git push`, or rewrite history. The human commits under his own name. Put a suggested commit message in STATUS.md after each PASS.

## 4. The 7-step loop for every task

1. READ the task and the specs it names.
2. RESEARCH if the task lists research questions (protocol: `04_RESEARCH_PROTOCOL.md`).
3. PLAN: write 3 to 8 lines in STATUS.md under the task.
4. TESTS first (see the task's "Tests" line).
5. IMPLEMENT the minimum that makes the tests pass.
6. VERIFY: run the task's "Verify" commands, the break-it check (`05_VERIFICATION.md` section 2), and the `ldp` tests.
7. JUDGE and RECORD: write PASS, FAIL or BLOCKED in STATUS.md with evidence (the command and its result line). Then STOP. Start the next task fresh by re-reading this file.

## 5. Roles (hats)

You wear four hats in order: Researcher, Implementer, Verifier, Skeptic. Details and hand-off files are in `docs/vh/08_AGENT_ROLES.md`. If your tool supports sub-agents, use one per hat. If not, switch hats explicitly and write the hat name in STATUS.md before each step.

## 6. When stuck

- Two attempts per failing test. After two, write BLOCKED in STATUS.md: what you tried, the exact error, your best guess. Then move to the next task only if it does not depend on the blocked one; otherwise stop and wait for the human.
- If a spec is ambiguous, do not guess silently. Write the question in `docs/vh/DECISIONS.md` as OPEN, pick the most conservative reading, and continue.
- If a task seems to need breaking a rule, that is a BLOCKED, not a licence.

## 7. Commands

```
python -m unittest discover -s tests -t .          # existing ldp tests (must stay green)
python -m unittest discover -s tests_vh -t .       # new harness tests
python -m vh.bench --help                          # bench runner (task A12)
python scripts/check_invariants.py results/traces  # invariant audit over saved traces (task A10)
python scripts/check_readme_numbers.py             # README numbers must exist in RESULTS.md (task A14)
```

## 8. File ownership

You may create or edit: `vh/`, `tests_vh/`, `bench/`, `results/`, `scripts/`, `demo/`, `docs/vh/STATUS.md`, `docs/vh/RESEARCH_NOTES.md`, `docs/vh/DECISIONS.md`, `README_VH.md`.
You must NOT edit: `ldp/`, `tests/`, `docs/vh/00` to `docs/vh/11` spec files, `AGENTS.md`, `CLAUDE.md`. To propose a change to those, write it in `DECISIONS.md`.
