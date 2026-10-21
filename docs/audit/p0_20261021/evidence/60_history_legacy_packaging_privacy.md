# P0 audit 60 - History, legacy (_V1) line, packaging, privacy, worktree hygiene

Auditor: Claude subagent (read-only), 2026-10-21. Repository: shared object DB `C:/Users/cheta/Development/uri-agent/.git`
(commands run from `D:/uri-dev/uri-p0-audit`). Canonical = `uri-repo/integration/git-sync-20261008` @
`ec2fab5493578a4f5a805642153d56b4d5ea59fa` (2026-10-18). Root = `e8e3b652` (2026-09-20, ARN.1 close).

Evidence classes: **VERIFIED-GIT** = SHA exists and its ancestry vs canonical was checked with `git merge-base
--is-ancestor` (ANC = ancestor of canonical, NOT = not an ancestor), or a path was checked with `git cat-file`/
`git ls-tree` on `ec2fab54`. **DOC-ONLY** = only a document/memory note claims it (HISTORICAL/REPORTED).
**VERIFIED-LIVE** = read-only host query on 2026-10-21. Status words are taken from the record; "accepted" never
implies "integrated" or "live-verified".

## (a) Acceptance criteria

1. Every _V1 / M33-M39 capability and every `preserve/*` branch has a disposition (salvaged / donor / retired /
   pending) and at least five ledger claims are checked against `ec2fab54`.
2. Chronology M1..M39 + Phase 1/2 + all post-consolidation programs: one row each, key SHA checked for existence and
   ancestry, record path named, evidence class stated.
3. Packaging/distribution: each artifact named in scope located (path present/absent on canonical) with status.
4. Privacy/personal-data: each existing mechanism located by path; absence stated where searched and not found.
5. Consolidation physical/owner acceptance items (PA-1..PA-13, owner decisions, engineering items) each mapped to a
   later closure or marked open, with evidence.
6. Worktree hygiene: `git status --porcelain | wc -l` for every listed worktree path that exists; unpreserved work
   flagged (best effort); no file contents or secrets printed.
7. Gaps that limit any verdict listed explicitly.

## (b) Milestone chronology

ID scheme: `H-` historical M-series, `V-` _V1/desktop line, `P-` Phase 1/2, `I-` post-consolidation.

| ID | Name | Dates | Status (per record) | Key commit / tag | Record path | Class |
|---|---|---|---|---|---|---|
| H-M1..M5 | Pre-M6 (Phase 0-4 architecture checklist) | <=2026-08-29 | not tracked in repo; external checklist only | none | `URI_MILESTONE_TRACKER.md` (refers to OneDrive `URI_MILESTONE_CHECKLIST.md`) | UNKNOWN |
| H-M6..M21 | Capability awareness .. context window (M6,M7,M8A,M10A,M11-M21) | 2026-09-04..09 | DONE (M6-M8A-fix "Verified 5 Sep"; rest commit checkpoints) | `89169c1`..`5957eb2`; root `06ba82c2` 2026-09-04 | `URI_MILESTONE_TRACKER.md` table | DOC-ONLY (SHAs not individually checked) |
| H-M22.x | M22.1-M22.9 roles, authz, grants, providers/keys, router, metering, modes, PWA | 2026-09-10..12 | DONE, VERIFIED (M22.9 pending device check) | `a647c396`, `34839ce`, `8acbad5`, `ddbbb5e`, `69c8df3`, `5b97e12`, `35ac98b`, `9c848fe` | `URI_MILESTONE_TRACKER.md`; `docs/plans/M22.*_STATE.md` | DOC-ONLY (a647c396 seen in log) |
| H-M23 | Graph Intelligence foundation | 2026-09-12 | DONE, VERIFIED (self-audit) | `dfee5a8` | tracker | DOC-ONLY |
| H-M24..M30 | Canonical agent loop migration -> cutover/legacy retirement; M30-PFC; M30.7C | 2026-09-12..14 | CLOSED / ACCEPTED (M30 readiness accepted by User) | `0da36dfa` (M22.5-M30.8 migration), `698a6cb2` | `docs/governance/URI_ACTIVE_MILESTONE.md` s1/s5a/s6a-b | DOC-ONLY |
| H-HUI | Hybrid UI prototype | 2026-09-17 | PAUSED / working prototype | `7bb916fb` tag `checkpoint-hybrid-ui-paused` (ANC) | ACTIVE_MILESTONE s1a | VERIFIED-GIT |
| H-M31 | Model & Brain UX | 2026-09-16 | COMPLETE, VERIFIED | `5c31d254` (ANC) | ACTIVE_MILESTONE s6d | VERIFIED-GIT |
| H-M32 | External capability / native tool loop | 2026-09-17..18 | VERIFIED, released | `9a483b4a` (M32 Batch C) | ACTIVE_MILESTONE s6f | DOC-ONLY |
| H-M33/M33.1 | External Capability Bridge; Real Integrations + Tools&Skills UI | 2026-09-18..20 | CLOSED / ACCEPTED | `1b7d8d83`..`631d630a` | `docs/plans/M33_1_REAL_INTEGRATIONS_EXTENSION_VALIDATION_PLAN.md` s13.H | DOC-ONLY |
| H-M33.2 | Edge foundation (A, B..B.4) | 2026-09-20 | A/B/B.1/B.2 CLOSED/ACCEPTED; B.3 `d395c1ca`, B.4 `eaf97c57` "close accepted" | `uri_core/core/edge`, `edge_lifecycle` present in root and canonical | tracker M33.1 note | VERIFIED-GIT (paths) |
| H-M34 | Model-native capability preservation | 2026-09-19 | DONE, VERIFIED, CLOSED | `14ff152a` (ANC) | ACTIVE_MILESTONE s6g | VERIFIED-GIT |
| H-ARN.1 | Deterministic narrowing core | 2026-09-20 | DONE, VERIFIED (Gemini audit) | `e8e3b652` = root (ANC) | `docs/plans/ARN_1_STATE.md` | VERIFIED-GIT |
| V-M33.3 | Unified interaction/clarification (S-slices, M33.3-R) | 2026-09-21..27 | identity accepted; M33.3-R audit edits preserved | `47af60a6` (NOT), `preserve/m33-3-r-audit-candidate-20260927` `8cc688ec` | _V1 line `docs/plans/M33_3_R_STATE.md` | VERIFIED-GIT (SHA) / status DOC-ONLY |
| V-M35 | URIv1 parallel architecture, A2.x research | 2026-09-18..27 | research VERIFICATION_READY (ledger) | `m35-uri-v1-parallel-architecture` `405db1f`; `5a8e2448` | ledger s3 | DOC-ONLY |
| V-M36 | URI-Memory minimum | 2026-09-28 | FROZEN (bd7c450) | tag `accepted/m36-m38-closed-frozen-bd7c450` -> `bd7c4506` (NOT) | salvage ledger s2 | VERIFIED-GIT (tag/ancestry) |
| V-M37 | Edge minimum (local-first social routing) | 2026-09-28..10-01 | FROZEN; re-frozen `b610dd06` (NOT); M37-L4 user-accepted | `5460d643`, `b610dd06` | ledger s2 | VERIFIED-GIT (SHA) |
| V-M38 | Harness execution capsules | 2026-09-28 | FROZEN (bd7c450) | `3501f856` | ledger s2 | VERIFIED-GIT (SHA) |
| V-M39 | Office demonstrator | 2026-09-28..10-01 | ACCEPTED R0 (record) | `7363ba54`, review `5d60ac21` (NOT) | ledger s2 | DOC-ONLY (status) |
| V-DP1 | Dynamic planning slice 1 | 2026-10-01 | CLOSED_FROZEN, never integrated | tag `accepted/dynamic-planning-slice1-565eae8` -> `565eae8b` (NOT; has `uri_v1/planning`); branch tip `e4dea8c1` | `URI_CANONICAL_BRANCH_DECISION.md` s5 | VERIFIED-GIT |
| V-HF | Harness-first edge experiment; edge pair | 2026-10-01 | EXPERIMENTAL; edge pair NOT QUALIFIED (owner) | `86de4c02` (NOT), `e0950d40` (NOT) | branch decision s5 | VERIFIED-GIT (SHA) |
| V-DICT | Dictation | 2026-10-02 | IMPLEMENTED + qualification evidence (record) | `f1e13e94` (NOT), tag `donor/dictation-f1e13e9` (only in `uri-canonical-candidate` clone) | ledger s2 | VERIFIED-GIT (SHA) |
| V-INT-ARN-1 | RAR clarification in desktop /ask + desktop fixes | 2026-10-02..03 | IMPLEMENTED, audit rounds 1-4 (record); desktop mainline | `eb736933` (NOT), `donor/desktop-mainline-eb73693` | ledger s2 | VERIFIED-GIT (SHA) |
| V-HCC/V1H | Harness/Connections/Console; _V1 harness+voice | 2026-10-03..04 | PARTIAL / ACCEPTANCE BLOCKED; provisional | `preserve/harness-connections-console-20261003` `f07f7d40`; `preserve/v1-harness-voice-research-20261004` `6aa9c30b` | ledger s3 | VERIFIED-GIT |
| P-1 | Phase 1 Core C1-C7 | 2026-10-05 (commit 10-08) | FROZEN; C7 cutover NOT done | `925ad45c` tag `accepted/phase1-core-freeze-31a34dcb` (ANC) | `docs/plans/PHASE1_C1_C7_REVIEW_PACKAGE.md` | VERIFIED-GIT |
| P-RT1 | Runtime v1 resident Brain | 2026-10-07 | FROZEN (owner, self-qualified) | `f791d65c` tag `accepted/runtime-v1-freeze-20261007` (ANC) | `docs/governance/consolidation/URI_INFERENCE_OPTIMIZATION_RECOVERY.md` | VERIFIED-GIT |
| P-2A..2D+ops | Supervisor, bridge, composition, UI/ops | 2026-10-07..08 | ACCEPTED (Codex r7) | `02fa0e15` tag `accepted/phase2-ops-r6-9a0be52c` (ANC) | OUTSTANDING s1 | VERIFIED-GIT |
| P-2CL | Phase 2 closure | 2026-10-08 | ACCEPTED (Codex closure r6) | `b4a59773` tag `accepted/phase2-closure-f-fcd0d72e` (ANC) | `docs/plans/PHASE2CLOSE_*` | VERIFIED-GIT |
| P-2OQ | Phase 2 operational qualification | 2026-10-08 | ACCEPTED (Codex OQ r7); physical gates pending | `6dea2665` tag `accepted/phase2-oq-g-0b49d86d` (ANC) | `docs/plans/PHASE2OQ_REPORT.md` | VERIFIED-GIT |
| P-CONS | Unified consolidation + GitHub publication | 2026-10-08 | PUBLISHED; `main` rename PROPOSED only (canonical still `integration/git-sync-20261008`) | `037229c1` (ANC) | `docs/governance/consolidation/*` | VERIFIED-GIT |
| I-ULC / I-OI / I-ORB | UI Living Companion; Operational Intelligence; Solar orb R&D | 2026-10-08 | AwF; merged into WS | `569cf7c6`, `9306dc11`, `07a2f380` (all ANC) | `docs/ui_phase/`, `docs/operational_intelligence/` | VERIFIED-GIT |
| I-LAB / I-AR | Innovation Lab; Adaptive runtime R1/R2 | 2026-10-08..09 | research, not integrated | `47b63f62` (NOT), `7d035aa1` (NOT) | branch-only | VERIFIED-GIT |
| I-WS | Working system integration | 2026-10-08..09 | Codex r8 AwF | `68cac3d5` (ANC) | `docs/working_system/WS_INTEGRATION_RECEIPT.md` | VERIFIED-GIT |
| I-WSH | WS hardening, canonical FF | 2026-10-09 | AwF; canonical | `71606148` (ANC) | `docs/working_system/canonical_integration/WS_CANONICAL_INTEGRATION_RECEIPT.md` | VERIFIED-GIT |
| I-COMP | Living companions / companion voice / settings | 2026-10-09 | INTEGRATED | `d7a052f8`, `c0fc8b90`, `f24d57ab` (ANC) | `docs/companions/` | VERIFIED-GIT |
| I-SCHED / I-A2UI / I-VOICE | Scheduler; A2UI; live voice | 2026-10-09 | INTEGRATED | `b02ed4f5`, `15874496`, `6b488305` (ANC) | receipts in `docs/scheduler`, `docs/a2ui`, `docs/voice/live` | VERIFIED-GIT |
| I-TI | Text Intelligence + WS hardening | 2026-10-09 | INTEGRATED (Codex rounds 11-14) | `2563ca58` -> `54ad7be7` (ANC) | `docs/integration/ti_ws_20261009/` | VERIFIED-GIT |
| I-FINAL | Final integration (P-GOV-1, INT-F1/F2) | 2026-10-10 | Codex ACCEPT / AwF; cutover plan PLAN ONLY | `ffdf5343` (ANC) | `docs/integration/final_20261010/` (`CUTOVER_PLAN.md`) | VERIFIED-GIT |
| I-VRAM10 / I-MU | VRAM efficiency research; multi-user app-host research | 2026-10-10 | research only | `09c4b8ff`, `31dbd92a`, `e49d5854` (all NOT) | `docs/research/m1_multiuser_app_host/` (branch only) | VERIFIED-GIT |
| I-DL1/DL2 | Dev lifecycle 1/2 (Windows) | 2026-10-11 | integrated; PC run blocked on CLI login | `ce1a90c0`, `cbdf3f2c`, `73bdbef1` (ANC); receipts `86221a2b` (NOT) | `docs/dev_workflow/` | VERIFIED-GIT |
| I-SEC | W1/A0, WS-FLAKE-1, SSRF-1, GRAPHIFY-LEAK-1, IDN-1/1b | 2026-10-12 | integrated | `03f0bf2c`..`1b5423bc` (ANC) | first-parent "integrate ..." commits | VERIFIED-GIT |
| I-ACL | Scheduler token ACL 1/2 | 2026-10-11 | not integrated | `df1c12f1`, `eaf3bf69` (NOT) | branch-only | VERIFIED-GIT |
| I-OFF-M1/M2 | Office M1 (Sheets), M2 | 2026-10-11..13 | Codex r13 ACCEPT (M2); integrated via office-m1-m2 / frozen-authorized | `6348b1b1`, `b51a3912`, `28897ee5`, `aa232e36` (ANC) | `docs/office/` | VERIFIED-GIT |
| I-FCV | Frozen Core live verification | 2026-10-14 | BLOCKED (FCV-01/03/07) | report outside repo (`uri-core-live-verification-20261014/`) | memory note | DOC-ONLY |
| I-FCVR | FCV recovery | 2026-10-15 | INTEGRATED (FF 7d3d0f63->85f6a0ec) | `85f6a0ec` (ANC); tag `preserve/fcv-r-reviewed-8d8005cc-20261015` | `docs/governance/fcv_recovery/` | VERIFIED-GIT |
| I-DL3 | DL3 UI-first, 3A Codex sandbox, 3B Flutter gates, 3C | 2026-10-15..16 | 3/3A/3B integrated; 3C stopped (duplicate) | `7d3d0f63`, `777f8d81`, `57f2d567` (ANC); `4ca4a02a` (NOT) | `docs/dev_workflow/` | VERIFIED-GIT |
| I-OFF-O2/U | Office unified O2 + completion/LOW | 2026-10-14..17 | integrated; live 64K PASS (qual tags) | `eaeb10c1`, `3e769fdf` (ANC); tags `qual/office-*-p2-64k` | `docs/office/unified/` | VERIFIED-GIT |
| I-UIV2 | UI V2 completion / post-integration / freeze | 2026-10-15..17 | FROZEN | `2eff03d0`, `7893aaed` tag `accepted/ui-v2-freeze-20261017` (ANC) | `docs/ui_v2/postint/` | VERIFIED-GIT |
| I-AF | Lifecycle auditor fallback | 2026-10-16..17 | integrated | `348677b7` (ANC) | `docs/dev_workflow/` | VERIFIED-GIT |
| I-EMBER | Ember fire companion v1 / v2 / v2.1 / integ | 2026-10-14..18 | v1/v2 fidelity NOT MET; v2.1 DEVELOPMENT COMPLETE; integ candidate qualified locally; **NOT integrated** (`docs/companions/fire` absent in canonical) | `89ccf461`, `b73bd26c`, `d6a83131`/`4a70d9e7` tag `preserve/ember-v21-final-20261015`, `0b853288`, `68061d85` (all NOT) | `docs/companions/fire/` (branch) | VERIFIED-GIT |
| I-QWEN38 | Qwen3.8 Brain experiment | 2026-10-16..17 | provisional rec; Qwen3.6 stays default | `9689a666` (NOT) | branch `research/qwen38-27b-brain-20261016` | VERIFIED-GIT |
| I-VRAM-R1 / I-RP | VRAM-R1 research; runtime profiles integration | 2026-10-17..18 | R1 accepted r3 (branch `7c7a7776`, NOT); code integrated `adeb6d08`; profiles canonical `cd4a7963` (ANC) | `adeb6d08`, `cd4a7963` | `docs/operational_intelligence/profiles_live/` | VERIFIED-GIT |
| I-QC | Brain Quick Controls + closure | 2026-10-18 | INTEGRATED; closure QCC-R2 AwF (4 LOW) | `0d599b6a`, `feaabe3f`, `ec2fab54` (ANC) | `docs/integration/qc_ember_20261018/`, `docs/operational_intelligence/brain_quick_controls/` | VERIFIED-GIT |
| I-UICT | UI controls & typography | 2026-10-18 | in progress, not integrated (2 uncommitted) | `e9ee7409` (NOT) | branch `milestone/ui-controls-typography-20261018` | VERIFIED-GIT |

Governance-record gap: `URI_MILESTONE_TRACKER.md`, `PROJECT_MEMORY.md`, `docs/governance/URI_ACTIVE_MILESTONE.md` were
last changed on canonical at `925ad45c` (Phase 1). No canonical milestone ledger covers anything after Phase 1; the
I-rows above are reconstructed from commits/receipts. M36-M39 rows exist only on the _V1/donor line.

## (c) _V1 / M33-M39 line disposition (consolidation 2026-10-08, re-checked on ec2fab54)

| Item | Ledger disposition | Check on `ec2fab54` | Current state |
|---|---|---|---|
| RAR deterministic binding (`uri_v1/turn/rar_*`, `uri_v1/reference_clarification/fingerprints`) | RETAIN via Phase 1 C5 | `uri_core/reference_binding/PROVENANCE.json` present: donor `eb73693`, donor_sha256 == ported_sha256, "import-path rewrite only" (12 donor_path entries + 8 in `tests/reference_binding/PROVENANCE.json`) | **SALVAGED** (only provenance-recorded port found) |
| INT-ARN-1 desktop clarification | DONOR (superseded for Core by C5) | `uri_desktop_seams` MISSING | DONOR, not ported |
| M36 URI-Memory (`uri_v1/memory`) | INTEGRATE via C5 | `uri_v1` MISSING entirely | **PENDING** (not ported); Core memory = M18 `uri_core/core/user_memory.py` (root) |
| M37 Edge (`uri_v1/edge`) | INTEGRATE via C5 | MISSING; `uri_core/core/edge*` present but identical lineage to root (M33.2), not M37 | **PENDING** |
| M38 harness capsules | DONOR | MISSING; Phase 2 supervisor/bridge present | DONOR (superseded path) |
| M39 Office (`uri_v1/office`) | INTEGRATE via C5/C6 | MISSING; `uri_office/` present but built new from Office M1 (`ce1a90c` base); no reference to `uri_v1/office` in `uri_office` or `docs/office` | **SUPERSEDED in practice** by new Office (no formal ledger update) |
| Dynamic planning slice 1 | INTEGRATE later | `uri_v1/planning` MISSING | **PENDING** (owner priority) |
| Dictation | DONOR | `uri_dictation` MISSING | DONOR; live voice (I-VOICE) is a separate implementation |
| Desktop features (Google onboarding, Gmail/Drive/Docs, PPT, uploads, Ollama residency) | INTEGRATE via C6 parity | not verified file-by-file | **PENDING / UNKNOWN** (CONS-9 / P2-6 "PLANNED"; L-5 in cleanup report) |
| Desktop UI build `uri_ui.exe` (`uri-m37-m39-integration`) | DONOR until C6 parity | `URI.lnk` still points there (LEGACY-2 OPEN, `docs/ui_v2/postint/02_FINDINGS_REGISTER.json`) | DONOR, still installed |
| Legacy launchers `Launch URI.bat`, `scripts/launch_uri.ps1`, `uri_server_ctl.ps1`, `run_uri_server.py` | QUARANTINE in place | all present on canonical | QUARANTINED (forbidden entrypoints per authority manifest) |
| `Launch URI Harness.bat`, `Launch URI Voice.bat` | DONOR, never launch | MISSING on canonical (exist untracked in `_V1`) | DONOR |
| WIP batch 3 `535135d2` | QUARANTINE | NOT ancestor | QUARANTINED |
| Home automation | nothing to salvage | n/a | none exists |
| Retirement | "No component is retired by this ledger" | no deletions observed; all branches still present | **nothing retired** |

`preserve/*` branches (all exist; tip == ledger SHA; parent == the source worktree HEAD, verified):

| Branch | Tip | Remote | Classification | Tracked edits in source worktree match? |
|---|---|---|---|---|
| preserve/v1-harness-voice-research-20261004 | `6aa9c30b` | uri-repo | DONOR-ONLY | yes; 13 newer untracked files not in it (graphify artifacts, git_sync copies identical to canonical, qwen38 docs found on `research/qwen38-27b-brain-20261016`) |
| preserve/harness-connections-console-20261003 | `f07f7d40` | uri-repo | DONOR-ONLY | yes, 0 extra |
| preserve/intent-discovery-20261004 | `2a7c2bcf` | uri-repo | DONOR (historical) | yes, 0 extra |
| preserve/m33-3-r-audit-candidate-20260927 | `8cc688ec` | uri-repo | HISTORICAL | yes, 0 extra |
| preserve/batch-candidate-m37-qual-20260928 | `20319310` | uri-repo | HISTORICAL | yes, 0 extra |
| preserve/desktop-int-uncommitted-20261003 | `a3dab218` | uri-repo | DONOR-ONLY | yes, 0 extra |
| preserve/running-app-2026-10-01 | `a91e0e4f` | origin | PRESERVED | - |
| preserve/running-app-2026-10-01-local-full | `869fae5d` | **local only** | HISTORICAL/DISPUTED | tracked yes; 26 later untracked files (all blobs present in object DB) |
| preserve/dev-lifecycle-3-pre-rebase(-2) | `b1e01db9`, `342ac731` | local only | not in ledger (post-consolidation) | - |

Tags `donor/desktop-mainline-eb73693`, `donor/dictation-f1e13e9` exist only in `C:/Users/cheta/Development/uri-canonical-candidate`
(not in the shared repo, not pushed - consistent with the publication receipt). Remote `uri-repo/ccr-cab5ed06-9hwyc4`
`0ca32908` (2026-10-12, "Thread stopped by owner") is NOT an ancestor and appears in no consolidation ledger (post-dates it).

## (d) Packaging / distribution status

| Artifact | Location (canonical unless stated) | Status |
|---|---|---|
| Installer (.msi/.iss/.wxs/.nsi/MSIX) | none found on canonical tree | **ABSENT** |
| `uri_core.zip` | repo root, from initial commit `06ba82c2` (2026-09-04), never changed | baseline snapshot, not a distribution artifact |
| `Launch URI.bat`, `scripts/launch_uri.ps1` | present | legacy, QUARANTINED |
| `Launch URI Working System.bat`, `scripts/launch_uri_working_system.ps1` | present (`d0819e38`, WS-D3) | development launcher with legacy refusal; not production |
| C1 launcher authority | `scripts/uri_server_launcher.py`, `uri_server.ps1`, `uri_client_launcher.py`, `uri_client.ps1`, `*_manifest.schema.json`, `provision_uri_server.py`, `provision_uri_client.py`, `uri_authorized_start.ps1` | FROZEN (Phase 1); validate/start/status only |
| Stop/uninstall tool (R-4) | none | NOT IMPLEMENTED |
| Runtime build/rollback runbook | `docs/governance/consolidation/URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md` | GREEN steps executed (materialization+gates); RED cutover steps not run |
| Runtime materialization | detached `e8e3b652` + overlay (`RUNTIME_OVERLAY_PHASE2OQ_G.txt`, `scripts/oi_materialize_test_runtime.py`, `ws_provision.py`) | still the only runnable form on 2026-10-18 (dozens of e8e3b652 runtime worktrees) - CONS-7 OPEN |
| Rollback | `scripts/phase1_offline_rollback.py` (frozen, amended under FCV-01 `0d3e1224`), `scripts/fcv_guarded_rollback.py` (FCV-11) | implemented; Phase 2 rollback overlay P2-5 DESIGN ONLY |
| Clean venv from `requirements.txt` (R-3) | - | NOT QUALIFIED (cutover plan 10-10 still copies `uri-ws-final\.venv`) |
| Production cutover | `docs/integration/final_20261010/CUTOVER_PLAN.md` | PLAN ONLY, not authorised |
| Pinned UI release build | `C6_UI_INTEGRATION_CONTRACT.md` | PLANNED |
| Client profiles | Phase 1 C2/C3 `uri_core/client_runtime/*`; Phase 2 client-profile CODEX_HOME pin, `phase2close_acceptance.py login-guide` | IMPLEMENTED/TESTED; logins (PA-8/9) not done |
| Multi-client / multi-user | tests `test_multi_client_runtime.py`, `test_multi_user_isolation.py`; research `e49d5854` (NOT ancestor) | runtime separation in Core; multi-user app-host = research only |
| UI app identity | `uri_ui/windows/runner/Runner.rc` still "com.example"; shared prefs file shared by all builds (CONS-5) | DESIGN ONLY fix |
| Generated art | owner policy: provenance/licensing is a distribution-release gate (Ember OD-2) | gate open |

Verdict: no installable/distributable package exists; distribution = git clone + materialization by a developer.

## (e) Privacy / personal-data status

| Mechanism | Path | Status |
|---|---|---|
| Provider keys encrypted at rest, no read-back, prompt-module import ban | `uri_core/core/provider_keys.py`; `test_provider_keys_boundary.py`, `test_provider_keys_hygiene.py` | IMPLEMENTED/TESTED (M22.5) |
| Per-user memory / file-store isolation | `uri_core/core/user_memory.py`, `test_multi_user_isolation.py`, `test_m21_file_store_isolation.py` | IMPLEMENTED (M18/M21) |
| Memory recall honesty | FCV-07 fix `ee484938` (port of `ec1157fd`), `925dcfd1`, `df49e596` (ANC) | INTEGRATED via FCV-R |
| Memory D4 "history yes, learning no" | memory note `uri-memory-d4-history-not-learning` (2026-09-28) | owner rule for M36 (donor, not in canonical) - DOC-ONLY |
| Assist redaction (secrets, cards, IDs incl. Aadhaar/PAN; counts only) | `uri_assist/redact.py`; `docs/assist/03_PERMISSION_AND_DATA_FLOW.md` ("captured content never leaves the PC", loopback-only model) | IMPLEMENTED/TESTED |
| Office correction history with consent (no cell values, view/delete) | `uri_office/history.py`, `uri_office/sanitize.py` | IMPLEMENTED |
| Cloud Brain policy | `uri_operational_intelligence/brain_catalog.py`, `worker_bridge.py`; WS limitation CLOUD: activation disabled, no credentials | IMPLEMENTED, disabled by design |
| Client-local harness credentials (server never holds them); logins never copied | Phase 1 C4; ISO-1 | FROZEN / ACCEPTED |
| Secrets/state outside Git, ACL-hardened (`%LOCALAPPDATA%\URI`) | salvage ledger s4-5 | DOC-ONLY |
| Personal-information sovereignty / anonymization policy | searched `*.md` on all refs for "sovereign"; canonical for anonymi[sz]/pseudonym | **NOT FOUND** - no dedicated policy or design |

## (f) Outstanding physical / owner acceptance (consolidation list) - later status

| Item | Later evidence | Status 2026-10-21 |
|---|---|---|
| PA-1..PA-7, PA-13 human acceptance on real app | TODO row "PLANNED (runbook)"; WS/receipts list PA-1..PA-13 as out of scope | OPEN |
| PA-8/PA-9 Codex/Claude client-profile login | DL2 PC run "blocked on CLI login" (`86221a2b`); Claude CLI login still needed (memory) | OPEN |
| PA-10 native execution in worker | depends on PA-8 + EXE-1b | OPEN |
| PA-11 power-loss campaign | harness SIMULATED only; "durability NOT QUALIFIED" | OPEN |
| PA-12 cutover authorization | CUTOVER_PLAN.md PLAN ONLY | OPEN |
| P-2/P-3 `\URIServer` + `URI.lnk` containment | LEGACY-1/LEGACY-2 OPEN (UI V2 postint); live: `\URIServer State=Ready` (enabled), no listener on 8000 (VERIFIED-LIVE) | OPEN (task enabled, not running) |
| EXE-1b sandbox backend | fail-closed implemented; owner choice pending | OPEN |
| C6 decision 3 (Brain rows), voice rules 3-4 | TODO PENDING | OPEN |
| 11 Phase 1 full-suite failures | still the pinned accepted 11 (FCV-R gates) | OPEN (accepted as baseline, no decision record found) |
| P-4 install dir/state root/port; P-6 `main` rename | canonical branch still `integration/git-sync-20261008` | OPEN |
| CONS-7 `HEAD==e8e3b65` coupling | runtimes still materialized on e8e3b652 | OPEN |
| OI start (Runtime v1 <-> Core) | OI/WS/profiles/QC integrated (`9306dc11`..`ec2fab54`) | **CLOSED in substance** (integrated, dev-only, not production) |
| Phase 2 freeze; C7 cutover | no tag/record | OPEN |
| P2-5 Phase 2 rollback overlay | DESIGN ONLY | OPEN |
| R-3 clean venv; R-4 stop/uninstall; CONS-5 per-install prefs; CONS-14 local checkpoints | no later closure found | OPEN |
| CONS-9/P2-6 desktop-line parity port | none beyond C5 RAR | OPEN |
| Voice parity | live voice integrated `6b488305` (push-to-talk, local STT); no human-talker run | PARTIAL |
| Chat `/ask` C7 gate 5 | not re-checked here | UNKNOWN |

## (g) Worktree hygiene (225 listed paths, all exist; counts from `git status --porcelain | wc -l`)

| Group | Worktrees | Uncommitted count | Preserved? |
|---|---|---|---|
| Runtime/gate materializations (HEAD `e8e3b652` + overlay): brain_qc/runtime1-4, uri-*-gate*, *-rt*, staging1-3, ui-v2c-run/*, ui-v2p-run/* (9), fcv-recovery runtime/gate*, windows-assistant-recovery runtime-* (10), core-live-verification runtime-A/B/C, profiles-live runtime(-b..f), qc-closure-live runtime5/6, uri-integ-rt(-e), uri-ember-rt(2), uri-ui-typo-live, uri-auth-live/o2i-live/o2r-live/o2-live runtimes, ui-v2-freeze rt-*, uri-ws-final/ws-rt/ws-hard, uri-vram-r1-p1 (~95 worktrees) | 90-193 each | By design. Sample of 5 (runtime6, uri-ws-final, fcv runtime, war runtime-first, vram-r1-p1): 1928/1931 file blobs already in the object DB; residue 1 file each (local markers). Recoverable. |
| `.codex/worktrees/uri-phase2a/uri-agent` | 156 | 270/273 byte-identical to `6dea2665` (3 = post-acceptance docs, matches runbook) - PRESERVED |
| `.codex/worktrees/uri-phase1-integration/uri-agent` | 90 | 120 frozen files == `925ad45c`; 543/543 `model_lab` files == `ec2fab54` - PRESERVED (local `work/c1/checkpoints` zip = CONS-14, not checked) |
| `Development/Uri/_V1` | 249 | tracked == `preserve/v1-...` `6aa9c30b`; extra untracked preserved elsewhere except graphify artifacts - PRESERVED |
| `.codex/.../harness-connections-console/_V1` 42, `intent-discovery/_V1` 38, `m33-audit-candidate/_V1` 20, `uri-m37-m39-integration` 47, `uri-batch-candidate` 2 | as shown | == their preserve/* branch - PRESERVED |
| `Development/uri-agent` (legacy master) | 66 | == `869fae5d` (local only) + 26 later files, all blobs in DB - PRESERVED locally only |
| **`Development/uri-adaptive-runtime`** | 134 | **134 of 135 files NOT in object DB** (`research/adaptive_runtime/evidence/` 121, `r2/` 11, `model_lab/evidence/runs/` 2) - **NOT PRESERVED** |
| `D:/uri-dev/uri-runtime-vram-r1` | 3 | 2 files not in DB (research evidence + graphify) - NOT PRESERVED (minor) |
| `D:/uri-dev/uri-ui-controls-typo` | 2 | 1 doc not in DB (`docs/ui/controls_typography_20261018/`) - NOT PRESERVED (active work) |
| Office-family candidates (`uri-office`, `-m2`, `-xb1`, `-u2-a`, `-final-qualification/candidate`, `o2r-live/candidate`, `auth-live/candidate`, `o2i-live/candidate`, lifecycle `URI-OFFICE-O2-INTEG-r2/.../qualify`, `windows-assistant-recovery/candidate`) | 1-3 each | `uri_ui/assets/office/` built bundle (3 files) not in DB - build output by design (memory: "built page never committed"); `windows-assistant-recovery/candidate` also 1 `uri_ui/integration_test/` file NOT PRESERVED |
| `uri-innovation-lab` 1, `uri-ti-integ` 1, `fcv .../rollback-proposal` 2 | 1-2 | 1 file each not in DB (lab memory evidence; TI integration doc; rollback proposal file) - NOT PRESERVED (minor) |
| `.tmp_m33_1_batch4_baseline_5973f6d` | 2 (18 untracked under `.tmp_m33_c2_pytest`) | pytest residue; ledger: QUARANTINE / PROPOSE DELETION |
| `uri-vram-research` 6, `uri-scheduler` 1, companions 1 each, `m33-audit-baseline` 3, `uri-ui-v2c` 1, qwen38-dv/* 1 each, `uri-p0-audit` 1 (this audit) | small | blobs present in DB (or this audit's own output) |
| All others (~95) | 0 | clean |

"In object DB" means the exact blob exists in the shared repository (possibly only via a non-branch object); it is
best-effort evidence of recoverability, not proof the file is on a named branch. No file contents were read.

## (h) Evidence gaps

1. H-M6..M30, M32, M33/M33.1, M35, M39 statuses are DOC-ONLY; their SHAs were not each verified (affects only
   historical rows, not the canonical verdict).
2. Desktop-line feature parity (Google onboarding, Gmail/Drive/Docs, PPT, uploads) not compared file-by-file
   between `eb736933` and `ec2fab54`; recorded as PENDING/UNKNOWN.
3. No canonical milestone ledger after Phase 1 - post-consolidation statuses come from receipts and memory notes.
4. FCV (2026-10-14) report lives outside the repo; status DOC-ONLY.
5. `work/c1/checkpoints` Phase 1 archive (CONS-14) and `D:\URI-preservation` vault restore not checked.
6. "Blob in object DB" check cannot distinguish branch-reachable from dangling objects; a `git gc` could drop
   dangling ones - adaptive-runtime evidence is the material unpreserved set regardless.
7. Live state checked only for `\URIServer` task state and port 8000; shortcuts not inspected.
8. `donor/*` tags verified only in the `uri-canonical-candidate` clone; GitHub not queried (no network use).

## Self-review

- Criteria 1-7: each section maps to one criterion; ledger claims checked: `uri_v1/*` absent (5 subpaths),
  `uri_core/core/arn` present since root, RAR provenance hashes equal, `uri_dictation`/`uri_desktop_seams` absent,
  `uri_office` new lineage, `Launch URI Harness/Voice.bat` absent, edge paths are M33.2 root code (not M37).
- Repaired during review: (1) first hygiene pass showed hundreds of "differences" vs preserve branches; root cause
  was untracked files reported as `D` - re-measured as tracked-match + untracked-not-in-preserve. (2) `e4dea8c4`
  typo corrected to branch tip `e4dea8c1`. (3) qwen38 docs in `_V1` initially looked unpreserved; found on
  `research/qwen38-27b-brain-20261016` (`c679e638`, `9689a666`). (4) Did not count `uri_core/core/edge` as
  M37 salvage (same lineage as root).
- No positive claim rests on a PENDING/FAILED/BLOCKED result; "integrated" = ancestor of `ec2fab54`, nothing more.
