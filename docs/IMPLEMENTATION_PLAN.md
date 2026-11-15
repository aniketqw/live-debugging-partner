> Status: M0 to M4 are built in this repository, and all five sessions (not only S1 and S2). M5 to M7 (real Docker app, language-model executor, real speech, learned policy, human pilot) are not built. Code lives in `ldp/`, not `voiceops/live/`.

# Live debugging partner: implementation plan (v1, for review)

Status: plan only. Nothing in this file is built yet.
Inputs: `SESSIONS.md` (five sessions, action ledger, decision points D1 to D7, four arms, hypotheses H1 to H4), `PLAN.md` and `gym/` (earlier work we can reuse).

## 1. Goal of this build
Answer one question with numbers before anyone trains a model:
**Does interactive voice (barge-in, correction handling, screen binding, ledger-aware timing) beat Text + interrupt on the same tasks?**

We answer it in a simulator first. A simulator is cheap, repeatable, and needs no GPU, no speech API, and no Docker. Real audio, a real app, a language model, and RL come later and only if the simulator result is worth it.

## 2. Defaults I chose (change any of them)
| Choice | Default | Why |
|---|---|---|
| Sessions first | S1 (coupon checkout) and S2 (slow after a minute) | S1 tests holds, screen references and constraints. S2 tests speech versus work timing. |
| App | A **mock app** in Python (a state machine), no Docker yet | Fast and deterministic. Docker adds cost and safety work before we know the idea pays off. |
| Executor | **Scripted**, not a language model | Keeps the test about *interaction*, not about how well a model debugs. |
| Language understanding | Each scripted utterance carries its meaning label. Optional noise from `gym/speech.py`. | Separates "did the agent hear the words" from "did it handle the timing". |
| Time | Discrete events on a 100 ms clock | Fine enough for barge-in and talk-over. |
| Code | Python 3, numpy only, in `voiceops/live/` | Same as the gym. |
| Variants | 20 per session (40 in total) | Enough for bootstrap intervals. |

## 3. Architecture
```
 session script (JSON)          scripted user (reacts to the agent)
        |                                |
        v                                v
   [ clock / event loop, 100 ms ] <---> channel adapter (one of 4 arms)
        |                                |   text | text+interrupt | basic voice | interactive voice
        v                                v
   mock app (S1 shop, S2 API)      agent = policy + action ledger + scripted executor
        |                                |
        +------------> event log <-------+
                           |
                     metrics + hidden checks -> results table, timeline view
```

### Modules
| File | Job |
|---|---|
| `live/clock.py` | Event queue and 100 ms ticks. Every run is deterministic for a given seed. |
| `live/session.py` | Load a session script: utterances (text, start, word timings, meaning label), screen events (selection id, time), system events, the intent history (which instruction is current at each time), and hidden checks. |
| `live/ledger.py` | The action ledger from SESSIONS.md section 2. States: proposed, announced, running read-only, running changing, done reversible, done irreversible. Transitions for wait, stop, cancel, undo. Says what "too late" means. |
| `live/apps/shop.py` | S1 mock: checkout requests, logs, code files (with hashes), the coupon fault, a contract test for the response format. |
| `live/apps/api_pool.py` | S2 mock: load-test process (90 s), latency curve with the leak, connection counts, pool fix. |
| `live/executor.py` | Scripted executor: inspect logs, replay a request, edit a file, run tests, start or kill a process. Each action has a duration and a reversibility class. |
| `live/channels.py` | The four arms (section 4). |
| `live/speech_model.py` | Agent speech duration (words per second), user speech timing, talk-over measurement, optional word errors (reuse `gym/speech.py` confusions). |
| `live/usersim.py` | Scripted user: follows the timeline, answers clarifying questions, repeats when talked over, gets impatient if the agent is silent too long. All reactions are written into the script, not invented at run time. |
| `live/policies.py` | Decision rules for D1 to D7: `always_stop`, `never_stop`, `ledger_rules`, and later `learned`. |
| `live/metrics.py` | The eight measures from SESSIONS.md section 6, computed from the event log. |
| `live/run_experiment.py` | Runs arms x policies x variants, writes `results/*.json` and a summary table with bootstrap intervals. |
| `live/view_timeline.py` | Draws one run as an HTML timeline (user speech, agent speech, jobs, ledger states), to debug and to show you. |
| `live/tests/` | Unit and sanity tests (section 6). |

## 4. The four arms, defined so the comparison is fair
All arms use the **same** executor, mock app, and session. Only the input path changes.
| Arm | When the agent receives the user's message | Interrupt | Screen reference | Agent speech |
|---|---|---|---|---|
| Text | only when the agent's turn ends; typing takes time (about 40 words per minute) | no | selection at send time | written, no talk-over |
| Text + interrupt | as soon as the user presses send, also while work runs | yes, "stop" and "wait" work | selection at send time | written, no talk-over |
| Basic voice | after the user stops speaking plus recogniser delay | no barge-in; agent finishes its sentence | none | spoken; talk-over is counted |
| Interactive voice | speech start triggers barge-in; words arrive while spoken | yes | selection **at the time of each word** | spoken; stops on barge-in |

"Hands on the app": the script marks when the user is operating the app. Typing during those periods costs extra off-app time. This is an assumption with a parameter, and I report it separately so it cannot hide in the totals.

## 5. Milestones (each ends with a check and a short report to you)
| # | Build | Done when |
|---|---|---|
| M0 | Folder, clock, session format, ledger with unit tests | Ledger tests pass for every state and command (wait, stop, cancel, undo), including "too late". |
| M1 | S1 mock app, executor, scripted user, `ledger_rules`, Interactive voice arm | A reference run of S1 passes every hidden check. `always_stop` and `never_stop` each fail at least one named trap. |
| M2 | The other three arms, metrics, timeline view, 20 S1 variants | Metrics agree with hand-counted values on 3 runs. You get one timeline page to look at. |
| M3 | S2 mock app and 20 variants | Same checks as M1 and M2 for S2. A run that kills the load test shows the wasted 90 s. |
| M4 | Experiment: 4 arms x 3 policies x 40 variants, H1 to H4 | Results table with intervals. Each hypothesis is marked held, failed, or unclear. Written up as one page. |
| **Decision point** | You decide | Continue only if H1 to H4 show interactive voice is worth it. |
| M5 (later) | Real pieces, one at a time: Docker app for S1 and S2; a language model as executor; streaming speech (recogniser and synthesis); S3 to S5 | Same metrics, real delays measured. Needs your approval; the Docker safety design from TASK_MENU.md applies. |
| M6 (later) | Learned policy for D1 to D7 (bandit or RL) | Only if `ledger_rules` leaves a measurable gap. Same method as the gym: compare with rules and the best possible table policy. |
| M7 (later) | Human pilot, 5 to 8 people, S1 and S2 | Needs real audio and the real app. Measures comfort and true effort. |

## 6. How we test the simulator itself
- **Reference run passes, do-nothing fails** for every session variant (as in the gym).
- **Trap tests:** for each trap in SESSIONS.md, a policy built to fall into it must fail the matching check (for example, editing during the hold in S1, or killing the test in S2).
- **Determinism:** same seed gives the same event log byte for byte.
- **Metric checks:** hand-count talk-over, wasted seconds and unwanted actions on 3 runs per session and compare.
- **Fairness check:** with no interruptions in the script, all four arms must give the same completion. If not, the harness favours an arm.

## 7. What we reuse from the gym
- `gym/speech.py`: word confusions and confidences for optional recogniser errors.
- The test method: reference solution passes, do-nothing fails, wrong value fails.
- The results style: bootstrap intervals, ablations, "best table policy" as a ceiling.
- Not reused in Stage 0: the safety gate and the sandbox, because the mock app runs no real commands. They come back in M5.

## 8. Risks and how I handle them
| Risk | Handling |
|---|---|
| The simulator is built to make voice win | Write H1 to H4 before running; the fairness check in section 6; Text + interrupt as a strong baseline. |
| Scripted meaning labels hide real understanding errors | Label this limit clearly; add recogniser noise as a variant; real language model in M5. |
| Timing numbers are guesses | Keep them as parameters; run a sensitivity sweep (for example barge-in delay 150, 300, 600 ms). |
| Two sessions are too few | 20 variants each now; S3 to S5 in M5. |
| Results look good but users do not care | The human pilot in M7 decides. |

## 9. What I need from you before M0
1. OK to start with **S1 and S2**, a **mock app**, and a **scripted executor**?
2. OK to put the code in `voiceops/live/` next to `gym/`?
3. Any change to the four arms or the eight measures?
