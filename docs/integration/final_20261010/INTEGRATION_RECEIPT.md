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

| Item | Value |
|---|---|
| Pushed | 2026-10-10, `git push uri-repo cb7f3bd:refs/heads/integration/git-sync-20261008` → `54ad7be..cb7f3bd` (fast-forward) |
| Integration branch | `integration/final-qualification-20261010` pushed to `uri-repo` |
| Fresh-clone verification | the cutover GREEN dry run (`CUTOVER_PLAN.md` §2a with development paths) cloned `github.com/sche004-cyber/Uri`, checked ancestry, checked out `cb7f3bd` with a clean tracked tree, tree `cdf1b1b326454a4e112abb069f0455d7535300d4` (= local `cdf1b1b326454a4e112abb069f0455d7535300d4`); materialized, provisioned from PowerShell, built the UI and passed the launcher self-test with `real_installation.ok` (149 s; `evidence/cutover_dryrun_console.txt`). The dry-run trees `uri-cutover-dryrun-src-cb7f3bd` / `-rt-cb7f3bd` are development directories, not an installation in use |
| This receipt's own commit | follows `cb7f3bd` on the integration branch (docs only); the canonical branch is fast-forwarded to it after this record |
