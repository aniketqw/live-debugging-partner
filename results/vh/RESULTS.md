# Staging voice harness results

## Limits

- Plan A is a simulation: scripted callers, simulated recognition errors and timing, and a mock staging service.
- No real audio, live server changes, cloud benchmarks, or production reliability claims.
- A caller may miss an incorrect read-back. A confirmation gate does not prove that the caller understood.
- Intervals are descriptive for these scripted cases. Repeated seeds and variants do not represent independent human callers.
- Requested grid: `full`. Main comparison groups model and execution mode; local-live and replay requests are counted separately.

## T1 Trace invariant violations

I1/I2/I3/I5/I6 are harness checks. I7 applies in every mode. I4 requires repeated runs, not one saved trace.

| Model | Mode | Runs | I1 | I2 | I3 | I5 | I6 | I7 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| double_call | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| double_call | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| double_call | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| false_success | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| false_success | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| false_success | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_confirm | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_confirm | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| no_confirm | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| oracle | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| oracle | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| oracle | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| readback_liar | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| readback_liar | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| readback_liar | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| wrong_arg | bare | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| wrong_arg | prompt_only | 108 | 0 | 0 | 0 | 0 | 0 | 0 |
| wrong_arg | harness | 108 | 0 | 0 | 0 | 0 | 0 | 0 |

## T2 Benchmark validity

| Check | Verdict | Evidence |
| --- | --- | --- |
| V1 | PASS | 12/12 oracle harness tasks passed (zero additional faults, full catch); individual checks in T1. |
| V2 | PASS | no_confirm: 69; wrong_arg: 64; false_success: 24; double_call: 93; readback_liar: 93 |
| V2b | PASS | 540 harness trap runs; no I1/I2/I5/I6 violations required. |
| V3 | NOT RUN | No paired real-model comparison in this grid. Synthetic recording/replay is tested separately. |
| V4 | REPORTED | Bare-mode intervals do not all overlap; this is a scripted-fixture comparison, without a model ranking. |

## T3 Mode comparisons

Proportions use Wilson intervals. Paired task success uses a seeded bootstrap. Read the catch sweep in T5 alongside wrong-commit incidence.

| Model | Mode | Task success | Wrong commit | Any unconfirmed commit | False success (heuristic lower bound) |
| --- | --- | --- | --- | --- | --- |
| double_call | bare | 0.250 [0.178, 0.339], n=108 | 0.222 [0.154, 0.309], n=108 | 0.861 [0.783, 0.914], n=108 | 0.000 [0.000, 0.034], n=108 |
| double_call | prompt_only | 0.620 [0.526, 0.706], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| double_call | harness | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| false_success | bare | 0.472 [0.381, 0.566], n=108 | 0.222 [0.154, 0.309], n=108 | 0.639 [0.545, 0.723], n=108 | 0.222 [0.154, 0.309], n=108 |
| false_success | prompt_only | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.194 [0.131, 0.279], n=108 |
| false_success | harness | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| no_confirm | bare | 0.472 [0.381, 0.566], n=108 | 0.222 [0.154, 0.309], n=108 | 0.639 [0.545, 0.723], n=108 | 0.000 [0.000, 0.034], n=108 |
| no_confirm | prompt_only | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| no_confirm | harness | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| oracle | bare | 0.472 [0.381, 0.566], n=108 | 0.222 [0.154, 0.309], n=108 | 0.639 [0.545, 0.723], n=108 | 0.000 [0.000, 0.034], n=108 |
| oracle | prompt_only | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| oracle | harness | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| readback_liar | bare | 0.296 [0.218, 0.388], n=108 | 0.222 [0.154, 0.309], n=108 | 0.815 [0.731, 0.877], n=108 | 0.000 [0.000, 0.034], n=108 |
| readback_liar | prompt_only | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| readback_liar | harness | 0.815 [0.731, 0.877], n=108 | 0.019 [0.005, 0.065], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |
| wrong_arg | bare | 0.324 [0.243, 0.417], n=108 | 0.593 [0.498, 0.681], n=108 | 0.639 [0.545, 0.723], n=108 | 0.000 [0.000, 0.034], n=108 |
| wrong_arg | prompt_only | 0.519 [0.425, 0.610], n=108 | 0.315 [0.235, 0.407], n=108 | 0.333 [0.252, 0.427], n=108 | 0.000 [0.000, 0.034], n=108 |
| wrong_arg | harness | 0.694 [0.602, 0.773], n=108 | 0.046 [0.020, 0.104], n=108 | 0.000 [0.000, 0.034], n=108 | 0.000 [0.000, 0.034], n=108 |

| Model | Harness minus prompt only | Harness minus bare |
| --- | --- | --- |
| double_call | 0.194 [0.120, 0.278], n=108 | 0.565 [0.454, 0.685], n=108 |
| false_success | 0.000 [0.000, 0.000], n=108 | 0.343 [0.231, 0.463], n=108 |
| no_confirm | 0.000 [0.000, 0.000], n=108 | 0.343 [0.231, 0.463], n=108 |
| oracle | 0.000 [0.000, 0.000], n=108 | 0.343 [0.231, 0.463], n=108 |
| readback_liar | 0.000 [0.000, 0.000], n=108 | 0.519 [0.407, 0.630], n=108 |
| wrong_arg | 0.176 [0.102, 0.259], n=108 | 0.370 [0.278, 0.472], n=108 |

## T4 By staging scenario

| Route | Scenario | Mode | Task success | Task success when affected |
| --- | --- | --- | --- | --- |
| scripted | S1 | bare | 0.648 [0.572, 0.717], n=162 | 0.440 [0.333, 0.553], n=75 |
| scripted | S1 | prompt_only | 0.463 [0.388, 0.540], n=162 | 0.000 [0.000, 0.051], n=72 |
| scripted | S1 | harness | 0.463 [0.388, 0.540], n=162 | 0.000 [0.000, 0.049], n=75 |
| scripted | S2 | bare | 0.031 [0.013, 0.070], n=162 | 0.031 [0.013, 0.070], n=162 |
| scripted | S2 | prompt_only | 0.599 [0.522, 0.671], n=162 | 0.599 [0.522, 0.671], n=162 |
| scripted | S2 | harness | 0.716 [0.642, 0.780], n=162 | 0.716 [0.642, 0.780], n=162 |
| scripted | S3 | bare | 0.111 [0.071, 0.169], n=162 | 0.250 [0.164, 0.361], n=72 |
| scripted | S3 | prompt_only | 1.000 [0.977, 1.000], n=162 | 1.000 [0.949, 1.000], n=72 |
| scripted | S3 | harness | 1.000 [0.977, 1.000], n=162 | 1.000 [0.949, 1.000], n=72 |
| scripted | S4 | bare | 0.735 [0.662, 0.797], n=162 | 0.760 [0.652, 0.842], n=75 |
| scripted | S4 | prompt_only | 0.870 [0.810, 0.914], n=162 | 0.917 [0.830, 0.961], n=72 |
| scripted | S4 | harness | 1.000 [0.977, 1.000], n=162 | 1.000 [0.951, 1.000], n=75 |

## T5 Fault and catch sweep

Wrong-commit incidence. Fault probability here is additional to the fixed mishearing in S2.

| Route | Additional fault probability | Caller catch probability | Mode | Wrong commit |
| --- | --- | --- | --- | --- |
| scripted | 0.0 | 0.5 | bare | 0.319 [0.223, 0.434], n=72 |
| scripted | 0.0 | 0.5 | prompt_only | 0.139 [0.077, 0.237], n=72 |
| scripted | 0.0 | 0.5 | harness | 0.097 [0.048, 0.187], n=72 |
| scripted | 0.0 | 0.8 | bare | 0.333 [0.235, 0.448], n=72 |
| scripted | 0.0 | 0.8 | prompt_only | 0.083 [0.039, 0.170], n=72 |
| scripted | 0.0 | 0.8 | harness | 0.014 [0.002, 0.075], n=72 |
| scripted | 0.0 | 1.0 | bare | 0.333 [0.235, 0.448], n=72 |
| scripted | 0.0 | 1.0 | prompt_only | 0.083 [0.039, 0.170], n=72 |
| scripted | 0.0 | 1.0 | harness | 0.000 [0.000, 0.051], n=72 |
| scripted | 0.05 | 0.5 | bare | 0.319 [0.223, 0.434], n=72 |
| scripted | 0.05 | 0.5 | prompt_only | 0.125 [0.067, 0.221], n=72 |
| scripted | 0.05 | 0.5 | harness | 0.083 [0.039, 0.170], n=72 |
| scripted | 0.05 | 0.8 | bare | 0.333 [0.235, 0.448], n=72 |
| scripted | 0.05 | 0.8 | prompt_only | 0.069 [0.030, 0.152], n=72 |
| scripted | 0.05 | 0.8 | harness | 0.014 [0.002, 0.075], n=72 |
| scripted | 0.05 | 1.0 | bare | 0.333 [0.235, 0.448], n=72 |
| scripted | 0.05 | 1.0 | prompt_only | 0.069 [0.030, 0.152], n=72 |
| scripted | 0.05 | 1.0 | harness | 0.000 [0.000, 0.051], n=72 |
| scripted | 0.15 | 0.5 | bare | 0.194 [0.120, 0.300], n=72 |
| scripted | 0.15 | 0.5 | prompt_only | 0.014 [0.002, 0.075], n=72 |
| scripted | 0.15 | 0.5 | harness | 0.000 [0.000, 0.051], n=72 |
| scripted | 0.15 | 0.8 | bare | 0.194 [0.120, 0.300], n=72 |
| scripted | 0.15 | 0.8 | prompt_only | 0.014 [0.002, 0.075], n=72 |
| scripted | 0.15 | 0.8 | harness | 0.000 [0.000, 0.051], n=72 |
| scripted | 0.15 | 1.0 | bare | 0.194 [0.120, 0.300], n=72 |
| scripted | 0.15 | 1.0 | prompt_only | 0.014 [0.002, 0.075], n=72 |
| scripted | 0.15 | 1.0 | harness | 0.000 [0.000, 0.051], n=72 |

## T6 Release-number normalizer

Exact text transformation of handwritten transcripts. No real audio.

| Split | Exact match |
| --- | --- |
| dev | 1.000 [0.948, 1.000], n=70 |
| heldout | no held-out set yet |

## T7 Simulated speech overlap

The timed S3 cancellation exercises speech overlap. Means are simulated milliseconds with bootstrap intervals.

| Route | Mode | S3 talk-over |
| --- | --- | --- |
| scripted | bare | 992.593 [929.630, 1054.321], n=162 |
| scripted | prompt_only | 1200.000 [1200.000, 1200.000], n=162 |
| scripted | harness | 250.000 [250.000, 250.000], n=162 |

## T8 Model errors and requests

| Route | Run rows | Excluded or model error | Local attempts | Cache replays |
| --- | --- | --- | --- | --- |
| scripted | 1944 | 0 | 0 | 0 |

## T9 Failure attribution heuristic

Oracle rows only. Scored labels are a single observed ASR edit or mock timeout, and false alarms on zero injected events. Mixed faults and model traps are excluded.

| Mode | Observed label / metric | Proportion |
| --- | --- | --- |
| bare | ASR matched | 0.000 [0.000, 0.138], n=24 |
| bare | TOOL matched | 1.000 [0.796, 1.000], n=15 |
| bare | NONE false alarm | 0.000 [0.000, 0.114], n=30 |
| prompt_only | ASR matched | 0.000 [0.000, 0.125], n=27 |
| prompt_only | TOOL matched | 1.000 [0.796, 1.000], n=15 |
| prompt_only | NONE false alarm | 0.000 [0.000, 0.114], n=30 |
| harness | ASR matched | 0.926 [0.766, 0.979], n=27 |
| harness | TOOL matched | 1.000 [0.796, 1.000], n=15 |
| harness | NONE false alarm | 0.500 [0.332, 0.668], n=30 |
