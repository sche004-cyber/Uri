# URI Implementation Status Ledger — git location view, 2026-10-08

This ledger answers one question per item: what is its recorded status, and where does it live in git. It does not change any milestone status. Status words are quoted from the named verdict document or commit; "not re-verified" means I read the commit record but not the verdict document.

Legend for "Git before sync": **GH** = on GitHub; **GH-side** = on GitHub only on an unmerged side branch; **LOCAL** = committed locally only; **NONE** = uncommitted files only.
"After sync (proposed)" names the local candidate branch built on 2026-10-08. Nothing has been pushed.

## Core lineage (anchor `e8e3b65`)

| Item | Recorded status | Verdict source | Exact identity | Git before sync | After sync (proposed) |
|---|---|---|---|---|---|
| ARN.1 Deterministic Narrowing Core | DONE, VERIFIED | `docs/plans/ARN_1_STATE.md` | `e8e3b65` | GH (origin/master) | unchanged |
| Phase 0 runtime inventory and consolidation plan | Stage 1 evidence; recommends `e8e3b65` anchor | `CONSOLIDATION_PLAN.md` (Phase 0 outputs) | 26 files, 2026-10-05 | NONE (legacy master worktree) | integration A2 `44de9b3` |
| Phase 1 C1 Runtime identity / launcher authority | Part of frozen Phase 1 Core | `docs/plans/PHASE1_FINAL_CLOSURE_REPORT.md` §10 | zip `31a34dcb…f7` | NONE | integration A1 `925ad45` |
| Phase 1 C2 Client identity / state boundary | Part of frozen Phase 1 Core | same | same | NONE | A1 |
| Phase 1 C3 Client persistence / worker | Part of frozen Phase 1 Core | same | same | NONE | A1 |
| Phase 1 C4 Client-local harness execution | Part of frozen Phase 1 Core; native auth/containment remain documented limitations | same + fifth review §10 | same | NONE | A1 |
| Phase 1 C5 Intelligence loop incl. Intent Discovery | Part of frozen Phase 1 Core | same | same (`uri_core/core/intent_discovery.py`) | NONE | A1 |
| Phase 1 C6 UI integration contract, C7 cutover requirements | Part of frozen Phase 1 Core; cutover NOT performed | same | same | NONE | A1 |
| **Phase 1 Core freeze** | **A. PHASE 1 CORE FREEZE ACCEPTED** (2026-10-05) | same | same | NONE | A1 |
| **URI Resident Intelligence Runtime v1** | **FROZEN, verdict A STOCK** (User ruling 2026-10-07) | `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` §17 | 537 files; no freeze-time hash manifest | NONE | integration A3 `f791d65` |
| Phase 2A durable supervisor (`uri_supervisor/`) | Implemented, tested; NOT FROZEN, NOT CUT OVER | `docs/plans/PHASE2A_REPORT.md` | inside r6 `9a0be52c…` | NONE | integration A4 `02fa0e1` |
| Phase 2B supervisor bridge (`uri_supervisor_bridge/`) | Implemented, tested; not frozen | `docs/plans/PHASE2B_REPORT.md` | inside r6 | NONE | A4 |
| Phase 2C native qualification | Codex CLI NATIVE QUALIFIED run-scoped; Claude CLI BLOCKED (login) | `docs/plans/PHASE2C_NATIVE_QUALIFICATION_REPORT.md` | inside r6; checkpoint `4e812653…` | NONE | A4 + A5 |
| **Phase 2D composition** | **PHASE 2D ACCEPTED — MORE PHASE 2 SLICES REMAIN** (Codex round 3) | `evidence/phase2d_review/` | `cbec537a…68688d` | NONE | A4 (via r6) + A5 |
| **Phase 2 UI/operations** | **UI/OPERATIONS SLICE ACCEPTED — MORE PHASE 2 WORK REMAINS** (Codex round 7, 2026-10-08) | `evidence/phase2ops_review/round7/CODEX_REVIEW_round7.md` | `9a0be52c…affb50a` | NONE | A4 + A5 `6b2900e` |
| **Phase 2 closure (phase2close)** | **PHASE 2 CLOSURE ACCEPTED — PHYSICAL/OWNER GATES PENDING** (Codex closure round 6, 2026-10-08 08:30); not frozen, not cut over | `evidence/phase2close_review/round6/CODEX_REVIEW_round6.md` | `fcd0d72e…71298` (candidate -f) | NONE | integration A7 `b4a5977` + A8 evidence `e4d8408` + A9 post-acceptance docs `2325ad7` |
| Deferred for owner | Human UI click, client-profile login, power-loss qualification, EXE-1 decision, cutover | Phase 2 reports | — | — | — |

## Desktop mainline and side branches (uri-repo)

| Item | Recorded status | Exact identity | Git before sync | After sync (proposed) |
|---|---|---|---|---|
| M33, M33.1, M33.2 B/B.1/B.2 | CLOSED / ACCEPTED (tracker) | history before `5bbf738` | GH | unchanged |
| M33.3 | Frozen (`291c9da` "repair and freeze qualified offline contracts"); not re-verified | `291c9da` | GH | unchanged |
| M33.3-R audit worktree edits | Not accepted | `d1feaf7` + 5 files | LOCAL commit + NONE | `preserve/m33-3-r-audit-candidate-20260927` |
| M35 URIv1 parallel architecture | Skeleton/contracts committed; A2.x research `VERIFICATION_READY`, research only | `70e6065` (origin) / `405db1f` (uri-repo) + `_V1` files | GH + NONE | research files in `preserve/v1-harness-voice-research-20261004` |
| M36–M38 batch | CLOSED_FROZEN at `bd7c450`, ACCEPT_WITH_DOCUMENTED_LIMITATIONS | `5bbf738` | GH | unchanged |
| M39 R0 | R0 closing gates recorded; not re-verified | `c716f80` | GH | unchanged |
| M37-L4 | User acceptance recorded; not re-verified | `3fefb91` | GH | unchanged |
| Desktop repairs, Edge-first social route, Google/Gmail/PPT features | Commits with Codex audit repairs; not re-verified | `3c8087b..0699cb6` | GH | unchanged |
| INT-ARN-1 slices A–D | Implemented; Codex audit rounds 1–4 and amendment recorded; final acceptance not re-verified | `eb73693` | GH | unchanged |
| Presentation variants, document layout, approval result (2026-10-03) | Review package pending; NOT accepted | 57 files on `eb73693` | NONE | `preserve/desktop-int-uncommitted-20261003` |
| Dynamic planning slice 1 | CLOSED_FROZEN at `565eae8`, accept with documented limitations | `e4dea8c`; review `43101f8` | GH-side | unchanged; not integrated |
| Dictation | Feature and qualification evidence; not re-verified | `f1e13e9` | GH-side | unchanged |
| Harness-first edge | Experimental | `86de4c0` (GH-side), `69ef0e4` (LOCAL, remote deleted) | GH-side / LOCAL | unchanged; push of `69ef0e4` needs decision |
| Edge pair | Owner decision NOT QUALIFIED | `e0950d4` | GH-side | unchanged |
| Desktop core fixes | Experimental; "needs frozen-scope authorization" | `98abdd0` | LOCAL | unchanged; push needs decision |
| Running-app snapshot 2026-10-01 | Preservation | `a91e0e4` (GH), `869fae5` (LOCAL, adds graphify files), `71edc17` (LOCAL) | GH / LOCAL | unchanged |
| WIP batch 3 | Partial, unreviewed (Codex quota) | `535135d` | GH-side | unchanged |

## Work on superseded base `62d564c`

| Item | Recorded status | Location | Git before sync | After sync (proposed) |
|---|---|---|---|---|
| Desktop Claude Code harness qualification (2026-10-02) | Provisional; independent review pending | `_V1` | NONE | `preserve/v1-harness-voice-research-20261004` |
| Harness desktop completion (2026-10-03) | Provisional, acceptance blocked | `_V1` | NONE | same |
| Camera/voice/Gemma (2026-10-04) | Partial, non-milestone; acceptance pending | `_V1` | NONE | same |
| Intent clarification plan (2026-10-04) | DRAFT_FOR_USER_APPROVAL; direction "MINIMAL EXTENSION" accepted for planning only | `_V1` | NONE | same |
| Harness / Connections / Console (2026-10-03) | PARTIAL / ACCEPTANCE BLOCKED | harness-connections-console worktree | NONE | `preserve/harness-connections-console-20261003` |
| Experimental intent workflow (2026-10-04) | SUPERSEDED_BY_PHASE1_C5 | intent-discovery worktree | NONE | `preserve/intent-discovery-20261004` |
| M37 qualification JSON edits | Superseded line `a87e158` | uri-batch-candidate | NONE | `preserve/batch-candidate-m37-qual-20260928` |
