# 11 — Human review checklist (for Aniket: what YOU check, phase by phase)

You are the judge. The agent writes code; you decide whether it is correct and viable. Spend your time here.

## After A0 to A5 (foundations)
- [ ] Open `tests_vh/data/spoken_numbers_dev.csv`. Are the expected values right by your own reading? Write 30 extra rows yourself in `spoken_numbers_heldout.csv` (the agent must not write that file). Run them.
- [ ] Read the fault table in `faults.py`. Are the confusions plausible for how speech recognisers actually fail? Adjust via DECISIONS.md if not.
- [ ] Check `git diff --stat -- ldp tests` is empty.

## After A6 to A9 (gate and runtime)
- [ ] Read `confirm.py` classifiers. Try 10 phrases of your own, including Hindi-English ones. Is the conservative behaviour right?
- [ ] Read the read-back templates aloud. Would a caller catch a wrong digit by ear? Are ids spoken digit by digit?
- [ ] Trace walk: open `results/traces/` for S1, S8, S9 in harness mode. Does each event make sense in order?
- [ ] Break-it: ask the agent to show the break-it lines in STATUS.md. Did every invariant test really fail when the mutation was applied?

## After A10 to A12 (checks and bench)
- [ ] `checks.py` does not import the runtime. Is detection logic written from the spec, not copied from the gate?
- [ ] In RESULTS.md check V1, V2, V2b by eye. Does each trap fail where it should in `bare` and stay safe in `harness`?
- [ ] Look at T5 (wrong-commit versus catch probability). Is the headline honest about the catch sweep?
- [ ] Run the bench twice. Identical `runs.csv`?
- [ ] Look at T3 with a real Ollama model. Is the harness better than `prompt_only`, or not? Either answer is fine; being able to say which is the point.

## Before you say anything publicly
- [ ] `python scripts/check_readme_numbers.py` passes.
- [ ] You can explain: the gate, the ledger, why `prompt_only` exists, why the catch sweep exists, what the normaliser does not handle.
- [ ] README says "simulated speech" and carries the limits block.
- [ ] You commit it under your own name (the agent never commits).

## Plan B manual checks
- [ ] Run `demo/MANUAL_TEST.md` in Chrome (and one other browser). Mark which claims became VERIFIED.
- [ ] With headphones, say S1 digits 10 times. Look at the heard-versus-script panel. Is the error type what your fault model assumes?
- [ ] Turn the harness off and repeat. Does the difference match the bench's direction?
- [ ] Prepare a replay and a typed fallback for demo day.
