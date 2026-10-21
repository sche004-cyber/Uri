# Milestone Manager — implementation plan and status

Plan written 2026-10-21 and executed in the same session under the owner amendment (DEC-092 in the rehearsal
ledger). Each phase lists acceptance criteria (ids from `ACCEPTANCE_CRITERIA.md`), status and evidence.

## 1. Phases

| Phase | Scope | Criteria | Status (2026-10-21) | Evidence |
|---|---|---|---|---|
| 1 Discovery + design | capability map, alternatives, data model | R1-R7 | DONE | `MILESTONE_MANAGER_DISCOVERY.md`, `..._ARCHITECTURE.md`, `..._DATA_MODEL.md` |
| 2 Store + model + service | event store, guards, decisions, approvals, assignments, conflicts | F1-F12, F16, F17 | DONE | `scripts/dev_workflow/milestones/{store,model,service}.py`; tests |
| 3 Views + CLI + importers | status, resume, ready, JSON/A2UI export, P0 and lifecycle importers | F13-F15, F18 | DONE | `views.py`, `cli.py`, `importers.py`; tests |
| 4 Verification | MM tests, full `tests/dev_workflow` regression, frozen check, migration rehearsal on the real P0 registers, perf | N1-N5 | see §3 | `docs/milestone_manager/evidence/` |
| 5 Independent review + repair | fresh isolated subagent reviews until ACCEPT / AwF on the exact commit | L1, L2 | see `MILESTONE_MANAGER_HANDOFF.md` | `docs/milestone_manager/reviews/` |
| 6 Promotion (owner) | choose ledger location; build the authoritative ledger; declare markdown registers frozen-as-history | — | NOT STARTED: needs owner decision (rehearsal approval request "promote ledger") | — |
| 7 Canonical integration (owner) | fast-forward or merge into `integration/git-sync-20261008` | L4 | NOT STARTED: separate owner authorisation required | — |
| 8 Follow-ups (other milestones) | Lifecycle V3 fsync + lock (MM-F4); V3.1 emits/links tasks via `milestone_ref`; Mission Control reads `uri-mm-status/1` | — | proposed | — |

## 2. Integration prerequisites (owner amendment) and their state

| Prerequisite | State | Note |
|---|---|---|
| P0 audit prerequisites reconciled | NOT MET | P0 records live only on the local branch `audit/p0-comprehensive-20261021` @ `8e1d6324` (OPEN-09: push needs owner). MM reads them by path + commit + SHA-256 and does not need them in canonical, but the register that MM imports is not yet a canonical record. Also POL-P0-1 (canonical SKILL.md says subagent reviews are not an independent ACCEPT) is unresolved (OPEN-05) and directly affects whether this milestone's subagent acceptance counts for canonical integration. |
| Required tests and regression gates pass | see §3 | |
| Independent acceptance documented | see handoff | subagent tier (owner amendment says subagents qualify) |
| Frozen-core integrity preserved | MET | `scripts/ws_frozen_check.py` at `7ab9263c`: `unapproved_protected_changes: []`, exit 0; MM diff is additions only (13 files, 0 modified) |
| No unresolved blocking findings | see handoff | |
| Separate owner integration authorisation | NOT GIVEN | development authorisation is not merge approval |

Therefore the accepted candidate stays isolated on `milestone/milestone-manager-20261021`.

## 3. Verification record

| Check | Command | Result |
|---|---|---|
| MM tests | `PYTHONPATH=. python -m pytest -c scripts/phase2d_pytest.ini --rootdir=. tests/dev_workflow/test_milestones.py -q` | 49 passed (2026-10-21, Windows, Python 3.13.15) |
| N3 performance | `test_n3_performance_10k_events` | 10,001 events: rebuild 0.283 s, status 0.05 s, segment 4.4 MB |
| Frozen core | `python scripts/ws_frozen_check.py` | ok, exit 0 (`D:/uri-dev/mm-evidence/frozen_check_7ab9263c.log`) |
| Full dev_workflow regression | same pytest over `tests/dev_workflow` in detached worktree `D:/uri-dev/mm-gate-7ab9263c` | recorded in the handoff when complete |
| Migration rehearsal | `docs/milestone_manager/migration/run_rehearsal.py` | 217 events, verify ok, 93 decisions, 85 register rows, 12 open owner questions; outputs in `evidence/rehearsal/` |

Note on test invocation: with `python -I` the repository root is not on `sys.path` in this checkout, so the existing
`tests/dev_workflow/test_lifecycle.py` fails collection too; `PYTHONPATH=.` (or running from the root without `-I`)
is required. This is pre-existing, not introduced here.

## 4. Concurrency of the roadmap (requirement F)

Hard dependencies recorded in the rehearsal ledger (others are priority only):

| Milestone | Hard dependency | Can run concurrently with | Shared-resource conflict |
|---|---|---|---|
| MILESTONE-MANAGER (P0) | — | everything | none (stdlib, CPU-light) |
| LIFECYCLE-V3-1 (P1) | — (contract with MM) | everything | `scripts/dev_workflow/` package: different files; coordinate via messages |
| PERSONAL-DATA-SOVEREIGNTY (P2) | — | all | touches key stores (D10) also used by Office/OI: serialise with any Office/OI repair |
| WRITING-INTELLIGENCE (P3) | — (P2 only for remote processing) | P0-P2, P5-P8 | Brain GPU for live tests: lease |
| MEETING-INTELLIGENCE (P4) | PERSONAL-DATA-SOVEREIGNTY | after P2 | voice/GPU lease |
| OFFICE-CLIENT-INSTALLER (P5) | — | all | packaging touches launchers: coordinate with Working System owners |
| MISSION-CONTROL (P6) | MILESTONE-MANAGER | after P0 accepted | Flutter UI files: serialise with any UI milestone (Ember, Controls) |
| SKILL-COMMAND-CENTER (P7) | MILESTONE-MANAGER | after P0 | Flutter UI + skills tree |
| DEVELOPER-STUDIO (P8) | MILESTONE-MANAGER, LIFECYCLE-V3-1 | after P0, P1 | UI |
| ADVANCED-VISION-ASSIST (P9) | — (needs OPEN-04 decision, D14) | CPU-side design with all | GPU-exclusive live runs: never in parallel with P3/P4/P10 live runs |
| BRAIN-RUNTIME-OPTIMIZATION (P10) | — (needs OPEN-03) | design with all | GPU-exclusive; conflicts with every live Brain test |

## 5. Risks

| Risk | Likelihood | Effect | Mitigation |
|---|---|---|---|
| Agents bypass MM and edit segments by hand | low | chain breaks | `verify` refuses writes on a broken chain; git history shows the edit |
| An agent relays a fabricated owner approval | low | false approval | approval requires owner words + source; relaying actor recorded; INTEGRATED additionally needs the lifecycle integration record |
| Two ledgers diverge (rehearsal vs authoritative) | medium | confusion | only one promoted ledger; rehearsal homes are labelled and disposable |
| Markdown registers and ledger disagree before promotion | medium | split truth | markdown stays authoritative until promotion; re-import records revisions |
| Task duplication with V3.1 | resolved | — | DEC-093 split; MM never writes tasks |
| Secret-pattern false negatives | medium | secret stored | patterns cover common key formats; evidence stored as references only; review finding welcome |
| Windows `msvcrt.locking` semantics | low | lock failure | multiprocess test on Windows passes; POSIX path uses `flock` (code review only on this host) |

## 6. Rollback

MM adds files only (`scripts/dev_workflow/milestones/`, `tests/dev_workflow/test_milestones.py`,
`docs/milestone_manager/`). Rollback = revert the merge or fast-forward commit, or simply stop using the CLI. A
ledger home is data outside the code; deleting the code never deletes a ledger. The markdown registers are never
modified by MM, so they remain a complete fallback.
