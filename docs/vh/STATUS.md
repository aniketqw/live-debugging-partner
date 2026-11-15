# STATUS

Current task: Plan A and Plan B implementation complete. Local browser and automated verification recorded below. Maintainer README read-through and manual native speech checks remain pending.

Publication scope: the repository includes source, tests, setup instructions, the generated benchmark and saved examples. Machine-specific task logs and one-off local probes are retained in the development checkout. Historical references to those files below record where evidence was captured.
Last updated: 2026-11-15

Plan A is a SIMULATION (no real audio). This setup task makes no benchmark claims.

Ollama budget: aim for no additional charges; USD 2 total project cap. Live cloud calls are off unless their cost can be bounded within the remaining budget. See D7 in `DECISIONS.md`.

## Task log
## Task A0 — Setup, research, ldp contract — DONE — PASS

Plan:
- Install the supplied kit verbatim and initialize its tracking documents.
- [Researcher] Verify the environment and existing ldp contracts; record R4 and R5 with runnable probes.
- [Implementer] Write the contract tests first, demonstrate a failing setup check, then create the minimum package skeleton and ignore rules.
- [Verifier] Run both suites, attack the contract tests without editing protected files, and confirm ldp/ and tests/ remain unchanged.
- [Skeptic] Audit the evidence and record the verdict, then stop before A1.

Hat log:
- [Researcher] Starting R4 and R5; no product code may be written in this role.
- [Researcher] R4 and R5 recorded in RESEARCH_NOTES.md. Use `/usr/local/bin/python3.12`; HTTPS documentation probe succeeded with certificate validation and the system CA bundle. Live Ollama remains untested and is deferred to A11.
- [Implementer] Starting tests-first setup and the ledger contract tests, using the Researcher hand-off.
- [Implementer] Wrote tests before the package skeleton: the four required real-object ledger contracts passed; the package import test failed because `vh` did not exist. Created only the minimal package skeleton and the required `.env` ignore entry, preserving existing ignores. The same tests then passed. Raw output: `results/a0/implementer_red.txt`, `results/a0/implementer_green.txt`.
- [Verifier] Starting independent suite runs, scope checks and in-memory contract attacks. Future harness invariants are not implemented in A0 and must not be claimed as verified.
- [Verifier] Independent verification PASS: existing suite and new contract suite green; protected file hashes and kit bytes unchanged; required ignores work. Four in-memory mutations each failed the named contract test, then passed after restoration. Reproduce with `PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 results/a0/verify_probe.py`; raw output in `results/a0/verification.txt` and `results/a0/break_it.txt`.
- [Skeptic] Starting the scoped checklist and final verdict; runtime invariants and result audits remain deferred to their planned tasks.
- [Skeptic] Reviewed the task, local source, research notes, decisions, tests-first logs, verification logs and mutation probe. Independently reran both test suites, checked the protected baseline hashes and scanned executable/setup artifacts for credential assignments and token patterns. No applicable A0 issue remains. Verdict: PASS for setup and the existing ledger contracts only.

Tests written: `tests_vh/test_ldp_contract.py` contains the four handwritten A0 ledger contract tests and one package-import setup test. They use real `Ledger`/`Job` objects; expected enum values come directly from A0, not generated implementation output. The initial import failure and subsequent green run are saved in `results/a0/implementer_red.txt` and `results/a0/implementer_green.txt`.

Verify (repository cwd; explicit interpreter selected by R4):
- `PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 -m unittest discover -s tests -t .` -> `Ran 34 tests`, `OK`, exit 0; independently rerun by Skeptic.
- `PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 -m unittest discover -s tests_vh -t .` -> `Ran 5 tests`, `OK`, exit 0; independently rerun by Skeptic.
- `git diff --stat -- ldp tests` -> no output, exit 0; independently rerun by Skeptic.
- `PYTHONDONTWRITEBYTECODE=1 /usr/local/bin/python3.12 results/a0/verify_probe.py` -> `PASS: A0 independent suites, scope preservation, ignore rules, and all four in-memory mutation checks.`, exit 0. Exact commands and output are retained in `results/a0/verification.txt` and `results/a0/break_it.txt`.
- `git check-ignore --no-index -v -- .env vh/.env __pycache__/a0_probe.pyc vh/__pycache__/a0_probe.pyc` -> all named paths ignored, exit 0 (recorded by the probe; no secret file created).
- Probe SHA-256 and path-set comparisons against `results/a0/protected_baseline.json` -> protected files, including existing bytecode, unchanged. `README.md` and existing `results/RESULTS.md` unchanged from the captured pre-task baseline; immutable kit files match archive bytes. The README's preexisting working-tree edit is preserved.

Break-it (in-memory patches only; protected source files never edited):
- break-it: announced job returns cancellation instead of drop -> `test_stop_announced_job_is_dropped` failed as expected -> reverted -> same test passed.
- break-it: committed changing job is cancelled -> `test_stop_committed_changing_job_is_too_late` failed as expected -> reverted -> same test passed.
- break-it: protected read-only job is forcibly cancelled -> `test_stop_protected_running_read_only_job_is_protected` failed as expected -> reverted -> same test passed.
- break-it: irreversible finish becomes reversible -> `test_finish_irreversible_changing_job_is_done_irreversible` failed as expected -> reverted -> same test passed.

Open questions: D1 remains OPEN for A11 because no live target host is specified. This does not block offline A0: the successful transport probe is explicitly limited to the researched documentation host; no model behavior is claimed. Default TLS trust is broken for the selected interpreter; R4/D2 record the verified system-CA probe and a safe offline fallback. No unverified external behavior is used by the package skeleton or contract tests.

Suggested commit message (suggestion only; no commit or push performed): `Set up voice harness simulation and verify existing ledger contracts`

Stop: A0 ended here. The human subsequently authorized A1.

## Task A1 — Types and trace — DONE — PASS

Plan:
- [Researcher] Read the local trace contract and record only decisions needed for A1; no external probes or Ollama calls.
- [Implementer] Write the trace tests first, show the failing run, then add the shared model-response types and JSONL trace functions.
- [Verifier] Run the targeted and full suites; attack the hash with bad behavior in memory and verify protected paths stayed unchanged.
- [Skeptic] Check coverage and evidence, record the verdict, then stop before A2.

Hat log:
- [Researcher] Starting review of the local A1 schema and test contract. The trace layer is reusable for the staged deployment demo.
- [Researcher] Completed the local handoff. D9 and D10 record the conservative interpretations of canonical bytes, metadata, and validation. No external facts are required for A1.
- [Implementer] Writing tests before the trace code.
- [Verifier] Preparing independent tests and mutation probes in parallel with implementation, at the human's request. Final checks will run against the finished code.
- [Skeptic] Reviewing specification and coverage in parallel. Final audit follows the Verifier's evidence.
- [Implementer] Captured the missing-module RED before creating the code. Added the shared model types and trace functions. The unchanged targeted suite is green; both runs are in `results/a1/`.
- [Verifier] Running the suites, independent canonical-byte and round-trip probe, protected-path comparison, and in-memory mutation checks.
- [Verifier] All initial suites passed; the independent byte probe agreed and three deliberately broken variants were detected.
- [Skeptic] Found a concrete round-trip issue: distinct strings containing surrogate code points and a valid Unicode character serialize to the same bytes. Returned to Implementer for one tests-first correction; no test expectations will be loosened.
- [Implementer] Adding regression coverage and a narrow check for surrogate code points in string values and keys.
- [Verifier/Skeptic] The subagents hit their usage limit after the fix handoff. The primary agent ran the independent probes again on the final code and verified the Unicode repair, including failure when the repair is removed in memory. No A1 finding remains open.

Tests: `tests_vh/test_trace.py` covers the required event schema, nested structures, sequence, manual hash bytes, key order, recognized metadata boundary, malformed records, preservation of valid Unicode, and JSONL round-trip. Evidence includes the original missing-module RED and the Unicode RED before each corresponding fix.

Verify (Python 3.12 with bytecode writes disabled):
- `python -m unittest tests_vh.test_trace -v` → `Ran 15 tests`, `OK`.
- `python -m unittest discover -s tests -t .` → `Ran 34 tests`, `OK`.
- `python -m unittest discover -s tests_vh -t .` → `Ran 20 tests`, `OK`.
- `git diff --stat -- ldp tests` → empty. Protected paths and hashes match the baseline. See `results/a1/verification.txt` and `results/a1/unicode_verification.txt`.

Break-it (in memory): including event `meta`, not sorting JSON keys, dropping the sequence guard, and dropping the Unicode guard each failed its corresponding test; each restored test passed. See `results/a1/break_it.txt` and `results/a1/implementer_unicode_red.txt`. Full simulated call replay determinism (I4) remains scheduled for A9.

Suggested commit message: `Add validated JSONL traces and deterministic event hashing`.

## Task A2 — Mock staging backend and tools — DONE — PASS

Plan:
- [Researcher] Use the stage-only tool contract in D11 without external services.
- [Implementer] Write backend and schema tests first; implement the two allowlisted mock tools.
- [Verifier] Verify failure before mutation, state snapshots, hashes, and no audit for read-only calls; rerun both suites.
- [Skeptic] Review scope and recorded evidence before advancing to A3.

Hat log: [Researcher] D11, local synthetic fixture only. [Implementer] `tests_vh/test_backend.py` ran before code and failed on the missing backend; the same tests passed after adding the two tools. [Verifier] Targeted `Ran 8 tests`, harness `Ran 28 tests`, existing `Ran 34 tests`, all `OK`; protected Git diff empty. [Skeptic] Verified only mock staging is actionable; reads do not change state, and a failed rollback leaves no mutation or audit entry. No live requests.

Break-it: bypass first-call timeout in memory → timeout-without-mutation test failed → restored and passed. A non-staging fixture was refused. Evidence: `results/a2/`. Suggested commit: `Add a validated mock staging backend and rollout tools`.

## Task A3 — Seeded speech recognition faults — DONE — PASS

Plan:
- [Researcher] Read the local injection rules and adapt the service-name example to staging; no external claims about ASR accuracy.
- [Implementer] Write tests first for probability boundaries, seeded replay, individual faults, undo, and a small staging snapshot.
- [Verifier] Run both suites; change RNG draw order in memory and verify the snapshot fails.
- [Skeptic] Confirm outputs are synthetic and repeatable and that the log can reconstruct the reference.

Hat log: [Researcher] D12 pins edit offsets and the synthetic service fault. [Implementer] `tests_vh/test_faults.py` failed before `vh/faults.py` existed. [Verifier] Targeted `Ran 6 tests`, harness and existing suites each `Ran 34 tests`, all `OK`; protected diff empty. Moving the kind draw before the probability draw in memory failed the seed-one snapshot, then it passed on restoration. [Skeptic] The snapshot came from separately hand-traced RNG draws, is available for human review, and has not been claimed human-reviewed; the measured behavior is only that of the simulator.

Evidence: `results/a3/`. Suggested commit: `Inject seeded speech faults with reversible logs`.

## Task A4 — Spoken release numbers — DONE — PASS

Plan:
- [Researcher] Verify useful spoken forms and document the staging scope.
- [Implementer] Pin handwritten examples and negative cases before code; implement a normaliser and lossless read-back formatting for release identifiers.
- [Verifier] Run exact examples and deterministic round trips, exercise a broken repetition rule, then run both suites.
- [Skeptic] Flag missing held-out evidence and any overstatement about real recognition accuracy.

Hat log: [Researcher] R6 and D13 ground the small English staging grammar. [Implementer] Wrote the expected CSV and tests before the normaliser (`results/a4/red.txt`). [Verifier] Targeted `Ran 6 tests`, harness `Ran 40 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Changing the double rule in memory made the CSV test fail, then restoration passed. [Skeptic] `no held-out set yet`; no real speech accuracy is inferred.

Evidence: `results/a4/`. Suggested commit: `Normalize spoken release identifiers without guessing unsupported numbers`.

## Task A5 — Mock speech timing and barge-in — DONE — PASS

Plan:
- [Researcher] Use the verified simulation timing from `ldp.model.Params` (R5); no external call.
- [Implementer] Test word spans and cut boundaries before implementing the stateless speech mock.
- [Verifier/Skeptic] Verify exact completed prefixes, attack the rounding behavior, and check both suites.

Hat log: [Researcher] Imported `Params` from `ldp`; no audio or real clock. [Implementer] Missing module RED before implementing. [Verifier] Targeted `Ran 3 tests`, harness `Ran 43 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Counting partly spoken words in memory failed the cut test and restoration passed. [Skeptic] Describes only simulated word timing; a spoken prefix joins complete words with one space. Runtime history enforcement remains A9.

Evidence: `results/a5/`. Suggested commit: `Model speech timing and cut at complete word boundaries`.

## Task A6 — Confirmation, controls, and staging read-back — DONE — PASS

Plan:
- [Researcher] Use the local confirmation precedence and staging contract (D11, architecture section 5).
- [Implementer] Write a manual classification table and template checks, then implement the parser and staging templates.
- [Verifier/Skeptic] Test negation priority and proofs that formatted read-back includes both arguments. Full runtime gating remains A9.

Hat log: [Researcher] Local parser rules and D11. [Implementer] Confirmation cases and exact template test preceded `vh/confirm.py`. [Verifier] Targeted `Ran 4 tests`, harness `Ran 47 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Prioritizing yes over no in memory failed the manual table; restored test passed. [Skeptic] These are parser and formatting results only; the runtime gate is still pending.

Evidence: `results/a6/`. Suggested commit: `Classify confirmation conservatively and render staging read-backs`.

## Task A7 — Staging scenarios and scripted caller — DONE — PASS

Plan:
- [Researcher] Use D11 to pin synthetic initial and expected states, and the independent random streams from the architecture.
- [Implementer] Write scenario and caller expectations first; then add the scripted cases and reactive caller.
- [Verifier/Skeptic] Check exact fixtures, matching vs. mismatched confirmation, retry limit, and independence of random streams.

Hat log: [Researcher] D11/D14 fixture and fixed fault; separate seeded streams. [Implementer] Scenario tests failed on the missing modules before code. [Verifier] Targeted `Ran 5 tests`, harness `Ran 52 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Replacing the reactive caller with unconditional yes failed the mismatch test and restoration passed. [Skeptic] A fixed fault is logged in every mode, and is not represented as measured speech data.

Evidence: `results/a7/`. Suggested commit: `Add replayable staging scenarios and a reactive synthetic caller`.

## Task A8 — Scripted models and prompts — DONE — PASS

Plan:
- [Researcher] Translate the local trap model definitions to the staging tools (D15).
- [Implementer] Test the oracle, trap responses, and exact prompt diff before implementation.
- [Verifier/Skeptic] Check that only one paragraph changes and that each adversarial response is observable; runtime outcomes remain A9/A12.

Hat log: [Researcher] Local trap definitions and D15. [Implementer] Wrote model and prompt tests before the models existed. [Verifier] Targeted `Ran 8 tests`, harness `Ran 60 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Replacing the wrong-argument trap with the oracle failed the designated test; restoration passed. [Skeptic] These are synthetic outputs only. The prompt comparison adds only one paragraph.

Evidence: `results/a8/`. Suggested commit: `Add staging oracle, fault models, and a prompt-only comparison`.

## Task A9 — Stepwise simulation and confirmation gate — DONE — PASS

Plan:
- [Researcher] Recheck the ledger contract (R5), exact gate rules, event envelope, and the adapted staging cases (D11/D14/D15).
- [Implementer] Write executable invariant tests before adding `CallSession` and the scripted event loop.
- [Verifier] Run the scenario and invariant tests and deliberately break I1–I7 in memory; rerun both suites and check protected files.
- [Skeptic] Review that the runtime uses confirmed arguments, only speaks verified results, and never treats simulated inputs as real audio.

Hat log: [Researcher] Rechecked R5 and D11/D14. [Implementer] Recorded missing-module RED, then fixed correction-message ordering and blocked uncertainty from counting as approval (D16). [Verifier] Targeted `Ran 14 tests`, harness `Ran 74 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. [Skeptic] Verified a fresh read-back on retry and that a blank or premature confirmation cannot change mock state.

Break-it (`results/a9/break_it_probe.py` / `break_it.txt`):
- I1 immediately execute → `test_I1_waits_for_confirm_and_bare_does_not` failed → restored and passed.
- I2 reuse model speech → `test_I2_ignores_model_readback_when_arguments_disagree` failed → restored and passed.
- I3 append unheard speech → `test_I3_history_keeps_only_completed_prefix_after_cut` failed → restored and passed.
- I4 add wall time to hashed data → `test_I4_determinism` failed → restored and passed.
- I5 speak model success over a timeout → `test_I5_never_speaks_success_for_timed_out_tool` failed → restored and passed.
- I6 remove call ID guard → `test_I6_reusing_a_dispatched_call_id_cannot_change_release_again` failed → restored and passed.
- I7 mutate backing state outside a successful tool event → `test_I7_replaying_successful_tool_records_reconstructs_state` failed → restored and passed.

Suggested commit: `Enforce staging confirmation and audit simulated action execution`.

## Task A10 — Independent trace checks — DONE — PASS

Plan:
- [Researcher] Read evaluation rules and record the staging read-back comparison and single-trace limitation (D17).
- [Implementer] Test handcrafted clean and bad traces, then build standalone checks and CLI.
- [Verifier/Skeptic] Verify that the CLI fails on a violating harness trace, that audit code imports no runtime, and that both test suites remain green.

Hat log: [Researcher] D17 and the local evaluation spec. [Implementer] Wrote handcrafted trace tests before adding the check module. [Verifier] Targeted `Ran 7 tests`, harness `Ran 81 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. The CLI accepted a clean fixture and returned exit 1 for the same trace missing the gate yes. AST inspection found no runtime import in `vh/checks.py`; the checker found no violations for the four oracle harness traces. [Skeptic] I4 repetition is separately tested under A9. False-success text detection in unmanaged arms remains a heuristic.

Evidence: `results/a10/`. Suggested commit: `Audit staging trace safety and replay independently of runtime`.

## Task A11 — Ollama adapter and offline cache — DONE — PASS

Plan:
- [Researcher] Ground the native request and response format, local model discovery, and the limits of replay and cost knowledge.
- [Implementer] Write transport and cache tests first; implement a bounded stdlib client with recording and replay.
- [Verifier/Skeptic] Verify retry and request budgets, secret removal, live-to-replay trace identity on a fake server, and no paid inference.

Hat log: [Researcher] R1–R3 and D18 ground the request, local metadata, and strict budget boundary. [Implementer] Missing-module RED first. [Verifier] Targeted `Ran 8 tests`, harness `Ran 89 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Synthetic requests validated both argument shapes, bearer handling without disclosure, no IO on replay miss, and one budget unit per retry; recorded replay preserved trace hash. [Skeptic] One additional generation was run on the verified loopback model only: completed and reproduced from its recording, but did not emit the requested tool call. Tool-call results on real models are unverified; no hosted/cloud generation was performed in this continuation. See `results/a11/local_smoke.txt`.

Evidence: `results/a11/`. Suggested commit: `Add guarded local Ollama requests and deterministic record/replay`.

## Task A12 — Benchmark and generated report — DONE — PASS

Plan:
- [Researcher] Use the existing scripted validity checks and the scoped staging grid/output rules (D19).
- [Implementer] Write tests for statistics, deterministic smoke runs, the request cap, and report content first.
- [Verifier] Run and compare smoke outputs, run the full scripted grid, inspect validity checks and audit actual saved traces.
- [Skeptic] Verify the catch sweep, independent counts, and the separation of scripted evidence from Ollama and speech claims.

Hat log: [Researcher] D19 records staging design and separated output. [Implementer] Statistics and CLI tests preceded implementation. [Verifier] Targeted benchmark and stats passed, harness `Ran 93 tests`, existing `Ran 34 tests`, all `OK`; protected diff empty. Two smoke CSVs and reports were byte-identical. The full scripted grid saved 1944 run rows and passed V1, V2, V2b and the standalone trace audit; local and hosted generation count was zero. [Skeptic] Independently recomputed the V1 cell from CSV as `12/12` and read all events in five samples: prompt-only confirmation, correction and supersession, cancellation and spoken prefix, safe timeout speech, and duplicate bare dispatch. See `results/a12/full_grid.txt` and `results/vh/traces/`. Full traces can be regenerated from the exact grid; the workspace retains review copies.

Suggested commit: `Benchmark staging confirmation modes with reproducible evidence`.

## Task A13 — Scoped failure attribution — DONE — PASS

Plan:
- [Researcher] Use the documented trace-only heuristic and scoring boundary in D20.
- [Implementer] Test the rules with handcrafted stripped traces; then add attribution and its benchmark table.
- [Verifier/Skeptic] Check the hidden-fault guard, verify false attribution is disclosed, and regenerate benchmark evidence without changing the scenarios or grid.

Hat log: [Researcher] D20 pins ground truth and heuristic scope. [Implementer] Tests preceded the module. [Verifier] Targeted `Ran 5 tests`, harness `Ran 98 tests`, existing `Ran 34 tests`, all `OK`. Repeated the full grid and saved trace audit; all shipped review trace bytes match the rerun. [Skeptic] Independently recomputed the oracle harness no-fault false alarms from the CSV (15/30); T9 reports rather than hides this weakness. The heuristic is diagnostic only and is never used to approve or route a rollback.

Evidence: `results/a13/` and T9 in `results/vh/RESULTS.md`. Suggested commit: `Report scoped failure attribution with explicit false alarms`.

## Task A14 — README and numbers check — PASS (automated; human read-through pending)

Plan:
- [Researcher] Use generated evidence and the original honesty rules, adapted to the staging scope.
- [Implementer] Test the number guard before building it; write the README and copy the validity table from generated output.
- [Verifier/Skeptic] Run the guard, verify evidence and protected paths, and flag the remaining human read-through separately from completed agent work.

Hat log: [Researcher] The README uses the adapted staging limits and copies the validity table verbatim. [Implementer] The guard tests failed before adding the script and passed afterward. [Verifier] `python -m unittest tests_vh.test_readme_numbers -v` reported `Ran 2 tests`, `OK`. Full harness and existing suites reported `Ran 100 tests` and `Ran 34 tests`, both `OK`. `python scripts/check_readme_numbers.py` and `python scripts/check_invariants.py results/vh/traces` passed. The final SHA check matched the original repository files and unchanged Git HEAD. [Skeptic] All README links resolve, delivered trace hashes match the CSV, and no real speech, cloud benchmark, model tool performance, or human review is claimed.

Evidence: `results/a14/`, `README_VH.md`, `results/vh/RESULTS.md`. Suggested commit: `Document the staging harness, evidence, and limits`. No commit or push performed. Agent work finished for Plan A; the maintainer's read-through is still pending.

## AUDIT

Skeptic verdict: PASS for A0 only. Plan A is a SIMULATION (no real audio). This task adds no runtime safety feature or harness benchmark result; setup outputs are operational evidence, not performance claims (D4).

- T1 — DEFERRED to A6/A9: no harness read-back exists in A0; no claim about `shown_args` enforcement.
- T2 — DEFERRED to A13: no attribution implementation exists; no use of hidden fault labels added.
- T3 — DEFERRED to A8/A9: no harness oracle or gate exists; no special oracle path added.
- T4 — PASS: A0 expected outcomes are handwritten from the task and asserted on real objects. Package import is an independent setup condition. Red/green logs and mutation failures demonstrate the tests can fail.
- T5 — NOT APPLICABLE to A0; no normaliser dataset is created. Explicit status: "no held-out set yet". Dev/held-out separation belongs to A4.
- T6 — DEFERRED to A10/A12: no task-success measurement added; the ledger contracts do not claim backend success.
- T7 — DEFERRED to A8: no model prompts or comparison arms added.
- T8 — DEFERRED to A7/A12: no paired harness grid run. R5 only probes the existing bootstrap's repeatability, not future bench determinism.
- T9 — DEFERRED to A11/A12: no live model call, model error rate, or model result produced.
- T10 — DEFERRED to A11/A12: no live/replay runs produced or combined.
- T11 — DEFERRED to A12: no wrong-commit headline or catch sweep produced.
- T12 — NOT APPLICABLE to A0: no harness README/report claim added; `scripts/check_readme_numbers.py` belongs to A14 and does not exist yet. Existing README and results report hashes match the captured baseline. Do not interpret this as an A14 pass.
- T13 — PASS for A0 artifacts: independently scanned text files under `vh/`, `tests_vh/`, `bench/`, `scripts/`, `demo/`, and `results/a0/` for credential assignments, OpenAI-style and GitHub-style token patterns; no matches. Environment-key comparison was not applicable because the variable is unset. Output: `Skeptic T13: executable/setup artifact assignment and token-pattern scan empty; environment-key comparison not applicable (key unset)`. A repository literal-name scan matches only the immutable `docs/vh/05_VERIFICATION.md` instruction containing its own placeholder. That documentation match is not a credential assignment and was not deleted or concealed. No trace/cache or actual credential was generated; future adapter leak testing remains A11.
- T14 — PASS: `git diff --stat -- ldp tests` is empty; hash/path-set baseline checks also cover untracked additions and existing bytecode. No protected source or spec changed.
- T15 — PASS for A0: no harness scenarios, faults, rules or model results exist to tune. No post-result tuning performed. Future changes must still be recorded in DECISIONS.md.

Section 2 future break-it checks: I1–I7 are explicitly DEFERRED to A9; normaliser, fault RNG and confirmation-classifier attacks are DEFERRED to A4, A3 and A6 respectively. Their implementations/tests do not exist in A0. Only the A0 contract mutations above were exercised; no future invariant is marked verified.

Section 4 result audit:
- Smoke grid twice / byte-identical `runs.csv` — DEFERRED to A12; harness bench does not exist yet.
- Manual trace review across modes and specified scenarios — DEFERRED to A9/A12; no harness traces produced.
- Independent trace-invariant script — DEFERRED to A10; no invariant audit claim made.
- Recompute a report cell from `runs.csv` — DEFERRED to A12; no harness table or README claim created.

Applicable open findings: none. D1's deferred host selection is documented and nonblocking for this task. Final task verdict: DONE — PASS. Stop before A1.

### A1 audit

T4: manual literal hash bytes and schema fixtures. T13: synthetic evidence, no credentials or cloud calls; future emitters must sanitize metadata before storing it. T14: protected Git diff empty and byte hashes unchanged. T15: no measured model outcome to tune against. T1–T3, T5–T12 and the result audit do not apply to the trace codec and remain with the scheduled feature tasks. No latency or model performance claim.

### Final Plan A audit

- T1/T3/T6: exact confirmed arguments, common runtime path, and task success checked through mock state and successful mutation audit. The in-memory invariant attacks were all detected.
- T2: attribution refuses input containing the injected fault field; scoring is confined to the benchmark. T4: hand-authored fixtures and separate tests are retained. T5: no held-out set exists; the report states that explicitly.
- T7/T8: the prompt difference is one paragraph; seeds and cases are paired. T9/T10: model errors are excluded visibly, and routes are reported separately. A local Ollama check returned text but did not show tool behavior; the full grid was entirely scripted.
- T11/T12: the generated report includes the caller catch sweep; README numbers pass the guard and the validity table matches the generated text exactly.
- T13: fake credential echo and cache/trace scan tests passed; no real key was stored in the evidence. T14: original source, tests, README, and results hash to the baseline; no protected Git diff. T15: staging scope and timed cancellation were recorded before the full grid; attribution and route labels were documented add-ons, not scenario tuning.
- Report audit: two smoke comparisons are byte-identical, five representative traces were read, the full trace audit passed, and the V1 cell and attribution false-alarm counts were independently checked from CSV. Evidence is under `results/a12/`, `results/a13/`, and `results/a14/`.

## BLOCKED
(None yet.)

## Plan B — Local staging browser demo

User authorized continuing without inter-task prompts. A14 human read-through stays pending as a separate review. Independent research, UI preparation, and adversarial test preparation run in parallel; final checks use the integrated source.

### B0 — Research and decisions — PASS
- [Researcher] Check browser speech, SSE, and dependency pins with official sources and probes.
- [Implementer] Record the loopback, speech acknowledgment, and budget decisions in D21.
- [Verifier/Skeptic] Distinguish mock checks and actual microphone/browser observation.
- Verified real loopback SSE/POST concurrency and the pinned disposable JSX build. R7 remains PARTIAL pending real microphone and browser-provider testing. See R7–R9 and D21.

### B1 — Loopback server — PASS
- [Researcher] R8/D21. [Implementer] Missing-server RED preceded stdlib HTTP/SSE and external playback support. [Verifier/Skeptic] Separate core and adversarial HTTP tests passed on ephemeral loopback. Checks cover playback identity, rejection of early confirmation, prefix validation, resumable SSE, replay isolation, redaction, and hosted model refusal.
- Suggested commit: `Serve synthetic staging sessions with explicit playback acknowledgments`.

### B2/B3/B6 — Browser client, speech adapters, typed fallback — PASS (automated and typed browser flows)
- [Implementer] Built the local console against the loopback API. Acknowledgment of displayed speech is distinct from confirming an action.
- [Verifier] Observed the typed read-back hold the release at v12, then a separate yes change it to v11. Tested synthesis boundary prefixes, invalidated callbacks, and recognition restart with fake browser events. `npm test`: 7 passed. `npm run build`: successful. Native microphone access, recognition and word boundaries remain PARTIAL, with the device checklist in `demo/MANUAL_TEST.md`.
- Suggested commit: `Add a typed and optional speech staging console`.

### B4 — Synthetic script scoring — PASS
- [Implementer] Authored rejected-input, opt-in, matching and typed exclusion tests before `vh/demo_score.py`. [Verifier] Targeted suite: `Ran 3 tests`, `OK`. Free speech and typed inputs do not persist samples.
- Suggested commit: `Compare spoken release digits with opt-in synthetic samples`.

### B5/B7 — Saved replay and mode comparison — PASS
- [Verifier] Replayed the shipped S2 trace to its expected v11 outcome in the browser and checked that replay endpoints do not mutate a live room. The scripted comparison showed bare v10 and harness v11. The browser displayed the generated scripted benchmark counts separately. Screenshot: `results/b1/browser-comparison.jpg`. The UI reads scoreboard aggregates directly from the benchmark CSV to avoid a second stale results file.
- Suggested commit: `Show audited rollback replay and side-by-side mode outcomes`.

### B8 — Calibration counter — PASS (tool only)
- [Verifier] Handwritten swap, drop, insertion, substitution and service mutation cases passed. The counter reported `No opted-in voice attempts recorded; calibration was not measured.` No real recognizer result was added to the scripted Plan A report.
- Suggested commit: `Count discrepancies in opted-in synthetic speech samples`.

### B9 — Local runbook and final verification — PASS with documented verification limits
- [Implementer] Added `demo/README.md` and `demo/MANUAL_TEST.md` with startup, browser fallback, calibration, and screen-recording guidance.
- [Verifier] Offline test pass: 106 harness/demo unit tests and 34 original tests; saved trace audit, README number guard, and protected Git diff checks passed. Earlier, 3 core HTTP and 5 adversarial loopback tests passed on ephemeral ports. A final combined loopback rerun was not executed: automatic approval review hit its usage limit. After the earlier runs, a no-socket test verified explicit playback stops in both modes and the final browser build exercised the typed route, comparison, replay, and benchmark view. Evidence: `results/b9/python-verification.txt`.
- [Skeptic] No demo Ollama calls, microphone recording, external publishing, commits, or pushes. Preview server stopped. Native speech and the maintainer read-through are pending manual checks, not claims about device compatibility.
- Suggested commit: `Document and verify the local staging lab demo`.
