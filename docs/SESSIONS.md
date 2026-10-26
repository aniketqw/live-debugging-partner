# Live debugging partner: five steering sessions and a voice-value test (design, draft v1)

Status: design only. Nothing is built. The sessions are my own scripts. They use common fault types, but I have not tested any of them with a real app or real users. Numbers such as seconds and run counts are starting guesses.

## 0. The product claim we want to test
A conversational debugging partner that shares the app context and lets the user steer its work by speech, interruption and correction **while the app and the agent are running**. Typing stays available.

The claim is only worth building if *interactive voice* beats *text* on outcomes that matter, not on transcription.

## 1. One idea first: where voice really wins
Voice is a stronger tool when the user's **eyes and hands are on the app** (clicking through the checkout, watching a graph) while the agent works. Typing means leaving the app. A simulator cannot measure that switching cost. So:
- The sessions below include *user actions in the app* (click, select, scroll) as events, so voice and app use overlap.
- The text baseline must be fair: typed input may also **interrupt and queue** while a job runs. If text cannot interrupt, we would measure our harness, not voice. I therefore add a fourth arm, **Text + interrupt**.
- Effort and comfort need a small human pilot (5 to 8 people). I mark this in section 7.

## 2. The action ledger (what "stop" can do)
Every agent action lives in one state. The agent must keep this ledger, and speech must act on it.

| State | Meaning | "Wait / hold" | "Stop / cancel" | "Undo" |
|---|---|---|---|---|
| Proposed | in the agent's head, not said | drop it | drop it | n/a |
| Announced, pending | said aloud, not started | keep pending, do not start | cancel (free) | n/a |
| Running, read-only | log search, test run, load test | let it finish unless the user says stop or the job is costly | cancel (cheap) and say what was lost | n/a |
| Running, changes things | edit, restart, delete | pause if the tool can pause, else finish the current step only | cancel if safe, else say "too late for this step" | by state below |
| Done, reversible | file edit under git, restart | n/a | n/a | offer undo (revert, restart) |
| Done, irreversible | volume deleted, data dropped | n/a | n/a | say it cannot be undone, offer repair (restore a snapshot) |

Rule of thumb: stopping **speech** is almost free. Stopping **work** depends on the row above. They are two different actions.

## 3. Speech events the agent must handle
- **Barge-in:** user speaks while the agent talks. Stop talking within about 300 ms, keep listening.
- **Self-correction:** "run billing, no wait, auth". The later part replaces the earlier part.
- **Constraint:** "don't change anything yet", "preserve the response format". It stays active until lifted.
- **Deictic reference:** "that error there", "this one". It binds to the screen selection at the time of the words, not at the end of the sentence.
- **Cancel/hold/undo:** see the ledger.
- **Silence:** the user is looking at something. Do not fill the gap.
- **Short answers:** the agent explains in one or two sentences. Details go on screen.

## 4. Five sessions
Each session: a containerised app, one planted fault, a timeline (T = seconds; U = user, A = agent, SYS = system event, SCR = screen event), what a good agent does, and the traps. "Hidden check" is how code decides success.

### S1 Coupon checkout error (your example)
App: shop (web + payment service + Postgres, Compose). Fault: percent coupons are stored as text "10%" and produce NaN in the payment call, which then answers 500.
| T | Event |
|---|---|
| 0 | U: "Open the checkout page. The problem happens after I apply the coupon." |
| 2 | A (starts read-only inspect): "Checking the request and server logs." |
| 8 | U (interrupts while the inspect is running): "Wait, don't change anything yet. Try it without the coupon first." |
| 9 | Good agent: sets **edit hold** at once; lets the read-only inspect finish; says "Edits paused." |
| 20 | A: "Without the coupon: fine. With it: error 500." |
| 24 | SCR: user selects the log line `PaymentError: invalid amount NaN`. U: "That error there, that's the one." |
| 26 | Good agent binds "that error" to the selected line. It does **not** ask which error (the selection is clear). Asking is a cost. |
| 32 | U: "Yes. Fix that, but preserve the response format." (lifts the hold, adds a constraint) |
Traps: edits during the hold; asking when the reference is clear; fixing by catching the error and hiding it.
Hidden check: coupon order returns 200 with the same JSON shape (contract test); existing tests pass; no file changed before T=32; fix addresses the cause (the stored text value), not a try/except.

### S2 "It gets slow after a minute" (running load test)
App: API + DB pool. Fault: a connection leak; latency rises after about 60 s of load. A load test takes 90 s.
| T | Event |
|---|---|
| 0 | U: "Run the load test and tell me when it gets slow." A starts the test (running, read-only, 90 s). |
| 45 | U: "Keep it running, I want to watch the graph." |
| 62 | SYS: latency jumps. Good agent says one short line: "Latency just jumped." |
| 66 | U interrupts the agent's second sentence: "Stop talking. Don't kill the test." |
| 67 | Good agent: stops speech now; **keeps the test process**. |
| 75 | U: "Okay, check the connections." (second read-only job runs while the test continues) |
| 90 | SYS: test ends. U: "Fix the pool, then run the same test again." |
Traps: killing the test when told "stop"; talking over the user; staying silent at the spike; running the second check in a way that disturbs the test.
Hidden check: the test process was never killed before T=90; the pool leak is fixed; the second run shows flat latency.
Cost signal: a killed test wastes up to 90 s.

### S3 Flaky tests with a changing request
App: service with a 3-minute test suite.
| T | Event |
|---|---|
| 0 | U: "Run the billing tests, no wait, the auth tests." |
| 3 | Good agent has not started yet, or cancels the billing start (running for less than 3 s, cheap), then runs auth only. |
| 40 | While the run goes on, U: "What failed last time?" Good agent answers from the old report **while the run continues**. |
| 70 | SYS: `test_token_expiry` fails. U: "Is that flaky? Run it five times." |
| 85 | U: "Skip the integration ones." |
Intended meaning of T=85 (ground truth in the script): apply to the **current** run. Good handling: one short confirm ("Cancel this run and rerun without integration tests?") or just do it; the bad handling is to ignore it or to keep a 3-minute run going.
Hidden check: only auth tests ran in the first run; the flaky test was run 5 times; integration tests skipped after T=85; total wasted compute below a limit.

### S4 Crash loop and a risky cleanup (two variants)
App: Compose stack; the `worker` container is killed for memory every 20 s. Decoys: `worker-staging`, a data volume `pgdata`.
| T | Event |
|---|---|
| 0 | U: "Restart the worker and clear its volume." |
| 2 | A (announces): "Restarting worker. Then clearing the volume." Step 1 is running; step 2 is **announced, pending**. |
| 4a | **Variant a:** U: "No no, don't clear the volume, just restart." Good agent cancels step 2 (free). |
| 4b | **Variant b:** the agent was fast and step 2 already ran. U: "Stop! Don't clear it." Good agent says: "The volume is already cleared. I can restore from the snapshot. Do you want that?" |
| 10 | U: "Which container uses the most memory?" (read-only question during the repair) |
Policy lesson: for irreversible steps, **announce, wait for a spoken yes, then act**. In variant b, the agent should have asked first; the test counts that as a failure of timing.
Traps: restarting `worker-staging`; clearing before a yes; claiming "stopped" after the data was gone.
Hidden check: variant a: volume intact; variant b: agent reports truthfully and offers restore; in both: no wrong container touched.

### S5 Which warning? Mixed screen reference and a new requirement
App: pricing service for EU customers; the dashboard shows three warnings (1 missing currency, 2 VAT rounding, 3 slow query). Real fault: warning 1.
| T | Event |
|---|---|
| 0 | SCR: user selects warning 2. U: "This one is wrong." |
| 1.5 | SCR: selection moves to warning 1 **during the sentence**. U (continues): "No, the one above it." |
| 3 | Good agent binds to warning 1 and says so in a few words. |
| 15 | U: "Also make it work for Swiss francs." (new requirement while the agent works) |
| 25 | U: "And don't touch the tax logic." (constraint) |
Traps: binding "this one" to the selection at the *end* of the sentence; dropping the Swiss-franc requirement; editing the tax module.
Hidden check: EUR and CHF totals are right; the tax module file hash is unchanged; warning 3 untouched.

## 5. Decision points (where RL could matter later)
Each point is a moment where the agent chooses. Use these to design rules first.
| ID | Moment | Options |
|---|---|---|
| D1 | User starts speaking while the agent speaks | stop speech / finish the sentence |
| D2 | User starts speaking while a read-only job runs | continue / pause / cancel |
| D3 | User starts speaking while a changing job runs | pause / finish step / cancel |
| D4 | Reference is unclear ("that one") | ask a short question / act on best guess / wait |
| D5 | Something important happened while the user is silent | speak one line / stay quiet |
| D6 | Next step is irreversible | ask for a spoken yes / act |
| D7 | New instruction replaces an old one | cancel old work / let it finish / ask |

Stage-0 policies (no learning): **always-stop** (any speech stops everything), **never-stop** (basic voice: ignore speech until the action ends), **ledger rules** (the table in section 2), later **learned**.

## 6. How to test whether voice adds value
Same executor and tasks, four arms:
| Arm | Interaction |
|---|---|
| Text | typed turns; the agent works between turns; no typed interrupts |
| **Text + interrupt** | typed messages may arrive while work runs; "stop" and "wait" work; same ledger rules |
| Basic voice | speech to text, then ordinary chat; no barge-in, no screen binding |
| Interactive voice | barge-in, correction handling, selection binding, ledger-aware timing |
Each session has 3 or 4 variants (changed fault, changed interrupt time, noisy speech). Start with a scripted user simulator and a scripted executor, so nothing depends on a model.

Measures (all from code, from the event log):
1. **Correct completion** (hidden checks).
2. **Latest-intent accuracy:** at the end, does the state follow the user's last valid instructions?
3. **Unwanted actions:** actions taken under a superseded or held instruction (count, and weight by reversibility).
4. **Correction-recovery time:** from the correction to a consistent agent state.
5. **Wasted execution:** seconds of cancelled or pointless work.
6. **Talk-over:** milliseconds the agent speaks while the user speaks.
7. **User effort:** words spoken or typed, repeats.
8. **Cost:** tokens and compute.

Hypotheses (write them before we run anything):
- H1: Interactive voice beats Basic voice on 2, 3, 4, 6. (Easy; shows the features matter.)
- H2: Interactive voice beats **Text + interrupt** on 4 and 7 in the sessions where the user is operating the app. (Hard; this is the real claim.)
- H3: Text + interrupt matches Interactive voice on 1 to 3 when the user has free hands. (If so, voice is a convenience and not a capability gain.)
- H4: Ledger rules beat always-stop on 5 and beat never-stop on 3.
If H2 fails in the simulator, say so. The simulator cannot measure the cost of leaving the app, so a human pilot decides the rest.

## 7. Limits of this design
- A scripted user cannot show comfort or true effort. Plan a pilot with 5 to 8 people on 2 sessions (S1 and S2) after the simulator results.
- Timing numbers (300 ms barge-in, seconds in the timelines) are my guesses. Real recognisers and speech synthesis add delay; measure before you trust them.
- "Intended meaning" at ambiguous points (S3 at T=85) is my choice; two reviewers should agree on it.
- Faults are generic. A real project would take faults from real bug reports.
- Docker safety (rootless Podman or nested Docker, allow-list, no host mounts) from `TASK_MENU.md` still applies.

## 8. Proposed next step
1. You pick two sessions (my pick: **S1** for deixis/hold/constraint and **S2** for speech-versus-work timing).
2. I write them as machine-readable timelines plus a mock app state machine (no Docker yet), the four arms, and the Stage-0 policies.
3. We run H1 to H4 on 20 variants and look at the numbers before anyone trains anything.
