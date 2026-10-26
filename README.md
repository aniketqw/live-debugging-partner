# Live Debugging Partner

A simulator that tests one question before anyone builds the real thing:

**When a voice agent works next to you on a running app, does interactive voice (barge-in, self-correction, "that error" bound to your screen, ledger-aware timing) beat a good text interface with an interrupt button?**

Today's coding agents work turn by turn. In real debugging you speak while you click, change your mind, and say "stop" while a command runs. This repository builds five realistic debugging sessions, four ways to talk to the agent, three decision policies, and the measures that show what changes. No GPU, no Docker, no speech service, and no third-party package is needed: Python 3 standard library only.

> Everything here is a **simulation** with scripted users, a scripted executor, and timing guesses. It tests the design. It does not show how real people feel. See [Limits](#limits).

## Quick start

```bash
python -m unittest discover -s tests -t .     # 34 tests, about 2 s
python -m ldp.experiment                       # 1,200 runs, about 15 s, writes results/
python -m ldp.experiment --quick               # 5 variants per session
```

Outputs: `results/RESULTS.md` (tables and hypothesis verdicts), `results/runs.csv` (one row per run), `results/hypotheses.json`, and `results/timelines/*.html` (open one in a browser to see a run as a timeline).

## The idea in one picture

```
 session script                         scripted user (reacts, repeats if ignored)
        |                                      |
        v                                      v
 [ clock, 100 ms ]  <-- channel (one of 4 arms) -->  agent = policy + action ledger + scripted executor
        |                                                    |
        v                                                    v
   mock app  <---------------------------- event log ---------------> metrics + hidden checks
```

**The action ledger** (`ldp/ledger.py`). Every agent action is in one state: proposed, announced (pending), running read-only, running changing, paused, done reversible, done irreversible, cancelled. Speech acts on that state: "stop" drops a pending step for free, cancels a read-only job cheaply, cancels a changing job only before its commit point, and can only report and offer repair after an irreversible step. Stopping *speech* is almost free. Stopping *work* is not.

**Four arms** (`ldp/channels.py`). Same app, same executor, same session. Only the input path differs.

| Arm | Message reaches the agent | Interrupt | Screen reference | Agent output |
|---|---|---|---|---|
| `text` | when the agent is idle; typing takes time | no | selection at send time | text |
| `text_interrupt` | as soon as sent, also while work runs | yes | selection at send time | text |
| `basic_voice` | final transcript, when the agent is idle | no barge-in | none (must ask) | speech, so talk-over |
| `interactive_voice` | clause by clause while speaking | yes, at speech onset | selection at the time of the word | speech, stops on barge-in |

A fifth arm, `oracle`, is interactive voice with zero lags. It proves that every session can be solved.

**Three policies** (`ldp/policies.py`), one per decision point D1 to D7 in [docs/SESSIONS.md](docs/SESSIONS.md): `ledger_rules` (the table above), `always_stop` (any speech stops everything), `never_stop` (ignore speech until the agent is idle). Eight broken variants of `ledger_rules` are the trap policies used by the tests.

**Five sessions** (`ldp/sessions/`), 20 seeded variants each (timing, speech speed, selection time):

| | Session | What it tests |
|---|---|---|
| S1 | Coupon checkout error | edit hold, "that error" bound to a log line, preserve the response format |
| S2 | Slow after a minute | speech vs a running load test: "Stop talking. Don't kill the test." |
| S3 | Flaky tests | "billing, no wait, auth"; a question during a run; "skip the integration ones" |
| S4 | Crash loop | an irreversible cleanup: announce, wait for a yes, or report honestly when too late |
| S5 | Which warning? | a selection that changes mid-sentence, a new requirement, a constraint |

**Measures** (`ldp/metrics.py`): completion, latest-intent accuracy, unwanted actions (weighted by reversibility), correction-recovery time, wasted execution, talk-over, user effort (words, input seconds, seconds off the app), repeats, clarifying questions, cost.

## What the simulator found (full tables in `results/RESULTS.md`)

Ledger rules, 100 session variants, mean over variants:

| arm | completion | latest intent | recovery (s) | talk-over (s) | input (s) |
|---|---|---|---|---|---|
| text | 1.00 | 0.40 | 35.3 | 0.0 | 25.1 |
| text + interrupt | 1.00 | 1.00 | 6.8 | 0.0 | 21.5 |
| basic voice | 0.80 | 0.21 | 35.4 | 2.1 | 14.9 |
| **interactive voice** | **1.00** | **1.00** | **3.2** | **0.24** | **11.9** |

- **H1 held.** Interactive voice beats basic voice on latest-intent accuracy, unwanted actions, recovery time and talk-over. This is the easy claim: basic voice cannot interrupt or bind to the screen.
- **H2 held, but only on speed and effort.** Against text + interrupt in the hands-on sessions (S1, S2, S5), interactive voice recovers about 4.7 s faster and needs about 12 s less input. **Outcomes are the same**: both reach 1.00 completion and 1.00 latest-intent accuracy. The gap is the typing time plus the assumed 1.5 s cost of leaving the app, so it moves with those guesses (sweeps in `results/RESULTS.md`).
- **H3 held.** With free hands (S3, S4), text + interrupt and interactive voice are identical on completion, latest intent and unwanted actions. Voice is a convenience there, not a capability gain.
- **H4 held.** Ledger rules waste 18.7 s less work than always-stop and take 0.8 fewer weighted unwanted actions than never-stop.
- **Break-even.** Text + interrupt starts to lose outcomes (completion 0.94) when typing takes 3 s per word. Interactive voice starts to lose (latest intent 0.86) when all voice lags are 8 times the defaults. In the plausible range neither loses.

How to read this honestly: the best agent solves every session by design (the oracle passes 100 of 100 variants, and each trap policy fails the check it was built to fail). So the simulator mainly shows **where the interface decides the outcome** (text without interrupt, basic voice, the wrong policy) and **how large the speed and effort gap is** between the two strong arms. It cannot say whether people prefer talking.

## Layout

```
ldp/ledger.py        action states and the stop / hold / undo table
ldp/model.py         parameters, meanings (intents), utterances, session spec
ldp/engine.py        discrete-event loop, barge-in, queueing, binding, unwanted-action rules
ldp/channels.py      the four arms (+ oracle)
ldp/policies.py      ledger rules, always-stop, never-stop, trap policies
ldp/sessions/        S1 to S5: scripted user, mock app, hidden checks, variants
ldp/metrics.py       the measures
ldp/experiment.py    grid, bootstrap intervals, H1 to H4, sensitivity, report
ldp/timeline.py      HTML timeline of one run
tests/               ledger table, engine hand counts, solvability, trap policies, arm behaviour
docs/                design (SESSIONS.md), build plan, project description
results/             generated tables, CSV, timelines
```

## Limits

- The user is scripted. Comfort, errors in real speech, and the true cost of switching to a keyboard need a human pilot (5 to 8 people, S1 and S2).
- Language understanding is scripted: each utterance carries its meaning. Recognition errors are not modelled yet.
- The executor is scripted, not a language model, so results say nothing about how well a model debugs.
- The mock apps are state machines. No real container, shell, or fault is involved.
- Timing numbers (typing 1.2 s per word, 1.5 s app-switch cost, 150 ms onset, 300 ms stream lag, 250 ms barge-in cut, and the session timelines) are guesses. They are parameters in `ldp/model.py`; the report sweeps three of them.
- Sessions are my own scripts with generic faults. "Intended meaning" at ambiguous points (for example S3, "skip the integration ones" applies to the current run) is a design choice that two reviewers should confirm.
- Not modelled: a second check disturbing a running test (S2), picking the wrong container (S4), speech recognition noise.

## Not built yet

M5: real Docker app (rootless, allow-listed commands), language-model executor, streaming speech in and out. M6: a learned policy for D1 to D7 if the rules leave a gap. M7: the human pilot. Start with M7 for the question the simulator cannot answer.
