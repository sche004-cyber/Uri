# URI Development Register (`developmental.md`)

Interim authoritative development progress register. It stays in force until Lifecycle V3.1 and the persistent
Milestone Manager (roadmap P1) can import and manage these records. Created by P0 (Comprehensive Audit & Controlled
Integration) on 2026-10-21. No earlier `developmental.md` existed in any of the 179 refs, so nothing was overwritten.

Rules for editing this file:
- Append and correct; never delete. When later evidence disproves an entry, add a dated correction and keep the old text.
- A claim taken only from a document, a receipt outside git, an assistant memory note or another agent's summary is
  labelled `HISTORICAL/REPORTED` until it is checked against git, a committed record or a re-run.
- Keep this file short. Detail lives in the linked evidence files under `docs/audit/p0_20261021/`.

Status legend (used consistently):

| Status | Meaning |
|---|---|
| GREEN | Integrated in canonical and verified (git ancestry + recorded tests; live where the capability needs it) |
| BLUE | In progress, or built but needs repair / review / re-run before it can be integrated |
| YELLOW | Waiting for a genuine owner decision |
| RED | Blocked or failed |
| WHITE | Paused, deferred, research-only or superseded |
| UNKNOWN | Insufficient evidence |

Stage columns never stand in for each other: **Impl** (code exists) / **Tested** (test result recorded) /
**Accepted** (independent review verdict recorded) / **Integrated** (ancestor of canonical) / **Live** (real Windows
app or GPU run that completed with a result, on the stated commit).

---

## A. Project overview and current verified baseline

URI is a local-first desktop assistant: Flutter Windows UI (UI V2, Living Companion shell) talking over stdio/SSE to an
integrated Python worker, which runs one resident local Brain (Qwen3.6-35B-A3B UD-IQ3_S on stock llama.cpp b11425,
Vulkan, AMD Radeon RX 7900 GRE 16 GB) under a machine-wide GPU lease, plus Office, Web, Assist, Voice, Scheduler,
Text Intelligence and Operational Intelligence services.

| Fact | Value | Evidence |
|---|---|---|
| Canonical branch | `uri-repo/integration/git-sync-20261008` (remote `https://github.com/sche004-cyber/Uri.git`) | `git fetch uri-repo` 2026-10-21; `docs/governance/consolidation/URI_SOURCE_OF_TRUTH_MANIFEST.md` |
| Canonical HEAD | `ec2fab5493578a4f5a805642153d56b4d5ea59fa` (2026-10-18, Brain QC closure) | `git rev-parse` 2026-10-21 |
| Stale refs to ignore | local branch `integration/git-sync-20261008` = `348677b7`; `origin/master` / `uri-agent` master = `e8e3b652` (root, 804 commits behind) | evidence `00_branch_divergence_vs_ec2fab54.txt` |
| Frozen Core | Phase 1, 121 files, tag `accepted/phase1-core-freeze-31a34dcb` | `scripts/ws_frozen_check.py` run at ec2fab54: ok, no unapproved drift; only owner-approved blobs differ (`server.py` D12, `fetch_url.py` D2/D33) |
| Frozen Runtime | Runtime v1, tag `accepted/runtime-v1-freeze-20261007` -> `f791d65c` (ancestor of canonical) | freeze-to-canonical diff under `model_lab/` = 6 added repro files, 0 frozen files modified |
| Frozen UI | UI V2, tag `accepted/ui-v2-freeze-20261017` -> `7893aaed` | receipt `receipts/ui-v2-20261016@595c1a04`; canonical has owner-authorised Brain QC/Office deltas past the freeze, no re-freeze receipt |
| Git footprint | 179 refs, 15 tags, 224 worktrees (about 95 runtime materialisations) | `00_worktree_list.txt`; hygiene in `60_*.md` §g |
| Independent reviewers (2026-10-21) | Codex CLI authenticated but rate-limited until 2026-10-22 14:03 (HISTORICAL/REPORTED in receipts); local Claude CLI logged out (`claude auth status` = loggedIn false) | live probe 2026-10-21 |
| Live hazard | Windows scheduled task `\URIServer` is `Ready`; at logon it starts the legacy pre-SSRF server from `C:\Users\cheta\Development\uri-agent` on port 8000 (not listening at probe time) | `Get-ScheduledTask` 2026-10-21 |

Tests re-run by P0 at canonical `ec2fab54` (CPU only, COMPLETED_WITH_RESULT):

| Suite | Result |
|---|---|
| `scripts/ws_frozen_check.py` | ok (121 files, unapproved drift empty) |
| `test_runtime_profiles`, `test_runtime_profile_selection`, `test_brain_quick_controls`, `test_brain_qc_integration` | 95 passed, 1 skipped |
| Office grants / folder access / approvals | 87 passed |
| `tests/ssrf` + `tests/web` | 3792 passed (`tests/ssrf` alone 65) |
| `tests/assist` | 2212 passed, 25 failed (host lacks Playwright; tests fail instead of skipping = D15) |
| Graphify: `test_graphify_index.py` 15, `tests/graphify` 15, `test_graph_*` 62, hint activation 7 | all passed (`test_graph_isolation.py` needs `URI_EXTERNAL_CREDENTIAL_SECRET` set) |
| skill router/evaluator/registry 87; Gemma/Qwen MCP bridges 29 (+1 skip) | passed |

Not re-run by P0: Flutter suites, scheduler/OI/WS/phase chains (start processes), any live GPU or Windows UI journey.
No live run exists on canonical `ec2fab54` itself for Office or the core FCV journeys; the most recent live runs were
on `fcc1f183` (Brain QC code, 2026-10-18) and on test composites (Office `0283aab2`, 2026-10-17).

---

## B. Capability inventory

Detail per row (objective, tests, reviewers, limitations) is in the evidence file named in the last column.

| ID | Capability | Location | Key commit | Impl | Tested | Accepted | Integrated | Live | Status | Main limitation / remaining work | Ev. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CAP-RT1 | Resident Runtime v1 (Qwen3.6-35B-A3B, b11425 Vulkan, 32K, q8_0 KV, GPU vision, MTP n=2) | `model_lab/integration/local_brain.json`, `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` | `f791d65c` | yes | yes (freeze suites, HISTORICAL/REPORTED) | owner ruling (self-qualified, no Codex) | yes | yes (2026-10-07; qcc-1 2026-10-18) | GREEN | `URI_RUNTIME_AUTHORITY_MANIFEST.json` stale ("NOT WIRED") | 10 |
| CAP-RT2 | Runtime profiles P2 (64K, no vision, no MTP) and P3 (32K, GPU vision, no MTP) | `uri_operational_intelligence/runtime_profiles.py`, `runtime_profile_selection.py`, `scripts/ws_brain_host.py` | `cd4a7963` | yes | yes | subagent AwF RPI-R1..R9 | yes | yes (`f3d5eb29`, 68/68 + 12/12) | GREEN | reviews subagent-class, records outside git | 10 |
| CAP-RT3 | P1 (64K + GPU vision) | catalog only; refused by selection, host and QC | `4c61a0b3` (refusal) | measured | refusal tested | — | refusal only | crashed (CRASH-1), demoted (DEMOTE-P1) | YELLOW | retire or investigate (owner) | 10 |
| CAP-RT4 | Brain Quick Controls + QC closure (thinking per turn, Vision/Context/Draft switches, mismatch line, Assist vision lock) | `uri_operational_intelligence/brain_quick_controls.py`, `uri_ui/lib/living/integration/brain_quick_controls.dart` | `feaabe3f`, `ec2fab54` | yes | yes (793p/23s at `fcc1f183`; 95p/1s at ec2fab54) | QCC-R3 ACCEPT (subagent) | yes | yes (qcc-1 32/32 on `fcc1f183`) | GREEN | none blocking | 10 |
| CAP-RT5 | Automatic vision fallback "F-1" (Standard vision if it fits, else 32K-no-MTP, else clear refusal; keep conversation) | not implemented | — | no | — | — | no | ui-2 showed refusal case | YELLOW | product decision, then build | 10 |
| CAP-RT6 | Restore after failed switch (QC-F5) | `ws_brain_host.py`, `worker_bridge.py` on UI-controls branch | `e9ee7409` | yes | yes (805p/23s at `22b53b78`) | R1 AwF, R1-01 open | no | ui-2 (`22b53b78`) | BLUE | ships with CAP-UI3 | 10, 20 |
| CAP-RT7 | GPU lease, fit check, residency/perf monitor | `uri_operational_intelligence/gpu_lease.py`, `perf_monitor.py`, `brain_health.py` | WS hardening line | yes | yes (recorded gates) | Codex WS rounds (HISTORICAL/REPORTED) | yes | yes (lease histories) | GREEN | monitor reports only, never restarts | 10 |
| CAP-RT8 | VRAM-R1 research record (accepted code already integrated as CAP-RT2) | `research/runtime_vram_r1/` | `7c7a7776` | yes | "710 passed / 22 skipped" HISTORICAL/REPORTED, no log | r3 ACCEPT HISTORICAL/REPORTED, no review file | code yes; record no | research runs | WHITE | optional docs-only merge of the record | 10 |
| CAP-RT9 | Qwen3.8-27B Development Brain experiment | `research/qwen38/` | `9689a666` | lab | lab | Codex r1-r3 REVISE; r4 blocked by quota | no | lab | WHITE | r4 re-check after 2026-10-22; adoption = owner | 10 |
| CAP-RT10 | Adaptive Runtime R2, VRAM efficiency, UI VRAM cache | research branches | `7d035aa1`, `09c4b8ff`, `31dbd92a` | research | recorded | none | no | research | WHITE | AR2 report verdict sections unfilled; target unreachable; no effect | 10 |
| CAP-UI1 | UI V2 app shell (Concept C, Solar, conduits, detached chat, themes) | `uri_ui/` | `7893aaed` (freeze) | yes | yes (758 Flutter at freeze; 788 at `fcc1f183`) | yes | yes | yes (68/68, 12/12, 3/3 at freeze) | GREEN | post-freeze deltas: returning/perf journeys not re-run | 20 |
| CAP-UI2 | Ember V2.1 fire companion | `uri_ui/lib/living/...` on candidate | `68061d85` (code = `bb61e976`) | yes | yes (Flutter 855/5 at `bb61e976`) | R1-R4, stage-2, FINAL AwF (subagent) | no | main journey 68/68; Ember live runs | YELLOW | owner authorisation; fidelity AC-F1/AC-F3 not met (owner-carried); UI V2 returning/perf not re-run | 20 |
| CAP-UI3 | UI Controls & Typography (QcToggle, Segoe UI/Consolas scale, static glow) | 43 Dart files + Python restore path | `e9ee7409` | yes | yes (Flutter 799 at `22b53b78`) | R1 AwF (uncommitted record), **R1-01 MEDIUM open** | no | ui-2 26/26 (claimed 30/30), uiv2-1 68/68 | BLUE | repair R1-01 (keyboard/screen reader), R1-02; re-review; contrast check | 20 |
| CAP-UI4 | Living companions, companion voice/settings, A2UI, orb/Solar shaders | `uri_ui/lib/living/`, `uri_a2ui/` | `f24d57ab`, `dc1ce81`, merge `ab8f8227` | yes | yes | yes (recorded) | yes | yes | GREEN | — | 20 |
| CAP-UI5 | Innovation Lab | `phase/innovation-lab` | `47b63f62` | yes | yes | Codex AwF (HISTORICAL/REPORTED) | no | lab ports | WHITE | no integration decision | 20, 60 |
| CAP-OF1 | Office Excel (open, cell edit, formulas, hash-bound save, row insert/delete, formatting subset) | `uri_office/xlsx_*.py`, `uri_ui/office_web/` | `3e769fdf` | yes | yes (811p/1f env at `3e769fdf`) | S4 AwF (subagent), Codex drivers r6/r9/r10 ACCEPT | yes | open/edit/save/row insert yes (`0283aab2`, 64K, simulated input) | GREEN | row delete/format/recalc unit-only; no column ops/sort/charts | 30 |
| CAP-OF2 | Word authoring (owner direct edit) | `uri_office/authoring/docx_ops.py`, `word_editor.dart` | `84328f8b` | yes | yes | completion chain | yes | yes (C01-C03) | GREEN | Brain-driven authoring = `planned:O3` | 30 |
| CAP-OF3 | PowerPoint authoring (owner direct edit) | `uri_office/authoring/pptx_ops.py`, `presentation_editor.dart` | `16e040e7` | yes | yes | completion chain | yes | yes (A01-A05) | GREEN | Brain-driven authoring = planned | 30 |
| CAP-OF4 | PDF view/search/zoom, Office->PDF via LibreOffice 26.8.1 headless | `uri_office/render.py`, `workers/` | `eaeb10c1` | yes | yes | O2 Codex r4 ACCEPT | yes | yes (J08-J14) | GREEN | text extraction feature missing; PDF Q&A planned; printing off | 30 |
| CAP-OF5 | Folder access grants + hash-bound one-shot approvals | `uri_office/grants.py`, `approvals.py` | `4b600e6b` | yes | yes (P0 re-run 87 passed) | completion chain | yes | F01 partial | GREEN | save-in-folder and remove-then-refuse not shown live | 30 |
| CAP-OF6 | Office LOW findings S4-01..S4-03 | `a2ui_hub.dart`, `office_controller.dart`, `ops.py` | — | no | — | — | — | — | BLUE | repair + review | 30 |
| CAP-OF7 | Brain-driven Office authoring/Q&A (O3-O5) | `uri_office/capabilities.py` statuses `planned:O3/O4/O5` | — | no | — | — | — | — | WHITE | future milestone | 30 |
| CAP-WEB1 | Web Intelligence W1 (search, safe fetch, synthesis) | `uri_web/` | `03f0bf2c` | yes | yes (3792 at ec2fab54) | Claude reviewer AwF on `422159e9` | yes | **no** (no Windows worker/UI run, no live keyed search) | BLUE | live qualification; 1 MEDIUM + 1 LOW open | 40 |
| CAP-WEB2 | Web & Document Intelligence W2 | plan only on `uri-repo/ccr-cab5ed06-9hwyc4` | — | no | — | — | — | — | WHITE | thread stopped by owner 2026-10-12 | 40 |
| CAP-SEC1 | SSRF-1, IDN-1/1b, GRAPHIFY-LEAK-1 | `uri_web/netpolicy.py`, `uri_core/tools/fetch_url.py`, `graphify_index.py` | `e07b71c6`, `368188b7`/`1b5423bc`, `e761ce8f` | yes | yes | yes | yes | partial | GREEN | review receipts only on `ccr-cab5ed06` branch | 40 |
| CAP-AS1 | URI Assist (consent model, redaction, A2UI cards) | `uri_assist/` | A0 line in canonical | yes | yes (2212 passed) | yes | yes | perception not possible | BLUE | **all perception adapters are refusing placeholders** (D14); no browser automation by design | 40 |
| CAP-VO1 | Live voice: faster-whisper base.en on CPU, push-to-talk | `uri_voice` service, UI composer | `3b88c67` / `6b488305` | yes | yes | Codex R4 | yes | startup only; no human-talker run | GREEN (with gap) | human acoustic qualification pending | 40 |
| CAP-VO2 | Wake word ("oii URI") | old `_V1` preserve branch only | `6aa9c30b` | partial | — | — | no | — | WHITE | not in canonical | 40 |
| CAP-TI1 | Text/Writing Intelligence (draft desk, voice drafting) | TI line | `54ad7be7` | yes | yes | Codex r16 AwF | yes | demo passed; speech drafting not operational | GREEN (with gap) | P3 Writing Intelligence builds on this | 40 |
| CAP-SC1 | Scheduler & calendar | `uri_scheduler/` | `b02ed4f5` | yes | yes (403 recorded) | Codex r11 AwF | yes | not activated; real-Claude runs blocked | BLUE | **D01** token file ACL; ACL-2 branch rejected (R4) | 40 |
| CAP-OI1 | Operational Intelligence, supervisor, worker bridge, Working System | `uri_operational_intelligence/`, `uri_supervisor*`, `scripts/run_uri_integrated_server.py` | WS hardening `71606148` + later | yes | yes | Codex r8/r10 AwF | yes | yes (journeys) | GREEN (with defect) | **D10** new random key-store secret every start | 40 |
| CAP-FCV | Frozen-core live verification + recovery (FCV-R) | `docs/governance/fcv_recovery/` | `85f6a0ec` | yes | yes | yes | yes | 29/29, 12/12, 5/5 at `85f6a0ec` and `eaeb10c1` | GREEN (with decision) | D08 rollback tree cannot import `uri_web` (owner) | 40 |
| CAP-PH2 | Phase 2 (durable supervisor, bridge, composition, ops, OQ) | Phase 2 tags | `fcd0d72e`, `0b49d86d` | yes | yes | Codex accepted | yes | technical | YELLOW | physical PA-1..PA-13, EXE-1b, Phase 2 freeze, C7 cutover (owner) | 40, 60 |
| CAP-GR1 | Graphify native runtime (`graphify_index.py`, hint activation, leak fix) | `uri_core/core/graphify_index.py`, `decision_engine.py`, `paired_reasoning.py` | M30, `78fb5e1`, `e761ce8f` | yes | yes (P0 re-run) | M34 Claude audit; LEAK-1 claude_cli AwF | yes | M34 legacy server (HISTORICAL/REPORTED) | GREEN (with finding) | **GRF-P0-1** working-system path ignores killswitch/filter, unreviewed | 50 |
| CAP-GR2 | Graphify development skill (`.agents/skills/graphify`, CLI 0.9.58) | dev tooling only | — | yes | — | — | in tree | — | GREEN (tooling) | canonical has no `graph.json`; CLAUDE.md graphify rules inert until built | 50 |
| CAP-LC1 | Development lifecycle V2/V3/V3A/V3B + auditor fallback | `.claude/skills/uri-development-lifecycle/`, `scripts/dev_workflow/` | `73bdbef1`, `7d3d0f63`, `777f8d81`, `57f2d567`, `348677b7` | yes | yes | DL2-DL3B driver-verified; fallback by subagents | yes | DL2 PC run blocked on CLI login | GREEN | open LOW AF-S1-02/03/04/06, AF-S3-01/02 | 50 |
| CAP-LC2 | Reviewer tiers 3-5 / owner-attested review | `scripts/dev_workflow/` on branch | `67d45317` | yes | **no result** (log truncated) | **none on this commit** (r10, r11 REJECT; r12 never collected) | no | — | BLUE | review + full test run | 50 |
| CAP-LC3 | Lifecycle V3.1, persistent task ledger, Milestone Manager | label only (`DEV_LIFECYCLE_3B_PLAN_AND_ACCEPTANCE.md:49`) | — | no | — | — | — | — | WHITE | roadmap P1 | 50 |
| CAP-SK1 | Skills & harnesses (`.agents/skills`, skill router/evaluator, harness adapters, MCP bridges) | `skill_router_v1.py`, `uri_harness_adapters/`, `scripts/*_mcp.py` | canonical | yes | yes (P0 re-run) | historical | yes | — | GREEN (tooling) | router/evaluator no longer wired into runtime; two divergent lifecycle SKILL.md copies | 50 |
| CAP-MC | Mission Control, Skill Command Center, Developer Studio | docs only, no code in any ref | — | no | — | — | — | — | WHITE | roadmap P6-P8 | 50 |
| CAP-PK1 | Installation, packaging, distribution | launchers `Launch URI Working System.bat` (dev), legacy `Launch URI.bat` (quarantined) | — | no installer | — | — | — | — | WHITE | no installer; runnable form = `e8e3b652` + overlay (CONS-7); clean venv unqualified (R-3); no stop/uninstall (R-4); app id `com.example` | 60 |
| CAP-PD1 | Privacy / personal data (encrypted provider keys, per-user isolation, Assist redaction, consent-gated correction history, cloud Brain disabled) | `provider_keys.py`, `uri_assist/`, Office | canonical | yes | yes | yes | yes | partial | GREEN (partial) | no personal-information sovereignty / anonymisation design anywhere (roadmap P2) | 60 |
| CAP-V1 | Old `_V1` parallel line (uri_v1: M36 memory, M37 Edge, M38 harness, M39 office, dynamic planning slice 1, dictation, desktop recovery) | 45-161 commits ahead of `e8e3b652`, not in canonical | tags `accepted/m36-m38-closed-frozen-bd7c450`, `accepted/dynamic-planning-slice1-565eae8` | yes | yes (historical) | yes (historical) | **no** (only RAR reference-binding salvaged, with provenance) | — | WHITE | no retirement or salvage decision for M36/M37/dynamic planning; M39 office superseded in practice by `uri_office/` | 60 |

---

## C. Milestone roadmap and dependencies

Owner-approved roadmap (owner prompt 2026-10-21, DEC-088 in `decisions.md`):

| ID | Milestone | Depends on | State 2026-10-21 |
|---|---|---|---|
| P0 | Comprehensive Audit & Controlled Integration | — | BLUE (this audit; integration steps wait for owner) |
| P1 | Milestone Manager + Lifecycle V3.1 | P0 records; reviewer tiers (CAP-LC2) | WHITE (not started; no code in any ref) |
| P2 | Personal Data Sovereignty | P1 (task history), CAP-PD1, CAP-OI1 D10 fix | WHITE (no design exists) |
| P3 | Writing Intelligence | CAP-TI1, CAP-VO1, P2 for remote processing | WHITE |
| P4 | Meeting Intelligence | CAP-VO1 human qualification, P2 | WHITE |
| P5 | URI Office Client Installer | CAP-PK1 gaps (CONS-7, R-3, R-4), OD-2 distribution gate | WHITE (no installer exists) |
| P6 | Mission Control | P1 | WHITE |
| P7 | Skill Command Center | CAP-SK1, P1 | WHITE |
| P8 | URI Developer Studio | P1, CAP-LC1/LC2 | WHITE |
| P9 | Advanced Vision Assist | CAP-AS1 perception adapters (D14), CAP-RT5 F-1 | WHITE |
| P10 | Brain Runtime Optimization | CAP-RT3 P1 decision, CAP-RT9, CAP-RT10 findings | WHITE |
| P11 | Multi-Client Deployment | P5, research `e49d5854` (multi-user host) | WHITE |

---

## D. Planned vs implemented vs tested vs accepted vs integrated

Counts over section B (43 rows):

| Stage | Count | Rows |
|---|---|---|
| Planned only, no code | 7 | RT5, OF6 (repairs), OF7, WEB2, LC3, MC, PK1 (installer) |
| Implemented, not integrated | 10 | RT6, RT8 (record), RT9, RT10, UI2, UI3, UI5, LC2, VO2, V1 |
| Integrated, but a live, review or defect gap remains | 11 | UI1, WEB1, AS1, VO1, TI1, SC1, OI1, FCV, PH2, GR1, PD1 |
| Integrated, tested, accepted and live-verified (or tooling with no live need) | 15 | RT1, RT2, RT3 (refusal only), RT4, RT7, UI4, OF1-OF5, SEC1, LC1, GR2, SK1 |

| Status | Count |
|---|---|
| GREEN | 21 (RT1, RT2, RT4, RT7, UI1, UI4, OF1-OF5, SEC1, VO1, TI1, OI1, FCV, GR1, GR2, LC1, SK1, PD1; several "with gap/defect") |
| BLUE | 7 (RT6, UI3, OF6, WEB1, AS1, SC1, LC2) |
| YELLOW | 4 (RT3, RT5, UI2, PH2) |
| RED | 0 capabilities (blockers are listed in section I) |
| WHITE | 11 (RT8, RT9, RT10, UI5, OF7, WEB2, VO2, LC3, MC, PK1, V1) |
| UNKNOWN | 0 rows; unknown details are named in section N |

---

## E. Independent audit history

| Audit | Date | Auditor | Scope | Outcome | Record |
|---|---|---|---|---|---|
| Consolidation final audit | 2026-10-08 | Codex r5 | git/branch consolidation | accepted | `docs/governance/consolidation/URI_CONSOLIDATION_FINAL_AUDIT_20261008.md` |
| Per-milestone lifecycle reviews | 2026-10-11..18 | Codex drivers, claude_cli, fresh subagents | each milestone | see section B "Accepted" | per-milestone `review/` folders; many outside git under `D:\uri-dev\lifecycle\` |
| Antigravity Part 1 `URI-DEV-AUDIT-20261020` | 2026-10-20 | Antigravity | whole project | many claims refuted by P0 (section M) | `C:\Users\cheta\.gemini\antigravity\brain\2f49f16d-...\URI_DEV_AUDIT_20261020.md` (outside repo) |
| Antigravity Part 2 `URI-DEV-AUDIT-20261020-RECOVERY` | 2026-10-20 | Antigravity | history recovery | partly refuted (section M) | same folder, `URI_HISTORICAL_RECOVERY_AUDIT_20261020.md` |
| Antigravity master register + Milestone Manager V1 prototype | 2026-10-20 | Antigravity | register | file-existence checks only; cites non-existent commits | same folder; `scratch\uri-milestone-manager-v1\` |
| Antigravity Graphify follow-up | 2026-10-20 | Antigravity | Graphify | transcript only, no report | Antigravity transcript chunk 00000005 |
| **P0 comprehensive audit** | 2026-10-21 | Claude Code (this session) + 7 read-only evidence subagents | whole project | this file, `decisions.md`, `docs/audit/p0_20261021/` | `docs/audit/p0_20261021/P0_AUDIT_REPORT.md` |

P0 reviewer class: Claude session plus fresh read-only subagents (lifecycle tier 3 by the 2026-10-17 owner policy).
It is not a Codex or claude_cli driver-verified review. Codex was not used to save quota before its reset.

---

## F. Branches, worktrees and commits that matter

| Ref | Commit | Relation to canonical | Disposition |
|---|---|---|---|
| `uri-repo/integration/git-sync-20261008` | `ec2fab54` | canonical | — |
| `integration-candidate/ember-on-canonical-20261018` (worktree `D:\uri-dev\uri-integ-ember`) | `68061d85` | 63 ahead, 0 behind | candidate Q-1 (YELLOW) |
| `milestone/ui-controls-typography-20261018` (`D:\uri-dev\uri-ui-controls-typo`) | `e9ee7409` | 5 ahead, 0 behind | candidate Q-2 (BLUE, repairs first) |
| `milestone/lifecycle-owner-attested-review-20261017` (`D:\uri-dev\uri-owner-attested`) | `67d45317` | 16 ahead, 66 behind | candidate Q-3 (BLUE, review first) |
| `research/runtime-vram-r1-20261017` | `7c7a7776` | 4 ahead (records only) | Q-4 optional record merge (WHITE) |
| `milestone/sched-token-acl-2` | `eaf3bf69` | 4 ahead | RED (R4 REJECT) |
| `research/qwen38-27b-brain-20261016` | `9689a666` | 6 ahead | WHITE (research) |
| `research/adaptive-runtime`, `research/vram-efficiency-20261010`, `research/ui-vram-cache-20261010` | `7d035aa1`, `09c4b8ff`, `31dbd92a` | research | WHITE (archive) |
| `phase/innovation-lab` | `47b63f62` | 11 ahead | WHITE |
| `integration-candidate/ember-on-qc-20261018`, `milestone/ember-v21-integ-20261018`, `phase/ember-v21-final-20261015`, `phase/fire-companion*` | `582a2734`, `0b853288`, `4a70d9e7`, ... | superseded by `68061d85` | WHITE |
| `repair/windows-assistant-recovery-20261014` | `2e3262cd` | superseded (8/10 equivalent in canonical) | WHITE |
| Office repair/proposal/wip branches `6bd91f5d`, `9769f8e8`, `ea6c4076`, `9f5f14ad` | — | superseded or abandoned | WHITE |
| `_V1` / M33-M39 line, `preserve/*`, `uri-repo/claude/project-thread-*`, `uri-repo/ccr-cab5ed06-9hwyc4` | various | not in canonical | WHITE (preserved; `ccr-cab5ed06` holds the only W1/SSRF/IDN/LEAK review receipts) |
| `audit/p0-comprehensive-20261021` (`D:\uri-dev\uri-p0-audit`) | on `ec2fab54` | P0 records only | not to be integrated without owner approval |

---

## G. Test results and verification evidence

See section A for the P0 re-runs. Recorded milestone results (not re-run by P0, HISTORICAL/REPORTED where marked):

| Commit | Result | Source |
|---|---|---|
| `fcc1f183` (Brain QC code) | pytest oi+ws 793 passed / 23 skipped; Flutter 788; release build OK; qcc-1 live 32/32 | `docs/operational_intelligence/brain_quick_controls/evidence/gates/closure_fcc1f183/` |
| `f3d5eb29` (profiles) | e-p2/e-p3 main 68/68, ret 12/12 | `docs/operational_intelligence/profiles_live/` |
| `bb61e976` (Ember code) | Flutter 855 passed / 5 skipped / 0 failed | Ember integration evidence on `68061d85` |
| `22b53b78` (UI controls code) | pytest oi+ws 805/23; Flutter 799; ui-2 26/26; uiv2-1 68/68 | UI-controls branch evidence |
| `3e769fdf` (Office tip) | office+office_u2 811 passed / 1 failed (bundle not built); live a16 13/13, o9 34/34 on composite `0283aab2` (64K profile, simulated input) | `D:\uri-dev\uri-auth-live\evidence\` (outside git) |
| `85f6a0ec`, `eaeb10c1` (FCV-R) | live 29/29, 12/12, 5/5 | FCV records outside git |
| `7c7a7776` (VRAM-R1) | 710 passed / 22 skipped — HISTORICAL/REPORTED, no log | report §10 |
| `67d45317` (tiers) | no result (`D:\uri-dev\lifecycle\suite_67d45317.log` truncated, 64 bytes) | — |

---

## H. Pending integrations

Full assessments: `docs/audit/p0_20261021/P0_INTEGRATION_PLAN.md`.

| Queue | Candidate | State | Owner approval needed |
|---|---|---|---|
| Q-1 | Ember V2.1 `68061d85` | technically ready (AwF, subagent class); fast-forward possible | yes |
| Q-2 | UI Controls & Typography `e9ee7409` | repairs R1-01/R1-02 + re-review first | after repair |
| Q-3 | Reviewer tiers `67d45317` | review + test run first | after review |
| Q-4 | VRAM-R1 research record `7c7a7776` | code already in canonical; records only | optional |

Not eligible: `eaf3bf69` (REJECT), Qwen3.8 (research, no ACCEPT), any research branch.

---

## I. Blocked, paused and abandoned work

| Item | State | Reason |
|---|---|---|
| Driver-verified independent review | RED until 2026-10-22 14:03 | Codex rate limit; Claude CLI logged out |
| `milestone/sched-token-acl-2` | RED | R4 REJECT (check-then-use race) |
| P1 profile | YELLOW | CRASH-1 0xC0000409, demotion 99->21 tok/s |
| Phase 2 freeze, C7 cutover, EXE-1b, PA-1..PA-13 | YELLOW | physical / owner gates |
| W2 thread, LINK-REP-1, IDN-2, ONBOARD-1, SETTINGS-1 | WHITE | owner stopped thread 2026-10-12 |
| Adaptive Runtime R2 | WHITE | AC1/AC3 failing in ledger; report incomplete |
| Qwen3.8-27B | WHITE | r4 audit waits for Codex |
| `_V1` line (M36/M37/M38, dynamic planning, dictation) | WHITE | no salvage/retire decision |
| DL3C `4ca4a02a` | WHITE (abandoned) | duplicate of auditor-fallback branch |
| `wip/office-manual-r2-repair` `9f5f14ad` | WHITE (abandoned) | superseded |

---

## J. Known defects and limitations (open)

| ID | Severity | Area | Defect | Location | Next action |
|---|---|---|---|---|---|
| D09 | HIGH (hazard) | host | `\URIServer` scheduled task runs legacy pre-SSRF server at logon | Windows Task Scheduler | owner: disable (not delete) |
| UI-R1-01 | MEDIUM | UI controls | QcToggle not operable by keyboard or screen reader (Semantics button with no `onTap`, `excludeSemantics: true`, no focus) | `uri_ui/lib/living/integration/qc_toggle.dart:111-140` @ `e9ee7409` (confirmed by P0) | repair before Q-2 |
| D01 | MEDIUM | scheduler | api-token file written with plain `write_text`, inherits folder ACL | `uri_scheduler/service.py:269-271` (confirmed by P0) | new reviewed repair (ACL-2 rejected) |
| D10 | MEDIUM | working system | random provider-key / credential secrets every start; saved keys unreadable after restart (impact not live-tested) | `scripts/run_uri_integrated_server.py:83-84` (confirmed by P0) | design fix (feeds P2) |
| D14 | MEDIUM | Assist | every perception adapter is `UnavailableAdapter` | `uri_assist/perception.py:305-323` (confirmed by P0) | P9 |
| GRF-P0-1 | MEDIUM | Graphify | working-system path rebuilds a capability-only index per turn, forwards without skill/memory filter, ignores `GRAPHIFY_HINT_ENABLED` (read only in `decision_engine.py:66`) | `uri_core/core/paired_reasoning.py:78-110` (confirmed by P0) | bounded repair + review (frozen-file check first) |
| POL-P0-1 | MEDIUM | governance | canonical lifecycle SKILL.md says a separate Claude session review is never an independent ACCEPT, but `348677b7`, `cd4a7963`, `ec2fab54` were integrated on subagent reviews under the 2026-10-17 owner tier policy, which lives only on `67d45317` | `.claude/skills/uri-development-lifecycle/SKILL.md:97-121` | integrate Q-3 or amend text (owner) |
| D08 | MEDIUM | FCV | secure rollback tree cannot import `uri_web` | FCV-R | owner decision |
| UI-F-1 | MEDIUM | runtime UX | no automatic Standard->P3 vision fallback | CAP-RT5 | owner decision |
| UI-R1-02..R1-06 | LOW | UI controls | live count overstated (26 not 30), false notice after 600 s gate, missing restore record, label, dialog case | `e9ee7409` | repair with R1-01 |
| S4-01..S4-03 | LOW | Office | raw `Refused: CODE (detail)` texts, delete-card wording, related | `a2ui_hub.dart`, `office_controller.dart`, `ops.py` | repair + review |
| AF-S1-02/03/04/06, AF-S3-01/02 | LOW | lifecycle | auditor-fallback LOW findings | lifecycle tooling | batch repair |
| GRAPHIFY R2-01 | LOW | Graphify | open LOW from LEAK-1 R2; GRAPHIFY-SKILL-1 never implemented | `docs/graphify/` | batch repair |
| D01b | LOW | scheduler | token comparison not constant-time | `uri_scheduler/service.py:105` | with D01 |
| D11 | LOW | legacy | hardcoded default key-store secrets on legacy path | legacy server | with D09 |
| D15 | LOW | tests | Assist tests fail instead of skip without Playwright | `tests/assist` | test hygiene |
| D16/D17 | LOW | docs | stale Assist docs; W2/RW1 briefs cited but absent | docs | docs repair |
| DOC-1 | LOW | docs | canonical ledgers (`URI_MILESTONE_TRACKER.md`, `PROJECT_MEMORY.md`, `URI_ACTIVE_MILESTONE.md`) stop at Phase 1 (`925ad45c`); `URI_RUNTIME_AUTHORITY_MANIFEST.json` stale; Office doc 08 stale | docs | superseded by this register; P1 to import |
| CRASH-1 / DEMOTE-P1 | open | runtime | P1 crash and demotion | — | owner decision |
| UIV2-DELTA-1 | LOW | UI V2 freeze | post-freeze deltas (QC, Office, later Ember/controls) without returning/perf re-run or re-freeze receipt | UI V2 | re-run with next live session |

---

## K. Next actions and responsible agents

Reviewer availability rule (DEC-074/075): Codex preferred, claude_cli fallback, fresh isolated subagent tier 3,
owner-attested tier; never weaken gates. Antigravity: housekeeping and evidence preservation only (DEC-004).

| # | Action | Agent | Needs owner? |
|---|---|---|---|
| N-1 | Decide Q-1 Ember V2.1 integration (see plan) | owner | yes |
| N-2 | Disable `\URIServer` (`Disable-ScheduledTask -TaskName 'URIServer'`) | owner (system setting) | yes |
| N-3 | Repair UI-R1-01..R1-06, commit R1 record, R2 re-review, re-run ui-2 / uiv2-1 | Claude (impl) + Codex or subagent (review) | no (routine); integration yes |
| N-4 | Review `67d45317` and run its full `tests/dev_workflow` suite | Codex after 2026-10-22 14:03, else tier 3 | no; integration yes |
| N-5 | Bounded repairs D01/D01b, GRF-P0-1, S4-01..03, AF LOWs, D15 | Claude/Codex via lifecycle | no (routine); integration yes |
| N-6 | Decide P1 disposition, F-1 behaviour, D08, POL-P0-1 wording | owner | yes |
| N-7 | Live session (one GPU window): UI V2 returning 12/12 + perf 3/3 on the combined candidate; W1 Windows live run | Claude driver under GPU lease | GPU override only if needed |
| N-8 | Qwen3.8 r4 re-check | Codex after reset | adoption yes |
| N-9 | Start P1 (Milestone Manager + Lifecycle V3.1) importing this file | per roadmap | plan approval per DEC-005 |
| N-10 | Decide fate of `_V1` M36/M37/dynamic-planning line and push of the local-only research/preserve branches | owner | yes |

---

## L. Integration history and receipts

| Date | Canonical move | Content | Receipt |
|---|---|---|---|
| 2026-10-08 | published `037229c` + 7 tags | consolidation | `docs/governance/consolidation/URI_GITHUB_PUBLICATION_RECEIPT_20261008.md` |
| 2026-10-09 | FF to `7160614`, `f24d57a`, `b02ed4f`, `dc1ce81`, `6b48830` | WS hardening, companion settings, scheduler, A2UI, live voice | `docs/working_system/canonical_integration/`, `docs/scheduler/`, `docs/a2ui/`, `docs/voice/live/` |
| 2026-10-10 | FF to `ffdf534` | final integration (P-GOV-1, rail orb, INT-F1/F2) | `docs/integration/final_20261010/INTEGRATION_RECEIPT.md` |
| 2026-10-11..12 | `cbdf3f2c`, `03f0bf2c`, `e07b71c6`, IDN, `e761ce8f` | DL2, W1/A0, SSRF-1, IDN-1/1b, GRAPHIFY-LEAK-1 | receipts on `uri-repo/ccr-cab5ed06-9hwyc4` |
| 2026-10-13..15 | `1b5423bc`, `7d3d0f63`, `85f6a0ec`, `2eff03d0` | Office M1/M2 frozen-authorised, DL3/3A, FCV-R, UI V2 | `receipts/dev-lifecycle-3-20261015`, `receipts/ui-v2-20261016` |
| 2026-10-16 | `eaeb10c1`, `57f2d567` | Office O2, DL3B | `D:\uri-dev\lifecycle\URI-OFFICE-O2-INTEG-r4\state\RECEIPT.md` (outside git) |
| 2026-10-17 | `7893aaed`, `3e769fdf`, `348677b7`, `cd4a7963` | Office completion + LOW repairs, UI V2 freeze, auditor fallback, runtime profiles | `docs/operational_intelligence/RUNTIME_PROFILES_INTEGRATION_PLAN.md`; `INTEGRATION_RECEIPT_348677b7.md` |
| 2026-10-18 | `feaabe3f`, `ec2fab54` | Brain Quick Controls, Brain QC closure | `docs/integration/qc_ember_20261018/01_BRAIN_QC_INTEGRATION_RECEIPT.md`; `D:\uri-dev\lifecycle\BRAIN-QC-CLOSURE\INTEGRATION_RECEIPT_ec2fab54.md` (outside git) |
| 2026-10-21 | none | P0 audit; no canonical change | — |

Dates and some SHAs before 2026-10-16 are taken from receipts and memory notes; ancestry of every listed SHA in
canonical was verified by the P0 evidence agents (`git merge-base --is-ancestor`).

---

## M. Changes since the previous audit (Antigravity, 2026-10-20)

No canonical change since `ec2fab54` (2026-10-18). P0 corrections to Antigravity findings (full verdict tables in
evidence files 10-60):

| Antigravity claim | P0 verdict | Evidence |
|---|---|---|
| Graphify "D. Partially implemented" | INCORRECT: native runtime Graphify implemented, tested, integrated, frozen; dev skill is separate tooling | 50 |
| Word/PPT authoring integrated at `36395b09`/`efeb6220`; paths `src/office/...` | REFUTED: commits do not exist; real paths `uri_office/authoring/docx_ops.py`, `pptx_ops.py`; integrated via `16e040e7`/`84328f8b` -> `7893aaed` | 30, P0 `git cat-file` |
| MCP bridges at `43224b1a` | REFUTED: commit does not exist; bridges exist and pass tests | 40, 50 |
| "Zero COM / no LibreOffice daemons" | PARTIAL: no COM; LibreOffice runs as persistent headless UNO listener | 30 |
| NVIDIA RTX 4080 / CUDA | REFUTED: AMD Radeon RX 7900 GRE, Vulkan | P0 `Win32_VideoController` |
| 768 MiB headroom formula in `gpu_guard.py`; dual-signal watchdog in production | REFUTED: research prototype only; production uses `gpu_lease.py` ±512 MiB and `perf_monitor.py` | 10 |
| P2 = q4_0 KV with MTP; P3 = fail-safe minimum | REFUTED: P2 keeps q8_0, MTP off; P3 not the smallest | 10 |
| Qwen3.8-35B-A3B, drop-in once GGUF published | REFUTED: 27B dense; GGUFs already used; criterion B4 not met | 10 |
| Ember / UI controls "awaiting reviewer gate"; UI controls "30/30, accepted" | REFUTED: Ember awaits owner authorisation; UI controls has open MEDIUM, live 26/26 | 20 |
| Solar shaders integrated at `07a2f380` | PARTIAL: R&D commit; shaders reached canonical via merge `ab8f8227` | 20 |
| W1 integrated at `ffdf534`; SSRF at `03f0bf2c`/`11d739b6`; push-to-talk in `uri_assist/bridge.py`; TLD blocking | REFUTED (W1 = `03f0bf2c`, SSRF = `e07b71c6`, `11d739b6` absent, no voice code in bridge, TLD list only detects links) | 40 |
| Lifecycle state machine DRAFT->...->COMPLETED, UUID task IDs | INCORRECT: no such code in canonical | 50 |
| Milestone Manager V1 "36/36 verified" | file-existence check only; ledger cites non-existent commits and mislabels Brain QC | 50 |
| AR2 numbers (27.6 tok/s, prefill 1,771->916); Codex reset 2026-10-22 | CONFIRMED (model is `gpt-6-sol`, not "GPT-4o") | 10 |
| Ember 855 tests; clean merge onto `ec2fab54`; `\URIServer` hazard | CONFIRMED | 20, 40, P0 live probe |

---

## N. Evidence gaps and unresolved questions

| Gap | Affects verdict? |
|---|---|
| Many review records and receipts live only under `D:\uri-dev\lifecycle\`, `D:\uri-dev\uri-*-live\` or on `uri-repo/ccr-cab5ed06-9hwyc4` (outside canonical tree) | No for integration status (git ancestry verified); yes for durability: if those disks or branches are lost, the review history is lost |
| VRAM-R1 r3 ACCEPT and "710/22" have no review file or log | No (accepted code later re-qualified as CAP-RT2) |
| Office C1-C3 Claude review records not found | No (later S1-S4 and Codex driver reviews exist) |
| No live run on canonical `ec2fab54` itself (Office, FCV core journeys, W1) | Yes for "live-verified at canonical": rows say live on the named commit only |
| Flutter suites not re-run by P0 | No (recorded logs checked) |
| UI V2 returning/perf journeys not re-run since freeze deltas | Yes for Q-1/Q-2 live requirement |
| Owner chat authorisations cited by receipts were not independently seen | No (receipts are the record) |
| M6-M30, M32/M33/M35/M39 statuses rest on documents | No (pre-consolidation history) |
| Uncommitted research evidence in `C:\Users\cheta\Development\uri-adaptive-runtime` (135 entries) | Preserved by P0 as a copy: `D:\uri-dev\preservation\p0-20261021\uri-adaptive-runtime\untracked_and_modified.tar`, SHA-256 `82b357c97bd5e42a7472ad416614a4fc3531a73dfde1821b0f3a225329995035`; source worktree untouched |
| UI-controls R1 review existed only as an untracked file | Copied to `docs/audit/p0_20261021/evidence/preserved/` (SHA-256 `8d3eeb20...50fc12`) |
| Personal information sovereignty has no prior design or ruling | Recorded as new owner policy in `decisions.md` (DEC-089); design is P2 |
