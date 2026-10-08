# URI Git / PC Cleanup and Quarantine Manifest — 2026-10-08 (round 2)

This manifest records the state of every URI-relevant item on the PC and in Git after round 2, what was done,
and what still waits for the owner. **Nothing was deleted, disabled, moved or stopped in round 2.** Round 1's
reversible containment (secret ACL hardening, git exclusion rules) stays in place. Detailed per-item
classifications: `URI_PC_CONTAMINATION_AUDIT.md` (PC) and `URI_SALVAGE_AND_RETIREMENT_LEDGER.md` (capabilities).

## 1. Re-verification of the previously reported issues (2026-10-08 ~15:00 IST)

| Reported issue | State now | Evidence |
|---|---|---|
| Legacy `uri-agent` master served by scheduled task `\URIServer` | **Still true.** Task `Running`; PIDs 8476 → 13544 → 13660 (`uri-agent\.venv\Scripts\python.exe scripts\run_uri_server.py --port 8000`) since 2026-10-07 17:34; listener 127.0.0.1:8000 | `Get-ScheduledTask`, `Win32_Process`, `Get-NetTCPConnection`; checker `live_report_20261008_oq.json` |
| UI builds share preferences pointing at `127.0.0.1:8000` | **Still true** (`%APPDATA%\com.example\uri_ui\shared_preferences.json`, checker finding `ui_server_binding`) | checker |
| Competing canonical and legacy worktrees | **Still present**, now with one difference: the accepted Phase 2 tree is in Git, so the Phase 2 worktree is no longer the only copy. 14 registered worktrees (list below) | `git worktree list` |
| Frozen `fake_executor.py` process (PID 9060) | **Gone.** No `fake_executor` process exists; no action was taken by this session | `Win32_Process` |
| Ollama service appeared during testing | Ollama **app** (not a Windows service) started 09:42:03 by `cmd /c "...\ollama app.exe" --hide --fast-startup`; `ollama serve` PID 15272 on `:::11434`; **no model loaded**. Ollama has a Startup-folder shortcut and an auto-updater (v0.40.1 downloaded, pending). It is a shared tool, not a URI runtime | Ollama `app.log`, `ollama ps`, Startup folder |

Live checker (normal mode) at the time: `VERDICT CONTAMINATED`, transitional findings = the task, two shortcuts,
three legacy server processes, the 8000 listener and the UI binding (all `TRANSITIONAL_LEGACY`, expected until
P-2/P-3); Runtime v1 listener `AUTHORIZED` (this session's reproduction benchmark); the benchmark's Python runner
`DONOR_ONLY` (it runs from the Phase 1 integration worktree's `model_lab`, by design flagged); Ollama
`SHARED_DEPENDENCY`; zero unaccounted findings.

## 2. Git state

| Ref | Before round 2 | After round 2 | Classification |
|---|---|---|---|
| `integration/git-sync-20261008` (GitHub) | `f8de153` | fast-forwarded to the canonical tip (SHA in the final audit) | CANONICAL INTEGRATION LINE |
| `canonical/candidate-20261008` (local) | `13bf68a` | same tip as the integration line | working branch of the canonical checkout |
| `accepted/*` tags | 6 local | 7 local (+ `accepted/phase2-oq-g-0b49d86d` → `6dea266`); pushed (see final audit) | immutable acceptance anchors |
| `donor/*` tags | 2 local | unchanged, **not pushed** (donor classification is an owner decision) | — |
| All other GitHub branches | as classified in `URI_CANONICAL_BRANCH_DECISION.md` §5 | unchanged | HISTORICAL / DONOR / EXPERIMENTAL / QUARANTINED |
| Local-only commits `69ef0e4`, `98abdd0`, `869fae5`, `71edc17` | local | unchanged (owner ruling: not pushed) | HISTORICAL / DISPUTED |

Worktrees (common dir `C:\Users\cheta\Development\uri-agent\.git`), unchanged, none removed:

| Path | HEAD | Classification | Note |
|---|---|---|---|
| `Development\uri-agent` | `e8e3b65` master (dirty) | TRANSITIONAL LEGACY (live server) | retire only after P-2/P-3 |
| `.codex\worktrees\uri-phase1-integration\uri-agent` | `e8e3b65` | PRESERVED (Phase 1 + Runtime v1 research, `work/c1/checkpoints`) | accepted content in Git; `work/c1/checkpoints` (provisional, 11–16 MB) still local only (CONS-14) |
| `.codex\worktrees\uri-phase2a\uri-agent` | `e8e3b65` branch `phase2a-durable-supervisor` | PRESERVED (Phase 2 dev) | accepted tree + evidence now in Git, byte-verified |
| `Development\Uri\_V1` | `62d564c` | DONOR (superseded base; voice/harness research) | snapshot on `preserve/v1-harness-voice-research-20261004` |
| `Development\uri-m37-m39-integration` | `eb73693` | DONOR (installed desktop UI) | retire only after C6 parity |
| `.codex\worktrees\batch-audit-canonical\_V1`, `harness-connections-console\_V1`, `intent-discovery\_V1`, `m33-audit-baseline\_V1`, `m33-audit-candidate\_V1` | `62d564c` / `c2f5839` / `d1feaf7` | HISTORICAL / DONOR | removal proposed per item (CONS-10) |
| `Development\uri-agent\.tmp_m33_1_batch4_baseline_5973f6d` | `5973f6d` | QUARANTINED (temporary) | proposed deletion (CONS-11) |
| `Development\uri-batch-candidate` | `a87e158` | HISTORICAL | preserved branch exists |
| `Development\uri-dictation` | `f1e13e9` | DONOR | — |
| `Development\Uri_edge_experiments` | `e0950d4` | EXPERIMENTAL / REJECTED | — |

## 3. Round-2 working directories (created by this session)

| Path | Purpose | Disposition |
|---|---|---|
| `Development\uri-canonical-evidence\oqgate\` | gate workspace (Git-materialized checkout + copied `.venv` + evidence copy) for the round-2 regression chain | chain outputs copied into Git (`docs/evidence/consolidation/`); the checkout and `.venv` copy may be removed after the owner has seen the results — they are reproducible from Git |
| `Development\uri-canonical-evidence\inference_repro\` | comparison script and outputs for the Runtime v1 reproduction | outputs copied into Git |
| `model_lab\evidence\runs\repro20261008_*` (Phase 1 integration worktree) | reproduction benchmark runs | additive; copied into Git |

## 4. Quarantine and cleanup awaiting the owner (RED, unchanged)

| Item | Prepared action | Reversal |
|---|---|---|
| CONS-1 `\URIServer` | `scripts\uri_containment.ps1 -Apply` exports XML then disables | `-Restore` |
| CONS-2 `URI.lnk` ×2 | same script moves them to a backup folder | `-Restore` |
| CONS-3 running legacy server | stop at an owner-chosen time | restart task / log on |
| Ollama autostart (new, optional) | remove the Startup shortcut, or leave Ollama as a shared tool. Not required: the Core is model-optional and the authority checker treats Ollama as shared | put the shortcut back |
| CONS-10 historical worktrees/branches | archive-tag, then remove per item | archive tags |
| CONS-11 `.tmp_m33` worktree, NVMe model copy | delete after hash check | D: copy / Git |
| CONS-14 `work/c1/checkpoints` | push a preserve branch or keep local | — |

No quarantined source is in any authorized execution path: the runtime checkout's changes over `e8e3b65` are
exactly the 273 overlay paths from Git (plus git-ignored `.venv` and `work/`), and the authority manifest's
authorized entrypoints are unchanged.
