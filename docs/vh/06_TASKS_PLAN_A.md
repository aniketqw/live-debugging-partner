# 06 — Plan A tasks (harness core and bench). Do them IN ORDER.

Each task: **Goal**, **Research**, **Files**, **Tests (write first)**, **Steps**, **Verify**, **Done when**. Follow the 7-step loop in AGENTS.md. Task sizes are small on purpose.

---
## A0 — Setup, research, ldp contract
**Goal:** a clean base and a verified understanding of `ldp`.
**Research:** R4, R5.
**Files:** `vh/__init__.py`, `tests_vh/__init__.py`, `tests_vh/test_ldp_contract.py`, `docs/vh/STATUS.md`, `docs/vh/RESEARCH_NOTES.md`, `docs/vh/DECISIONS.md` (from `templates/`), add `.env` and `__pycache__/` to `.gitignore`.
**Tests:** `test_ldp_contract.py` imports `Ledger, Job, St, Out` and checks, with real objects: (a) `stop` on an announced job returns `Out.DROPPED`; (b) `stop` on a running changing job with `committed=True` returns `Out.TOO_LATE`; (c) `stop` on a running read-only job whose name is in `ledger.protected` returns `Out.PROTECTED`; (d) `finish` on an irreversible changing job gives `St.DONE_IRREV`.
**Steps:** read `ldp/ledger.py`, `ldp/model.py`, `ldp/experiment.py::boot_ci`, `ldp/engine.py::_commit` and `_stop_job`; write the digest (R5) in RESEARCH_NOTES.md.
**Verify:** both unittest commands pass; `git diff --stat -- ldp tests` is empty.
**Done when:** digest written, contract tests green.

## A1 — Types and trace
**Goal:** events and a deterministic trace hash.
**Files:** `vh/types.py`, `vh/trace.py`, `tests_vh/test_trace.py`.
**Tests:** `validate_event` rejects missing fields per the schema table in 02; `seq` must be 0,1,2..; `trace_hash` ignores `meta`; reordering dict keys does not change the hash; changing any `data` value does change it; `write_trace` then `read_trace` round-trips.
**Verify:** `python -m unittest tests_vh.test_trace -v`.
**Done when:** all pass; break-it (I4) recorded later in A9.

## A2 — Backend and tools
**Goal:** the mock bank with strict validation.
**Files:** `vh/backend.py`, `vh/tools.py`, `tests_vh/test_backend.py`.
**Tests (values from `10_SCENARIOS.md`, written by hand):** every tool's valid call and each invalid-arg case (wrong digit count, unknown id, amount mismatch, bad PAN); audit entries; `state_hash` changes after a mutation and is equal across two fresh backends; `update_phone` undo restores the old value; `tool_schemas()` returns one entry per tool with name, description and parameters.
**Verify:** `python -m unittest tests_vh.test_backend -v`.
**Done when:** all pass.

## A3 — ASR fault injection
**Goal:** seeded, logged faults.
**Files:** `vh/faults.py`, `tests_vh/test_faults.py`.
**Tests:** `p=0` returns the reference unchanged and an empty log; the same seed gives the same output; different seeds eventually differ; each fault kind alone, tested with a forced RNG or tiny inputs; the fault log lets you rebuild the reference from the transcript (write `undo_faults(transcript, faults)` in the test helper and check it); `p=1` always faults every faultable token; a regression snapshot for seed 1, `p=0.15`, S1 text (generated once, reviewed by the human; label it "regression snapshot").
**Verify:** `python -m unittest tests_vh.test_faults -v`.
**Done when:** all pass.

## A4 — Spoken-number normaliser
**Research:** R6 (record the supported forms and 2 sources).
**Goal:** deterministic normaliser exactly as in `02_ARCHITECTURE.md` section 6.
**Files:** `vh/normalize.py`, `tests_vh/test_normalize.py`, `tests_vh/data/spoken_numbers_dev.csv` (columns: `spoken,expected`).
**Tests:** write `spoken_numbers_dev.csv` with at least 60 rows covering every rule, including negatives ("do" alone, "a" in prose, "oh" alone). **Compute every `expected` by hand from the rules, never by running the normaliser.** Test: exact match on all rows; `despeak(spoken_form(v, kind), kind) == v` for 200 random values per kind (seeded); `spans` carry original text. If `tests_vh/data/spoken_numbers_heldout.csv` exists, run it and print the rate; if it does not exist, print "no held-out set yet" (do not create it; the human writes it).
**Verify:** `python -m unittest tests_vh.test_normalize -v`.
**Done when:** dev CSV 100%; held-out status printed honestly.

## A5 — TTS mock and barge-in cut
**Files:** `vh/tts.py`, `tests_vh/test_tts.py`.
**Tests:** word timings are `start + i * tts_ms_per_word` (400 ms from `ldp.model.Params`); `cut` before the first word gives `("", 0)`; at the end returns the full text; mid-word times round DOWN to completed words only; cutting twice is idempotent.
**Done when:** all pass.

## A6 — Confirm classifier, control parser, templates
**Files:** `vh/confirm.py`, `tests_vh/test_confirm.py`.
**Tests (by hand from `02` section 5):** yes/no/other table of at least 40 phrases, including "yes", "yeah okay", "no", "no cancel that", "no it is 4 8 2" and "yes 48" (both -> other, because the NORMALISED text contains digits), "haan", "nahi", "maybe", "", "okay no" (-> no); control parser cases including S6, S7, S9 phrases; `render` fills every template and raises on a missing field; read-back text for each irreversible tool contains every arg value in spoken form.
**Done when:** all pass.

## A7 — Scenarios and scripted caller
**Files:** `vh/scenarios.py`, `vh/caller.py`, `tests_vh/test_scenarios.py`.
**Tests:** all ten scenarios exist with the exact data in `10_SCENARIOS.md`; `expected` diffs applied to the initial state give the expected end state; the caller says "yes" on a matching read-back; on a mismatch with `catch_prob=1.0` it says "no, it is ..." with the intended digits; with `catch_prob=0.0` it says "yes"; stops after 3 correction rounds with "cancel"; RNGs are separate (changing `catch_prob` does not change ASR faults for the same seed).
**Done when:** all pass.

## A8 — Scripted models and prompts
**Files:** `vh/agents/base.py`, `vh/agents/scripted.py`, `vh/prompts/agent_system.txt`, `vh/prompts/agent_system_prompt_only.txt`, `tests_vh/test_scripted_models.py`.
**What:** `OracleModel` (reads the latest user text, extracts digits/letters/names, calls the right tool with the right args, speaks a short answer; for S6 it answers with a fixed 60-word explanation) and the five traps from `03_EVAL_SPEC.md` section 3. `agent_system_prompt_only.txt` is `agent_system.txt` plus ONE added paragraph that tells the model to read back and wait for yes before irreversible tools.
**Tests:** a diff test proving the two prompts differ only by that paragraph; each trap behaves as described (unit tests on `respond`).
**Done when:** all pass.

## A9 — Runtime (the three modes)
**Goal:** `CallSession` and `run_call` exactly as in `02_ARCHITECTURE.md` sections 2, 4 and 5.
**Research:** none new; re-read R5 digest.
**Files:** `vh/runtime.py`, `tests_vh/test_runtime.py`.
**Design requirement for Plan B:** implement a stateful `CallSession` (see `02` section 2) and make `run_call` a loop over scripted turns that calls it. Do not write a monolithic function.
**Tests (before code):** one test per invariant using the right trap model, asserting 0 violations in harness mode and >0 in `bare` where the spec says so; V1 (oracle passes all ten scenarios, harness, p=0, catch 1.0); S6 cut and prefix (I3); S7 protect; S8 dropped; S9 too_late and exactly one execution (I6); S10 EXEC_ERROR and no completion text (I5); I4 (run each scenario twice, equal hashes); the "other with digits" correction path creates a second read-back; the reask then abort path.
**Break-it:** do all items in `05_VERIFICATION.md` section 2 for I1 to I7 now.
**Verify:** `python -m unittest tests_vh.test_runtime -v`, plus `python -m unittest discover -s tests -t .`.
**Done when:** all pass and break-it lines are in STATUS.md.

## A10 — Independent checks and the audit script
**Files:** `vh/checks.py`, `scripts/check_invariants.py`, `tests_vh/test_checks.py`.
**What:** implement `check_invariants`, `task_success`, `unconfirmed_irreversible` from `03_EVAL_SPEC.md` (section 7 literally). They must NOT import `vh.runtime`.
**Tests:** hand-built mini-traces (written in the test file) with known violations for each invariant; checks return exactly those violations; a clean trace returns none. `check_invariants.py <dir>` prints a table and exits 1 on any harness-mode violation.
**Done when:** all pass; a grep confirms `checks.py` does not import the runtime.

## A11 — Ollama adapter and cache
**Research:** R1, R2, R3 (VERIFIED or PARTIAL before coding). If no Ollama is reachable, test with a local fake HTTP server that you write from the VERIFIED docs shape, and mark live behaviour PARTIAL.
**Files:** `vh/agents/ollama.py`, `bench/models.json`, `tests_vh/test_ollama.py`.
**Tests:** request body built correctly (model, messages, tools, options); response parsing for `arguments` as dict and as string; tool call ids are generated deterministically if the server gives none; cache key stable; `replay` raises on a miss; `auto` uses the cache; retries; `model_error` handling; the API key never appears in any file or trace (test by writing a trace with a fake key in the env and scanning the output dir).
**Steps:** list models (research the exact call), write `bench/models.json` with names exactly as listed and a `tools_supported` flag. Do not invent names.
**Verify:** unit tests; then, only if a model is reachable, run one live S3 call and store it in the cache.
**Done when:** all pass; R1 to R3 notes written.

## A12 — Stats, bench, report
**Files:** `vh/stats.py`, `vh/bench.py`, `vh/report.py`, `tests_vh/test_stats.py`, `tests_vh/test_bench.py`.
**Tests:** `wilson` against hand-computed values (e.g. 0/10, 10/10, 5/10); `paired_boot` on a tiny example with a known sign; `bench --grid smoke` runs and writes `runs.csv`, traces and `RESULTS.md`; two runs give byte-identical `runs.csv`; `--max-requests` stops the run; the report contains the Limits block and tables T1 to T8; seeds are the same across modes.
**Verify:** `python -m vh.bench --grid smoke`; then `--grid full --models scripted` (free); open `RESULTS.md` and check V1, V2, V2b by eye.
**Done when:** V1, V2, V2b pass in the generated report. If any does not, that is a bug to fix, not a result to explain away.

## A13 — Failure attribution (P2, skip if short on time)
**Files:** `vh/attribution.py`, `tests_vh/test_attribution.py`, bench T9.
**Tests:** a test that `attribute` raises if the trace still contains `asr.out.faults`; hand-built traces for each rule; scoring only inside `vh/bench.py`; false-attribution rate on no-fault runs reported.

## A14 — README and number check
**Files:** `README_VH.md`, `scripts/check_readme_numbers.py`.
**What:** `README_VH.md` follows `09_HONESTY_AND_README.md`. The script finds every number in the README and fails if it does not appear in `results/RESULTS.md` (allowing the numbers in a small allow-list file for versions and counts of files).
**Verify:** `python scripts/check_readme_numbers.py` exits 0.
**Done when:** it passes and the human has read the README.

---
## Order summary

A0 setup -> A1 trace -> A2 backend -> A3 faults -> A4 normaliser -> A5 TTS -> A6 confirm -> A7 scenarios+caller -> A8 models -> A9 runtime -> A10 checks -> A11 Ollama -> A12 bench -> A13 attribution -> A14 README.
Suggested pace: A0 to A9 on day 1, A10 to A14 on day 2.
