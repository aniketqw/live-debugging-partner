# 05 — Verification (how to prove each thing, and how to attack it)

## 1. Always run

```
python -m unittest discover -s tests -t .          # ldp: 34 tests must pass
python -m unittest discover -s tests_vh -t .       # harness tests
git diff --stat -- ldp tests                       # must print nothing (we never edit them)
```

## 2. Break-it check (mandatory for every invariant and rule)

A passing test proves little unless it can fail. For each item below: apply the mutation temporarily, run the named test, confirm it FAILS, revert, confirm it passes. Write one line in STATUS.md per item: `break-it: <item> -> <test> failed as expected -> reverted`.

| Item | Temporary mutation | A test that must fail |
|---|---|---|
| I1 | execute irreversible calls immediately in harness mode | `test_I1_*` |
| I2 | build the read-back from the model's text instead of `shown_args` | `test_I2_*` |
| I3 | put the full text (not the spoken prefix) into history after a cut | `test_I3_*` |
| I4 | add `time.time()` into a hashed trace field | `test_I4_determinism` |
| I5 | speak the model's text next to tool results | `test_I5_*` with `FalseSuccessModel` |
| I6 | remove the execute-once guard | `test_I6_*` with `DoubleCallModel` |
| I7 | change backend state outside `apply` | `test_I7_*` |
| Normaliser | change the `double` rule | dev CSV test |
| Faults | change the order of `rng` calls | golden snapshot test for seed 1 |
| Confirm classifier | let YES win over NO | `test_classify_confirm_*` |

## 3. Skeptic checklist (known ways this kind of project fools itself)

Check every line; write the result in STATUS.md under AUDIT.

- T1. Is the read-back built from `shown_args` (what will run), not from model text?
- T2. Does attribution ever read `asr.out.faults`? (It must not.)
- T3. Does the oracle go through the same gate and checks as every other model? (No special path.)
- T4. Are expected values in tests written by hand from the spec, NOT copied from implementation output? (Circular tests prove nothing.)
- T5. Are the normaliser dev set and the held-out set different files, and is the held-out set written by the human? If it is missing, the report must say "no held-out set yet".
- T6. Is task success measured on backend state, not on text?
- T7. Are the system prompts for `bare` and `harness` identical, and does `prompt_only` differ only by the confirm instruction? (A better prompt for the harness arm would be cheating.)
- T8. Are the same seeds used across modes (paired)?
- T9. Are model errors counted and shown?
- T10. Are live and replay runs reported separately?
- T11. Is the catch sweep shown beside every wrong-commit headline?
- T12. Are README numbers copied from RESULTS.md (run `check_readme_numbers.py`)?
- T13. Do traces, cache, or logs contain the API key or any secret? Run `grep -rIl "OLLAMA_API_KEY=" . ` and a search for the key value patterns; must be empty.
- T14. Is `git diff --stat -- ldp tests` empty?
- T15. Did anyone tune scenarios, faults or rules after seeing model results? If so it must be in DECISIONS.md.

## 4. Result audit (before any README claim)

1. Run `python -m vh.bench --grid smoke` twice; the two `runs.csv` files must be byte-identical.
2. Open 5 random traces by hand (one per mode, include S6, S9, S10) and read them end to end. Write what you saw.
3. Run `python scripts/check_invariants.py results/traces` and attach the output.
4. Recompute one table cell by hand from `runs.csv` and compare it with RESULTS.md.

## 5. STATUS.md entry format

```
## Task A6 — runtime and gate — PASS | FAIL | BLOCKED
Hat log: researcher -> implementer -> verifier -> skeptic
Plan: ...
Tests written: tests_vh/test_runtime.py (12 tests)
Verify: <command> -> <result line>
Break-it: ...
Suggested commit message: "..."
Open questions: ...
```
