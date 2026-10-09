# Working System Integration — integration receipt

Date: 2026-10-08/09. Recorded by Claude, from the primary evidence listed below. Branch
`integration/working-system-20261008` (worktree `C:\Users\cheta\Development\uri-working-system`). The branch is
**local only**: it is not pushed and not merged into any shared branch. No cutover was made.

## 1. Commits

| Role | Commit |
|---|---|
| Published baseline | `037229c1fc04eadc6a2e42e92e6ef0d12520d3fe` |
| UI candidate merged | `569cf7c62d059ab188295bc286de882e0a7350e1` (merge `ddaf67b`) |
| OI candidate merged | `9306dc11317d3fd24a9c47dfca65dba188c58985` (merge `2b6ee9f`) |
| FB-1 frozen `.gitignore` restored | `385250f` |
| Integration implementation | `40e206c`, `525836e`, `d0819e3`, `a80dc58`, `085384d`, `2e4b377` |
| Codex repairs | r1 → `56c58b1`; r2 → `6bed5a3`; r3 → `fcfed5c`; r4 coverage → `abe2f9b` |
| Post-review | `cfe4e88` (identity tool error path), `fc30e9e` (status report, launcher default), then docs/evidence commits (`git log 037229c..HEAD`) |
| Code reviewed by Codex r4 | `fcfed5c` |
| Final chain and live runtime materialized from | `abe2f9b1e8a69e411c48f6b91e86e249b3cd8949` |

Changes after `abe2f9b` (none is in a Phase 1/2 test scope; Codex round 5 reviewed those present at `154b952`, and rounds 6-8 checked the later repairs):
- `cfe4e88` `scripts/ws_server_identity.py` error path. It reaches the runtime: copied into `uri-ws-final` by hand,
  and its SHA-256 prefix `2509ca4ad6ea6ef1` equals the committed file.
- `fc30e9e` launcher default `-RuntimeRoot` changed from `uri-ws-rt` to `uri-ws-final` (behavioral). The committed
  self-test (`evidence/launcher_selftest.json`) ran against `uri-ws-final` after this change.
- Round-5 repairs: `tools/capture_ws.ps1` `-Attach` now requires `-AttachPid`, verifies the executable and writes
  `capture_run_<pid>_*.json`; `ws_ui_live_test.dart` asserts that Stop is pressed while the turn is unfinished, and
  asserts that the destructive request was not executed (no approval card, Core code `REFUSED_UNSUPPORTED` or
  `INTENT_CONFIRMED_NOT_EXECUTED`, memory unchanged). The refusal code itself is demonstrated through the worker only. Rerun with Runtime v1 READY: passed (`evidence/ui_live_brain_ready.json`).

## 2. Frozen and accepted boundaries

- `scripts/ws_frozen_check.py` at the tip: 121/121 Phase 1 checkpoint files byte-identical. No tracked or untracked
  path under `uri_core/`, `uri_supervisor/`, `uri_supervisor_bridge/`, `uri_harness_adapters/` or
  `model_lab/integration/` differs from `037229c`. The same holds for the frozen worker/server entrypoints, the
  frozen Dart files and the root `.gitignore`.
- Accepted files changed under owner decision WS-D3, and nothing else: `tests/phase2a/test_frozen_core.py`
  (`ALLOWED_NEW` + 63 enumerated paths) and `scripts/phase2close_chain.py` (`WS_EXACT` equality set; the importer
  check now also refuses `uri_operational_intelligence`). `PHASE2_SCOPE` is byte-identical to `037229c`.
- Runtime v1 configuration and artifacts were only read. The artifact match was verified on every READY probe.

## 3. Regression receipts

| Run | Tree | Result |
|---|---|---|
| `ws_chain1` (`evidence/ws_chain1_summary.json`) | `uri-ws-gate` from `40e206c`+ (WS-D3 v1) | ALL_PASS |
| `ws_chain_final` (`evidence/ws_chain_final_summary.json`, 23:26-23:51) | `uri-ws-gate2` from `abe2f9b` (`evidence/uri-ws-gate2_MATERIALIZATION_RECEIPT.json`) | **ALL_PASS**: phase2 486 passed / 0 failed / 2 skipped; authority 134/0; phase1-full 2,676/11/11 with outcome identity (2,698 ids, missing = added = changed = ∅, same failure set as the accepted log); phase1-scope (outside = ∅, importers = ∅, 98 frozen files byte-identical); residue |
| Flutter full suite (`abe2f9b`) | integration worktree | 294 passed, 3 skipped |
| OI + WS Python (`abe2f9b`) | integration worktree | 182 passed, 16 skipped |
| Live worker, Brain READY (`evidence/worker_live_20261008-233820.json`) | `uri-ws-final` | 8/8 passed |
| Live UI, Brain READY (`evidence/ui_live_brain_ready.json`) | `uri-ws-final` | passed |
| Live worker / UI, Brain stopped (`worker_live_20261008-232829.json`, `ui_live_brain_stopped.json`) | `uri-ws-final` | passed |
| Launcher self-test (`evidence/launcher_selftest.json`) | `uri-ws-final` | exit 0: real installation ok; legacy root, foreign UI and port 8000 refused; listener identity proven; wrong-key proof refused |
| Real-app captures | built Windows app over `uri-ws-final` | `screenshots/01..10`, `07a`; the restart sequence 07a/07/08 comes from one PID-verified process (`capture_run_11272_*.json`) |

Accepted-chain steps not run: flutter (covered by the full Flutter run above), bridge and native (no change to
those packages; native needs a client-profile Codex login, PA-8/9).

## 4. Independent review (Codex CLI `gpt-6-sol`, medium, read-only disposable clone `C:\Users\cheta\Development\wsa`)

| Round | Commit | Verdict | Findings → disposition |
|---|---|---|---|
| 1 | `2e4b377` | REJECT | F1 HIGH card decidable only after the job recorded it; F2 HIGH late approval during shutdown; F3 MEDIUM launcher trusted any HTTP 200; F4 MEDIUM mock approval preference shown as fact; F5 MEDIUM WS-D3 prefixes/wildcards, untracked files unchecked → all confirmed and repaired in `56c58b1` (F1 test with a negative control that fails without the fix) |
| 2 | `56c58b1` | REJECT | F3/F4 FIXED; F1/F2/F5 partial; new MEDIUM (late original `turn.finished`), LOW (self-test missed the signature check) → repaired in `6bed5a3` |
| 3 | `6bed5a3` | ACCEPT WITH FINDINGS | all prior items FIXED; F2 residual accepted as a recorded limitation; new MEDIUM (timeout treated as not started) → repaired in `fcfed5c` |
| 4 | `fcfed5c` | **ACCEPT WITH FINDINGS** | MEDIUM FIXED; residual R-BUSY recorded; coverage note → tests in `abe2f9b` |
| 5 | `154b952` (diff after `fcfed5c` + reports) | candidate ACCEPT WITH FINDINGS; reports REJECT pending correction | report boundaries overclaimed (review and chain commits); unverified `-Attach` capture provenance; UI refusal journey overstated; cancel-probe assertion; launcher default omitted → all repaired in the commit after `154b952` (attach captures 07a/07/08 retaken with PID verification) |
| 6 | `04864c6` | candidate ACCEPT WITH FINDINGS; reports REJECT pending correction | findings 2, 4 and 5 FIXED; stale code-tip and "A" wording, UI refusal label and reasoning-character count corrected in the next commit |
| 7 | `d6537c5` | candidate ACCEPT WITH FINDINGS; reports REJECT pending correction | four round-6 corrections verified; remaining: the receipt and the regression table still called the UI journey a demonstrated refusal → reworded to "not executed" in the next commit |
| 8 | `6fa5993` | candidate **ACCEPT WITH FINDINGS**; reports **ACCEPT WITH FINDINGS** | round-7 finding FIXED; minor: round-5 scope sentence narrowed in the next commit |

Every Codex finding was checked against source before repair. Codex could not run tests in its sandbox; its verdicts
rest on source inspection. The test results above come from this session's own runs.

## 5. Processes and state left on the PC

- Integrated server for the final installation: `uri-ws-final` on 127.0.0.1:18300, under the C1 gates. A development
  process; stop it by PID when no longer needed.
- Runtime v1: stopped (`STOPPED_CLEAN True`). The GPU was left free.
- Untouched: the legacy `\URIServer` on 8000, Ollama, shortcuts and scheduled tasks, other sessions' worktrees and
  processes (Innovation Lab 18481/18482/18490/18491; the Adaptive Runtime benchmarks).
- Disposable trees this session created: `uri-ws-rt` (development), `uri-ws-final` (final runtime), `uri-ws-gate`,
  `uri-ws-gate2` (gates), `wsa` (review clone). All are registered worktrees or clones of the shared repo and can be
  removed with `git worktree remove --force <path>` (clones: delete the folder).

## 6. Open owner decisions

Production cutover and `\URIServer` containment; pushing or merging this branch; a GPU-sharing policy across
sessions (GPU-1); wiring the OI perf monitor or a recovery control (PERF-W1, R-BUSY); the dashboard Brain card
(L-DASH); physical gates PA-1..PA-13; paid-API activation (disabled by design).

## 7. Publication and hardening (2026-10-09)

### 7.1 Publication of the accepted integration (done)

`integration/working-system-20261008` was pushed to the canonical repository `uri-repo`
(`https://github.com/sche004-cyber/Uri.git`) as a NEW branch, no force: remote ref = `68cac3d50b0bd63c833704504c2c59bb43a9b782`.
A fresh single-branch clone showed the same commit and tree `22c9492c05caad7751962350adfcfb6942e49bfb`. Gates before
the push: `037229c` ancestor, `ws_frozen_check` ok (121/121, no protected path changed), every path in `037229c..68cac3d`
attributable to the UI candidate, the OI candidate or the documented WS files, `git fsck` clean.

### 7.2 Hardening branch

Branch `integration/ws-hardening-20261009` (worktree `C:\Users\cheta\Development\uri-ws-hardening`), from `68cac3d`.
Key commits: implementation `f566e03`, `822aa73`, `99f8041`, `9c0bea5`, `82f75e5`, `938c287`, `e6eddf7`; Codex
repairs r1 `079bf0d`, r2 `550843a`, r3 `f987025`, r4 `f8dd67b`, r5 `9808fb6` (round 6 ACCEPT); live-validation fixes
`1af99e4`, `2083724`; Codex repairs r7 `47c1b6d`, r8 `b5fd75c`, r9 `9ae28f4` (round 10 ACCEPT WITH FINDINGS);
line endings `1401aba` (content-identical); documentation and evidence after that (`git log 1401aba..`).

Changed accepted files: the two WS-D3 scope guards (four exact paths added each: `scripts/ws_brain_host.py`,
`tests/ws/test_ws_hardening.py`, `uri_operational_intelligence/brain_health.py`, `uri_operational_intelligence/gpu_lease.py`)
and `scripts/oi_materialize_test_runtime.py` (copies the host). `worker_bridge.py`, the integrated worker, the launcher,
the WS Dart files and the Dashboard tile are WS-owned. No frozen Phase 1 file, no `uri_core/`, `uri_supervisor*/`,
`uri_harness_adapters/` or `model_lab/integration/` path changed (frozen check at the tip: ok).

### 7.3 Gates and integration decision

| Gate | Result |
|---|---|
| Independent review | Codex hardening round 10 ACCEPT WITH FINDINGS at `9ae28f4` (code); documentation finding repaired |
| Flutter full / OI+WS Python / hardening tests | 313 passed 3 skipped / 226 passed 20 skipped / 44 passed |
| Chain phase2 / authority / phase1-scope / residue | PASS / PASS / PASS / PASS (gate tree from `2083724`) |
| Chain phase1-full outcome identity | **NOT ESTABLISHED** (two environment/fixture outcome changes in run 1; run 2 cut off by SAFE-1 hang 3) |
| Safety | **SAFE-1 open**: three unclean hard hangs of the PC on 2026-10-09, cause unknown |

**Integration decision:** the canonical development branch `integration/git-sync-20261008` (`037229c`) was **not**
fast-forwarded. The mandate requires the combined regression gates to pass before integration, and phase1-full
identity was not re-established; SAFE-1 is an unresolved safety question. The hardening branch is published as a
separate candidate branch only (§7.4), to protect the work against further unclean shutdowns. No production cutover,
no shortcut, task or `\URIServer` change, no paid API, no force push.

Rollback: nothing to roll back on the canonical branch; the candidate branch can be deleted by the owner.

### 7.4 Candidate branch publication

(Filled with the remote confirmation.)

### 7.5 Processes and state

After the 13:57 reboot no process of this phase runs: no Brain host, no integrated server (`uri-ws-hard`, port 18301),
no idle Ollama started by this phase. Disposable trees: `uri-ws-hard` (runtime), `uri-ws-gate3` (gate), `wsa` (review
clone); removable by the owner. The machine-wide lease record (`%LOCALAPPDATA%\URI\gpu\lease.json`) still names the host
that died in hang 2; its OS lock is free, so the next holder records the stale recovery.
