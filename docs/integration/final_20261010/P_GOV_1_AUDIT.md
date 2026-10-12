# P-GOV-1 independent audit record (Codex, model gpt-6-sol, effort medium)

Codex did not write this code. Each round reviewed `git diff 54ad7be..HEAD` read-only. Every finding was checked by
Claude against the code before it was repaired. Each repair has a test that fails without it.

| Round | Commit reviewed | Verdict | Findings (repaired in) |
|---|---|---|---|
| r1 | 3d4407b | REJECT | H1 -UiRoot authority, H2 drivers opened windows on WAIT_HEAVY, M1 peek race, M2 UI failure skipped Brain, M3 companion runner not covered, L1 tests (02e3189) |
| r2 | 02e3189 | REJECT | H1 default UI root bypassed the candidate rule, M1/M2 rnd evidence tooling (0a1b3c2) |
| r3 | 0a1b3c2 | REJECT | rnd tooling: deadline, non-perf JSON, label vs tag (38267a4) |
| r4 | 38267a4 | REJECT | rnd tooling: chatty runner, split stdout, stale tag outputs (0794a57) |
| r5 | 0794a57 | REJECT | A5 Brain started with a windowless UI, preflight before clearing outputs, A2 corrupt record with free lock (a25bc3e) |
| r6 | a25bc3e | REJECT | A5 reused windowless UI (4e564a8) |
| r7 | 4e564a8 | REJECT | A5 GPU memory without a window counted as shown (ee99329) |
| r8 | ee99329 | REJECT | A2 process counters missing gave GO (535c601) |
| r9 | 535c601 | REJECT | partial census below Brain threshold, non-llama large process, LAUNCHED before window (eafe83a) |
| r10 | eafe83a | REJECT | HIGH contention cleanup by executable path (f98d221) |
| r11 | 0a57c2b | **ACCEPT WITH FINDINGS** | scope reduced to the canonical files (a0e12d0: the companion-voice runners are their owner's, findings handed over in `P_GOV_1_RUNNER_HANDOFF.md`); two LOW: handoff attribution, gate provenance (repaired after r11) |

Not verifiable without hardware (classified as limitations by Codex r11): UI-first calibration ≥ 120 tok/s with a
window open, and the advisory verdict against a resident Brain. These are checked live in staging
(`STAGING_QUALIFICATION.md`).
