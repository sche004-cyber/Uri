# EPQ-1 interim report 2: sealed holdout results

Date: 2026-10-01. Holdout: 138 cases, run once at 08:15–08:55 IST after the harness freeze (`c17f593`, `battery/MANIFEST_harness.json`), 3 repeats per arm, accuracy is worst of 3. Full tables are in `results/holdout_tables.md`. **No model or pairing is qualified by these results.**

## 1. Headline

1. **Neither Needle nor Granite reaches the pre-registered `CANDIDATE` label (≥ 0.95 with no incorrect execution) in any of the 12 families.** Only Granite native on ARGS (10/12) and CPU Granite on SELECT (15/17) reach `PARTIAL`; every other specialist cell is `UNSUITABLE_AT_THIS_CONFIG`.
2. **The local Main Brain (`qwen3.5:9b`) is far stronger on the same workload:** 112/138 against 57–68/138 for the specialists. It reaches `CANDIDATE` on ARGS, NEGATION, ROUTE, SELECT and SEMANTIC.
3. **Adding Edge in front of the Main Brain made URI worse on this holdout.** The hybrid (M36 gate, deterministic rules, Granite, then Brain) completed 86/138 against 109/138 for the Brain alone. It also returned 45 incorrect results against 17, while cutting Brain calls to 32% of turns and p50 latency from 908 ms to 273 ms. Under the pre-registered pass rule (non-inferior success within 2 points), Edge fails.
4. **The pair adds little.** Selective routing by request kind (the version URI can actually implement) chose Granite for every kind on the development split, so it equals Granite alone (56/138). Granite-then-Needle completes 69/138 but returns 41 incorrect results. Selecting by family, an oracle upper bound URI cannot implement, reaches only 59/138.

## 2. Raw accuracy by family (worst of 3)

| Family (n) | determ. | needle_P0 | needle_P1 | gran_nat_P0 | gran_nat_P1 | gran_json_P0 | gran_json_P1 | gran_CPU_json_P1 | brain_P1 |
|---|---|---|---|---|---|---|---|---|---|
| AMBIGUITY (10) | 10/10 | 0/10 | 2/10 | 0/10 | 0/10 | 0/10 | 1/10 | 1/10 | 4/10 |
| ARGS (12) | 6/12 | 11/12 | 10/12 | 11/12 | 10/12 | 11/12 | 10/12 | 10/12 | 12/12 |
| ESCALATE (11) | 11/11 | 2/11 | 5/11 | 0/11 | 1/11 | 0/11 | 4/11 | 4/11 | 7/11 |
| EXTRACT (9) | 0/9 | 2/9 | 2/9 | 2/9 | 2/9 | 3/9 | 3/9 | 3/9 | 5/9 |
| INJECTION (13) | 6/13 | 9/13 | 7/13 | 7/13 | 7/13 | 5/13 | 5/13 | 5/13 | 10/13 |
| MULTISTEP (5) | 3/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 0/5 | 1/5 |
| NEGATION (15) | 5/15 | 10/15 | 6/15 | 10/15 | 14/15 | 10/15 | 10/15 | 11/15 | 15/15 |
| REFERENCE (14) | 8/14 | 4/14 | 4/14 | 6/14 | 6/14 | 5/14 | 4/14 | 4/14 | 11/14 |
| ROUTE (12) | 0/12 | 1/12 | 1/12 | 7/12 | 7/12 | 7/12 | 7/12 | 6/12 | 12/12 |
| SELECT (17) | 5/17 | 14/17 | 13/17 | 16/17 | 16/17 | 16/17 | 15/17 | 15/17 | 17/17 |
| SEMANTIC (10) | 0/10 | 3/10 | 3/10 | 3/10 | 3/10 | 6/10 | 6/10 | 6/10 | 10/10 |
| UNSUPPORTED (10) | 10/10 | 4/10 | 4/10 | 2/10 | 2/10 | 0/10 | 0/10 | 0/10 | 8/10 |
| **All** | 64/138 | 60/138 | 57/138 | 64/138 | 68/138 | 63/138 | 65/138 | 65/138 | 112/138 |

The deterministic column counts "did nothing" as a correct abstention. Its real completion rate is 14/138 (§4).

## 3. Containment (select cases, all 3 repeats) and latency

| Arm | false accept (no-action cases) | executed correct | executed incorrect | contained | held for approval right / wrong | p50 / p95 ms |
|---|---|---|---|---|---|---|
| needle_P1 | 36/49 | 68 | 75 | 86 | 17 / 12 | 734 / 993 |
| granite_native_P1 | 42/49 | 102 | 60 | 94 | 24 / 0 | 254 / 509 |
| granite_json_P1 | 42/49 | 80 | 68 | 113 | 21 / 0 | 166 / 386 |
| granitecpu_json_P1 | 42/49 | 87 | 60 | 108 | 24 / 0 | 745 / 989 |
| brain_P1 | 19/49 | 120 | 30 | 36 | 30 / 0 | 884 / 1540 |
| needle_R1 (real URI schemas) | 35/49 | 89 | 122 | 20 | 33 / 0 | 1146 / 1483 * |
| granite_json_R1 (real URI schemas) | 44/49 | 96 | 159 | 0 | 33 / 0 | 945 / 1309 * |

\* The R1 arms ran 08:43–08:55 IST, when another session on this PC was running a pytest suite that calls the same Ollama `qwen3.5:9b` (coordinator note). Their latencies are contended and will be re-measured on an idle machine. Accuracy is unaffected.

With the real URI schemas (R1), action choice on the 102 select cases is Needle 53 and Granite JSON 48, against 49 and 47 with the typed catalogue. Executed-incorrect rises sharply (122 and 159), because the real tools take `request_text` or no argument, so URI's argument grounding check has nothing to reject.

Consistency: cases whose outcome changed across the 3 repeats were Needle 4/138, Granite 0–1/138 and Brain 0/138. Repeats measure stability only.

Placement-matched latency (both on CPU): Granite JSON p50 745 ms against Needle P1 p50 734 ms. Needle's own warm inference is about 140–230 ms; its p50 includes building a new agent whenever the offered tool set changes. Accuracy for CPU and GPU Granite is the same (65/138).

## 4. End-to-end configurations (holdout, first repeat, specialists needle_P1 and granite_json_P1)

| Configuration | success | incorrect | safe fail | Brain share | p50 / p95 ms |
|---|---|---|---|---|---|
| C0 deterministic only | 14/138 | 13 | 111 | 0 | 0 / 0 |
| C1 Needle alone | 47/138 | 39 | 52 | 0 | 671 / 955 |
| C2 Granite alone | 56/138 | 34 | 48 | 0 | 179 / 491 |
| C3 pair, selective by kind | 56/138 | 34 | 48 | 0 | 179 / 491 |
| C3o pair, selective by family (oracle) | 59/138 | 39 | 40 | 0 | 267 / 790 |
| C4 Needle then Granite | 59/138 | 51 | 28 | 0 | 680 / 1338 |
| C4b Granite then Needle | 69/138 | 41 | 28 | 0 | 279 / 1124 |
| C5 Main Brain alone | **109/138** | 17 | 12 | 1.00 | 908 / 1794 |
| C6 hybrid: M36 + rules + Granite, then Brain | 86/138 | 45 | 7 | 0.32 | 273 / 1493 |
| C6c hybrid with Needle instead of Granite | 82/138 | 54 | 2 | 0.33 | 703 / 2074 |
| C7 M36 + rules, then Brain (no Edge model) | 100/138 | 27 | 11 | 0.80 | 743 / 1621 |

**Correction found on the holdout and kept visible.** The experimental deterministic rules had a bug in their filename pattern. Spaces were allowed, so the match started at the request's first word, giving "Read the attached file x.pdf" as the file name. That caused 13 incorrect executions in C0; the same defect was present but unnoticed in development. A corrected rule set (`DET_VERSION=fix1`, reported separately; the original run is kept) gives C0 24/138 with 3 incorrect, C7 110/138 with 17 incorrect at 80% Brain share, and C6 96/138 with 35 incorrect. The conclusions in §1 do not change.

## 5. Repair diagnostics on the holdout

Label-as-tool-choice (v3t), which raised Needle from 3 to 8 of 30 on development SEMANTIC, scored 2/10 on the holdout (v1: 3/10). For Granite native it scored 6/10 against 3/10 on v1. The Needle gain did not hold up.

## 6. Still to do

Fault injection and recovery, the seven URI-pipeline workflows, cold-start measurements, an idle-machine latency rerun, and reports A to G plus the Codex handoff package. These are paused while the Harness-first session uses the machine, at the coordinator's request.
