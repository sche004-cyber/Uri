# Capability ledger update — development lifecycle (2026-10-11)

Ladder as in `docs/integration/final_20261010/CAPABILITY_LEDGER.md`. Claimed only with COMPLETED_WITH_RESULT evidence.

**Status of the skill:** integrated into canonical `integration/git-sync-20261008` at `ce1a90c` (DEV-LIFECYCLE-1,
independent ACCEPT, receipt in `LIFECYCLE_QUALIFICATION.md` §3). DEV-LIFECYCLE-2 (Windows support, canonical remote
by URL) is recorded in §4 of that file.

| Capability | Linux | Windows (owner's PC) | Evidence | Not yet |
|---|---|---|---|---|
| `uri-development-lifecycle` driver (state, evidence binding, gates vs baseline, repair discipline, integration policy, receipts) | TESTED; independent ACCEPT; INTEGRATED (`ce1a90c`) | NOT VERIFIED: before DEV-LIFECYCLE-2 it crashed after every gate/worker (F1) and no review could count (F2), found on the PC | `LIFECYCLE_QUALIFICATION.md` §1-4 | Windows qualification run (`tests/dev_workflow` + one real DEVTEST round on the PC) |
| Worker/command containment | TESTED (child subreaper + orphan sweep) | TESTED on the PC (Job Objects, DEV-LIFECYCLE-2): the 5 `windows_only` real-job tests passed at `f3706e03`; logic also TESTED on Linux with a fake kernel32 | `tests/dev_workflow/test_lifecycle_platform.py`; `LIFECYCLE_QUALIFICATION.md` §4 | containment inside a real milestone run on the PC (DEVTEST round) |
| Canonical remote by URL (`canonical_url`) | TESTED (DEV-LIFECYCLE-2) | NOT VERIFIED | `tests/dev_workflow/test_lifecycle_remote.py` | — |
| Independent reviewer launch (`claude_cli`) | TESTED live (milestone reviews in the cloud) | IMPLEMENTED: the real npm install resolves to `claude.exe` behind `claude.cmd` and is launched directly (W-2); a live reviewer round NOT VERIFIED (bootstrap) | demo 2 sessions R1/R2; DEV-LIFECYCLE-1 §3; `test_lifecycle_windows_cli.py` | Windows DEVTEST round |
| `codex_cli` provider | IMPLEMENTED, NOT VERIFIED | NOT VERIFIED | — | Codex optional; out of quota |
| Status as A2UI surface | TESTED (validates against `uri_a2ui`) | not run | `test_status_surface_is_valid_a2ui` | not wired into the Developer Console UI |
| GPU-gated gates via `gpu_lease` | TESTED (lease-unavailable path only) | NOT VERIFIED | `test_gpu_gate_without_lease_blocks` | lease-held path on the PC |

**Known limits (not covered by containment on either platform):** processes started by other routes (Windows: Task
Scheduler, WMI, services, COM out-of-process servers; Linux: systemd-run, cron/at, D-Bus activation, an
already-running daemon acting on a worker's request). See `DEV_LIFECYCLE_2_PLAN_AND_ACCEPTANCE.md`.
