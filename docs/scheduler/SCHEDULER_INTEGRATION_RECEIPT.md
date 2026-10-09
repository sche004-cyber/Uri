# URI Scheduler — Integration Receipt

Date: 2026-10-09 (Asia/Kolkata). **Status: candidate independently accepted with findings and regression-verified.
NOT published, NOT merged, NOT registered with Windows, festival schedule NOT activated.**

## 1. Acceptance criteria for integration

| id | criterion | result |
|---|---|---|
| I-AC1 | Independent Codex review accepts the candidate (ACCEPT or ACCEPT WITH FINDINGS), findings repaired or recorded | **met**: round 8 ACCEPT WITH FINDINGS on `6cefc66`; both findings repaired in `7496bba` (SCHEDULER_AUDIT.md) |
| I-AC2 | Combined regression on the materialized tree equals the accepted baseline | **met**: see §3 |
| I-AC3 | No frozen file changed; guard lists extended by exact path only | **met**: phase1-scope `outside_phase2_scope = ∅`, `importers = ∅`, 98 frozen files byte-identical; `test_frozen_core.py` / `phase2close_chain.py` diffs add exact scheduler paths only |
| I-AC4 | Base line accepted and published before the candidate is merged into canonical development | **NOT met**: the base `integration/ws-hardening-20261009` (`99f8041`) is itself mid-phase (its plan lists T8 regression, T9 Codex review, T10 publication as Planned) |
| I-AC5 | Real harness-to-review path demonstrated | **NOT met**: real Claude generation BLOCKED (CLI not logged in; owner action) |

Because I-AC4 and I-AC5 are not met, the controlled integration step (publish + fast-forward canonical development) was
**not performed**. This receipt records the candidate so it can be integrated directly after the hardening line is accepted.

## 2. Provenance

| item | value |
|---|---|
| Worktree / branch | `C:\Users\cheta\Development\uri-scheduler` / `phase/scheduler` (local only) |
| Base | `99f8041` (`integration/ws-hardening-20261009`, worktree `uri-ws-hardening`) |
| Candidate code tip (reviewed + regression) | `7496bba` |
| Later commits | documentation and evidence only (`docs/scheduler/**`) |
| Commits since base | 14 up to `7496bba` (`a81e5dc` … `7496bba`), then documentation/evidence commits |
| Files changed vs base | 48 (+ docs/evidence after `7496bba`); outside the new scheduler paths: `scripts/oi_materialize_test_runtime.py`, `scripts/phase2close_chain.py`, `tests/phase2a/test_frozen_core.py` (exact-path guard and materialization lists), `uri_ui/lib/living/screens/dashboard_mode_view.dart` (one tile) |
| Review clone | `C:\Users\cheta\Development\sra` (`core.autocrlf=false`), Codex CLI 0.158.0, `gpt-6-sol`, `medium`, read-only |
| Gate tree | `C:\Users\cheta\Development\uri-sched-gate\uri-agent`, materialized from `7496bba` (`evidence/chain/gate_MATERIALIZATION_RECEIPT.json`: base `e8e3b65`, overlay `759d0d4`, `head_is_base: true`) |

## 3. Combined regression (accepted chain, `scripts/phase2close_chain.py --no-native`)

| gate | run | result | accepted baseline |
|---|---|---|---|
| phase2 | `sched_chain2` | 486 passed / 0 failed / 2 skipped | 486 / 0 / 2 |
| authority | `sched_chain2` | 134 / 0 | 134 / 0 |
| phase1-full | `sched_chain2` | 2,674 / 12 / 12 — **FAILED** (correction recorded below) | 2,676 / 11 / 11 |
| phase1-full | `sched_chain3` | **2,676 / 11 / 11, same failure set, 2,698 ids, missing = added = outcome_changed = ∅** | 2,676 / 11 / 11 |
| phase1-scope | `sched_chain3` | PASS (outside = ∅, importers = ∅, 98 frozen files identical, runner argv = accepted + phase2oq ignore) | PASS |
| residue | `sched_chain3` | PASS | PASS |
| Flutter (whole `uri_ui/test`) | separate run | 313 passed, 3 skipped, 0 failed (`evidence/chain/flutter_all.log`) | — |
| Scheduler suites | separate run | 60 passed (`tests/scheduler`) | — |

**Correction record (sched_chain2 → sched_chain3).** `sched_chain2` reported `CHAIN_FAILED` with two outcome changes, both
traced to the gate environment, not to the candidate:
1. `test_phase1_offline_components::…restore_hashes…` failed with `FileNotFoundError …\work\c1\checkpoints\c3-provisional-source.zip`.
   The accepted WS gate tree (`uri-ws-gate2`) carries this git-ignored fixture directory; the freshly materialized gate did
   not. The files were copied unchanged from `uri-ws-gate2\uri-agent\work\c1\checkpoints\`.
2. `test_gemma_worker_mcp::test_live_ollama_status_and_model` was skipped because no Ollama service was listening (the
   accepted baseline ran with Ollama up). `ollama serve` was started for the run (the test only calls `/api/tags`; no
   model was loaded) and stopped afterwards (PID 8368).
`sched_chain3` re-ran phase1-full, phase1-scope and residue on the same tree and passed with outcome identity. Phase2 and
authority were not re-run because the environment change cannot affect them (no fixture or Ollama use) and they had
already matched the baseline on the same tree. Both summaries are kept: `evidence/chain/sched_chain2_summary.json` (SHA-256
`98b004ee…a99da`), `evidence/chain/sched_chain3_summary.json` (`45070689…d7a21cd`).

## 4. What remains for the owner (RED / owner gates)

1. **Log the scheduler's Claude client profile in** (not done by the agent; credentials):
   `$env:USERPROFILE='C:\Users\cheta\Development\uri-scheduler-state\client_home'; $env:HOME=$env:USERPROFILE; claude auth login`
   then run the live leg (FESTIVAL_GIF_LIVE_TEST.md §2 Leg C).
2. Accept or reject the recorded limitations: F2 (filesystem boundary = Claude Code permission engine), R7-1 (cancel window
   inherited from the accepted supervisor).
3. Approve the festival list/dates (FESTIVAL_CALENDAR_PLAN.md §4), confirm the Sikkim dates, then activate.
4. Decide the Windows lifecycle: register `URIScheduler` (`scripts/scheduler_task_ctl.ps1 -Action install -Apply`) or not.
5. After the ws-hardening line is accepted and published: publish `phase/scheduler`, re-run the chain on the merged tree,
   fast-forward canonical development, and append the remote confirmation to this receipt.
