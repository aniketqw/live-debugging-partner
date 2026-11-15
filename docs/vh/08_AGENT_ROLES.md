# 08 — Agent roles (hats), hand-offs, and what each one produces

You may be one agent wearing four hats in order, or four sub-agents. Either way, each hat has its own job and its own output. A hat does not do another hat's job.

| Hat | Job | May edit | Must NOT do | Output (hand-off) |
|---|---|---|---|---|
| Researcher | Answers the task's research questions with the protocol in `04` | `RESEARCH_NOTES.md`, `DECISIONS.md` | write product code | Notes with status per claim; a short "what the implementer may rely on" list |
| Implementer | Writes tests first, then the minimum code | `vh/`, `tests_vh/`, `bench/`, `scripts/`, `demo/` | change a spec file; rely on UNVERIFIED claims; weaken tests | A diff, the plan, and the tests it wrote |
| Verifier | Runs verification commands and the break-it checks, tries to make tests fail | tests only to ADD attacking tests; never the implementation | fix bugs (it reports them) | Verify output, break-it lines, list of failures |
| Skeptic | Walks the trap checklist in `05` section 3 and the result audit in section 4 | `STATUS.md` (AUDIT section) | write code | A checklist with a verdict per item, and any claim it believes is overstated |

## Hand-off sequence per task

```
Researcher  -> RESEARCH_NOTES.md (+ DECISIONS.md)
Implementer -> code + tests, plan in STATUS.md
Verifier    -> STATUS.md: verify output + break-it
Skeptic     -> STATUS.md: audit lines, then the task verdict (PASS / FAIL / BLOCKED)
```
A task is PASS only if the Skeptic finds no open item for it. If the Skeptic finds a problem, the task goes back to the Implementer (maximum 2 loops, then BLOCKED).

## Writing the hat in STATUS.md

Before each step write the hat name, e.g. `[Verifier] running break-it for I3`. This makes the log reviewable by the human.

## Escalation to the human (stop and ask when)

- A spec contradicts `ldp` behaviour.
- A research claim is UNVERIFIED and the task needs it.
- A test would have to be loosened.
- A result looks too good (for example, 100% everywhere on real models). Too good is a bug until proven otherwise.
- Quota or cost limits would be exceeded.
