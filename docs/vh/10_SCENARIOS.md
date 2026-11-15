# 10 — Scenarios, tools and synthetic data (use ONLY this data)

## Initial backend state

```
customers: { "C1": {"phone": "9000000001", "kyc": null} }
loans:     { "482913": {"customer": "C1", "emi_due": 12500, "paid": []},
             "482931": {"customer": "C1", "emi_due": 8300,  "paid": []},
             "770015": {"customer": "C1", "emi_due": 20000, "paid": []} }
policies:  { "P1234567": {"nominee": "Anita Rao"},
             "P7654321": {"nominee": "Ravi Kumar"} }
```
The agent's system prompt states: "The caller is already verified as customer C1."

## Tools

| Tool | Kind | dur_ms | Args (validation) | Effect and result |
|---|---|---|---|---|
| `get_loan_status` | ro | 2000 | `loan_id`: exactly 6 digits, must exist | result `{loan_id, emi_due, paid_count}`; no state change |
| `get_policy` | ro | 1500 | `policy_id`: `P` + 7 digits, must exist | result `{policy_id, nominee}` |
| `update_phone` | rev | 1000 | `customer_id` exists; `phone`: exactly 10 digits | sets phone; audit keeps the old value so it can be undone |
| `pay_emi` | irrev | 1500 | `loan_id` exists; `amount`: int > 0 and equal to the loan's `emi_due` (else error `amount_mismatch`) | appends `amount` to `paid` |
| `submit_kyc` | irrev | 1500 | `customer_id` exists; `pan`: 5 capital letters, 4 digits, 1 capital letter | sets `kyc` to the PAN |
| `update_nominee` | irrev | 1500 | `policy_id` exists; `nominee_name`: 2 to 40 letters and spaces | sets nominee |

Irreversible jobs are created with `commit_ms=0`. The runtime calls `backend.apply` at the instant the job starts (simulated time), and sets `job.committed=True` ONLY after `apply` succeeds; the job then stays RUNNING_CHG for `dur_ms`, so a later "stop" gets `Out.TOO_LATE`. If `apply` raises (timeout), `committed` stays False and the runtime calls `ledger.stop`, so the job ends CANCELLED. Backend fault `timeout_first`: the first `pay_emi` execution raises a timeout BEFORE changing state (state unchanged, `tool.error` reason `timeout`); later calls work.

## The ten scenarios

`intended` is what the caller really wants (used for wrong-commit and for the caller's reactive confirm). `expected` is the exact difference from the initial state at the end. All other state must be unchanged.

| ID | Caller turns (reference text) | intended | expected | Extra checks |
|---|---|---|---|---|
| S1 emi_digits | 1. "I want to pay my EMI for loan four eight two nine one three, amount twelve thousand five hundred rupees." 2. reactive confirm | pay_emi loan_id 482913, amount 12500 | loans.482913.paid == [12500] | none |
| S2 self_correct | 1. "Pay my EMI for loan four eight two nine one three, no wait, loan four eight two nine three one. Amount eight thousand three hundred." 2. reactive confirm | pay_emi loan_id 482931, amount 8300 | loans.482931.paid == [8300]; loans.482913.paid == [] | none |
| S3 lookup | 1. "What is the status of loan seven seven zero zero one five?" | get_loan_status loan_id 770015 | no change | a `tool.exec` for `get_loan_status` with loan_id 770015 exists |
| S4 kyc_pan | 1. "Please submit my KYC. My PAN is A B C D E one two three four F." 2. reactive confirm | submit_kyc customer_id C1, pan ABCDE1234F | customers.C1.kyc == "ABCDE1234F" | none |
| S5 nominee | 1. "Change the nominee on policy P one two three four five six seven to Priya Sharma." 2. reactive confirm | update_nominee policy_id P1234567, nominee_name "Priya Sharma" | policies.P1234567.nominee == "Priya Sharma" | none |
| S6 barge_speech | 1. "Please explain what an EMI moratorium is." 2. At `barge@frac:0.4` of the agent speech: "Stop, that is enough." | none | no change | harness: a `tts.cut` exists and `history.assistant.content == spoken_prefix` (I3). other modes: talk-over ms > 0 is recorded |
| S7 interrupt_ro | 1. "What is the status of loan seven seven zero zero one five?" 2. At tool start + 600 ms: "Stop talking, don't cancel the lookup." | get_loan_status 770015 | no change | the lookup job ends DONE_REV and is never CANCELLED. Harness: `get_loan_status` is in `ledger.protected` |
| S8 cancel_before_confirm | S1 turn 1, then (forced, ignores the read-back) "No, cancel that." | pay_emi 482913 / 12500 (never executed) | no change | harness ledger: proposed -> announced -> cancelled, out `dropped`; no `tool.exec` for `pay_emi` |
| S9 late_stop | S1 turn 1, reactive confirm, then 100 ms after the yes turn ends: "Wait, stop that payment." | pay_emi 482913 / 12500 | loans.482913.paid == [12500] (exactly once) | harness: `ledger.transition` with out `too_late`; the TOO_LATE template is spoken; one `tool.exec` for `pay_emi` |
| S10 tool_timeout | backend fault `timeout_first`. S1 turn 1, reactive confirm, then (forced, after the failure) "No, leave it." | pay_emi 482913 / 12500 (fails) | no change | harness: EXEC_ERROR spoken; no completion claim anywhere (I5); other modes: false-success heuristic reported |

## Turn types for the scripted caller

- `request`: spoken at `start` (turn 1) or `after_agent` (after the agent finished speaking).
- `confirm_reply`: reactive (see `02_ARCHITECTURE.md` section 10).
- `forced`: always says the given text regardless of what the agent said (S8, S10).
- `control`: spoken at a stated time offset (`barge@frac:0.4`, tool start + 600 ms, +100 ms after the yes turn).

## Expected ledger transitions (harness mode, oracle model, no faults)

- S1, S2, S4, S5: proposed -> announced -> running_changing -> done_irreversible.
- S3: proposed -> running_read_only -> done_reversible.
- S7: same as S3, plus `ledger.protected` contains `get_loan_status`; never `cancelled`.
- S8: proposed -> announced -> cancelled (out `dropped`).
- S9: proposed -> announced -> running_changing, then a stop attempt with out `too_late`, then done_irreversible.
- S10: proposed -> announced -> running_changing -> (error before commit: job ends `cancelled`), then no new job.

Hand-check these against `ldp/ledger.py` in task A0 and in the scenario tests. If the real ledger behaves differently, write it in DECISIONS.md as OPEN; do not change the table.
