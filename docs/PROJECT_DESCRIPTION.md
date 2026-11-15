# Project description: Live Debugging Partner

## One line
A voice agent that helps you debug a running app, and that handles interruptions, corrections, "that error" on your screen, and the timing of its own actions.

## Problem
Today, coding agents work turn by turn. You type, you wait, the agent acts. In real debugging, you speak while you click, you change your mind, and you say "stop" while a command runs. A turn-based agent misses these signals. It acts on old instructions, talks over you, kills useful work, or cannot undo what it already did.

## What we build
An agent that listens and works at the same time. It knows the state of every action it takes:
- proposed, announced, running read-only, running changing, done reversible, done irreversible.

With this "action ledger", the agent decides what to do at each moment:
- wait, acknowledge, clarify, inspect, execute, or cancel.

It must:
1. Stop or pause when you interrupt, but only the action you mean.
2. Follow your latest instruction ("billing, no wait, auth").
3. Bind "that error" to what you selected on screen when you said it.
4. Keep your constraints ("don't touch the tax logic").
5. Tell you the truth when it is too late to stop, and offer an undo.

## Research question
Does interactive voice help more than a good text interface with an interrupt button? We compare four modes on the same tasks:
Text, Text + interrupt, Basic voice, Interactive voice.

## Measures
Task completion, follows latest intent, unwanted actions, correction-recovery time, wasted execution, talk-over, user effort, cost.

## Method
1. Five realistic debugging sessions (SESSIONS.md), for example a coupon checkout error and a slowdown during a load test.
2. A simulator first: a mock app, a scripted user, a scripted executor, a 100 ms clock. Fixed rules decide actions. No GPU, Docker or speech API.
3. If interactive voice wins in the simulator: real Docker app, a language model executor, streaming speech, a learned (RL) policy, and a pilot with 5 to 8 people.

## Outcome
A tested answer to "when does voice actually change how an agent should work", a reusable session benchmark, and a decision policy for live, interruptible agents.

## Files
SESSIONS.md (design), IMPLEMENTATION_PLAN.md (build steps M0 to M7), gym/ (earlier VoiceOps Gym work we reuse).
