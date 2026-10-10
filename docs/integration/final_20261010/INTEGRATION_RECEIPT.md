# Final integration receipt (2026-10-10)

Recorded by Claude, the final integration session. Codex built none of this code.

## 1. What is integrated

| Item | Value |
|---|---|
| Canonical branch | `integration/git-sync-20261008` on `uri-repo` (`github.com/sche004-cyber/Uri`) |
| Canonical tip before | `54ad7be` (tree `786f8de`); verified by fetch and ancestry on 2026-10-10 |
| Method | fast-forward to `integration/final-qualification-20261010`. No force, no rebase |
| Code changes | P-GOV-1: `gpu_lease advise --window`; UI-first launcher; `-UiRoot` candidate rule; `Wait-UiWindow`; `capture_ws.ps1` advisory. Workspace rail orb centred and enlarged (owner request). INT-F1: truthful A2UI handoff reply, companion state cleared for handoffs that produced nothing |
| Not changed | `uri_core/`, `uri_supervisor*/`, `uri_harness_adapters/`, `model_lab/integration/`, root `.gitignore`, the Runtime v1 profile, the companion-voice `rnd/` runners (handed over), the scheduler activation state |

## 2. Independent review (Codex, gpt-6-sol, medium, read-only)

| Unit | Rounds | Final verdict |
|---|---|---|
| P-GOV-1 | r1-r10 REJECT (all repaired), r11 after the scope cut | ACCEPT WITH FINDINGS (2 LOW, repaired) — `P_GOV_1_AUDIT.md` |
| Rail orb + INT-F1 | r1-r4 REJECT (repaired) | r5 ACCEPT |
| Whole integration `54ad7be..HEAD` (incl. staging record and cutover plan) | r1-r6 REJECT (evidence gap, cutover plan steps; repaired) | r7 ACCEPT |

## 3. Gates

| Gate | Result | Evidence |
|---|---|---|
| `tests/ws tests/oi tests/a2ui` | 596 passed, 22 skipped | `evidence/gates_orb_intf1_r4.txt` (at `08a9192`; later commits change docs only) |
| `tests/scheduler` (base interpreter, SCH-ENV-1) | 71/71 | same |
| Flutter full | 511 passed, 5 skipped | same |
| Frozen check | 121/121, no protected-path change | same |
| Materialized runtime: phase2a guard + ws/oi/a2ui | 599 passed, 26 skipped (first staging pass) | `STAGING_QUALIFICATION.md` gate note |
| Staging (live) | Qualified for the automatable criteria | `STAGING_QUALIFICATION.md` |

The accepted Phase 1/Phase 2 regression chain (`phase2close_chain.py`) was not rerun. Its frozen and protected
inputs are unchanged (frozen check), and none of the code changed here is in its scope. The chain evidence of the TI
integration (`85bf700`, ALL_PASS) is reused.

## 4. Not activated (unchanged)

Real-Claude scheduled execution (BLOCKED: CLI login); the `URIScheduler` logon task; festival jobs and the 09:00 IST
default; production cutover (`CUTOVER_PLAN.md`, plan only); the legacy `\URIServer` on port 8000, its task and
shortcuts were not touched. Human microphone qualification: NOT VERIFIED (deferred, owner unavailable).

## 5. Push record

(Filled after the verified fast-forward.)
