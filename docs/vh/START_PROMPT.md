# START_PROMPT.md — paste this into Codex (or Claude Code) to begin

---

You are working in the repository `live-debugging-partner`. A project kit was added: `AGENTS.md` at the root and specs in `docs/vh/`.

Do this now:

1. Read `AGENTS.md` fully. Obey every rule in it.
2. Read `docs/vh/00_READ_FIRST.md`, then `docs/vh/04_RESEARCH_PROTOCOL.md`, then `docs/vh/08_AGENT_ROLES.md`.
3. If `docs/vh/STATUS.md` does not exist, create it from `templates/STATUS.md`. Also create `docs/vh/RESEARCH_NOTES.md` and `docs/vh/DECISIONS.md` from `templates/`.
4. Start Plan A at the first task not yet DONE in `docs/vh/06_TASKS_PLAN_A.md`. Do exactly one task, using the 7-step loop in AGENTS.md section 4.
5. When a task is PASS, FAIL or BLOCKED, update STATUS.md with the evidence and STOP. Do not continue to the next task until I say "next".

Important reminders:
- Research before you rely on any external fact. Verify it with a small probe (a command or script), write it in RESEARCH_NOTES.md with the source and the probe result, then use it. Unverified facts get a fallback and a flag.
- Prove, do not claim. Every result must come from code that you ran, and every number in any document must come from `results/RESULTS.md`.
- Never edit `ldp/` or `tests/`. Never commit.
- If anything in the specs is unclear, write the question in DECISIONS.md and choose the most conservative reading.

Begin with the first task and report: the plan, the tests you wrote, the verification output, and the verdict.

---

## Continue prompt (use after each task)

"next. Re-read AGENTS.md and STATUS.md, then do the next task in the plan with the same 7-step loop. Report plan, tests, verification output, verdict."

## Review-only prompt (use when you want an audit instead of new work)

"Do not write new features. Act as Verifier and Skeptic from docs/vh/08_AGENT_ROLES.md. Run every command in docs/vh/05_VERIFICATION.md, attempt the break-it check on every invariant, check every trap in section 3, and write findings to docs/vh/STATUS.md under 'AUDIT'. Do not fix anything; list issues with evidence."
