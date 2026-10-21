# P0 audit 2026-10-21 — 10 Brain & runtime (evidence record)

Auditor: read-only Claude subagent (P0 comprehensive audit). Repository: shared object store, audit worktree
`D:/uri-dev/uri-p0-audit` (detached, HEAD `ec2fab5493578a4f5a805642153d56b4d5ea59fa`, tracked tree clean; only
untracked `docs/audit/`). CANONICAL = `uri-repo/integration/git-sync-20261008` @ `ec2fab54` (local branch
`integration/git-sync-20261008` @ `348677b7` is stale and was not used as canonical).

Nothing was modified, committed, started or loaded. No GPU, no port 18470. Commands actually run by this audit
(COMPLETED_WITH_RESULT unless stated): `git show/log/diff/merge-base/ls-tree/grep`; `python scripts/ws_frozen_check.py
D:/uri-dev/uri-p0-audit` (read-only; rc 0); one CPU-only pytest (below). Everything else is cited from committed or
on-disk records, labelled RECORDED (written by the milestone itself) or REVIEW (independent reviewer file).

## (a) Acceptance criteria (defined before inspection)

| ID | Criterion |
|---|---|
| AC-1 | Every status separates implemented / tested / independently reviewed / integrated (ancestor of `ec2fab54`) / live-verified, each with an exact SHA. |
| AC-2 | Positive claims rest only on COMPLETED_WITH_RESULT evidence that names its commit; recorded counts are marked RECORDED and, where cheap, re-derived. |
| AC-3 | Frozen-boundary claims are checked against git objects at the freeze tag and at `ec2fab54`, not against prose. |
| AC-4 | For each pending candidate: base, ahead commits classified code vs docs/evidence, review state, frozen impact, regression and live needs, rollback. |
| AC-5 | Each Antigravity claim gets CONFIRMED / REFUTED / PARTIAL / UNVERIFIABLE with a primary-evidence path. |
| AC-6 | Gaps state exactly what is missing and whether it changes a verdict. Memory notes and Antigravity text are HISTORICAL/REPORTED only. |

## Primary evidence produced by this audit

| ID | Command / check | Result |
|---|---|---|
| E-1 | `git merge-base --is-ancestor f791d65c ec2fab54` (freeze commit of tag `accepted/runtime-v1-freeze-20261007`) | ancestor |
| E-2 | `git diff --name-status f791d65c ec2fab54 -- model_lab` | 6 files, all `A` (added): `model_lab/evidence/runs/repro20261008_{mtp2,nomtp}/...` from `ea06d3b5`. **No frozen model_lab file modified or deleted.** |
| E-3 | `python scripts/ws_frozen_check.py D:/uri-dev/uri-p0-audit` at `ec2fab54` | `ok: true`, Phase 1 zip `31a34dcb…98cf7` 121 files, `unapproved_drift: []`, `unapproved_protected_changes: []`; protected changes vs `037229c1` = `uri_core/app/server.py`, `uri_core/tools/fetch_url.py`, both recognised exact owner-approved blobs (D12; D2/D33). Output kept in the audit scratchpad, not committed. |
| E-4 | `pytest tests/oi/test_runtime_profiles.py test_runtime_profile_selection.py test_brain_quick_controls.py test_brain_qc_integration.py -q -B -p no:cacheprovider` at `ec2fab54` (system Python 3.13, pytest 9.1.1) | **95 passed, 1 skipped, rc 0, 14 s**; worktree still clean afterwards. Matches the receipt's post-integration figure. |
| E-5 | `git diff 7c7a7776 ec2fab54 --` for the five VRAM-R1 accepted files | `runtime_profiles.py`, `runtime_v1.py`, `tests/oi/test_runtime_profiles.py`, `RUNTIME_PROFILES_UI_CONTRACT.md`: identical; `scripts/ws_brain_host.py`: canonical is a superset (later Brain QC commits `0d599b6a`, `0e24ad00`, `4c61a0b3`, `01e06d70`, `6427b681`). |
| E-6 | `git merge-base --is-ancestor` of `cd4a7963`, `c3fc8bbc`, `f3d5eb29`, `4c61a0b3` → `ec2fab54` | all ancestors |
| E-7 | Parsed `qcc-1/summary.json`, `qcc-1/native-execution.json`, `profiles_live/evidence/live_summary.json`, `switch_live/sw6/switch_live.json` | see table rows QC-2, RP-2, RP-3 |

## (b) Capability table

Status vocabulary: IMPL = code exists; TESTED = test run result recorded; REVIEWED = independent review verdict;
INTEGRATED = in `ec2fab54` ancestry; LIVE = real-app/GPU run COMPLETED_WITH_RESULT. "Subagent" = fresh read-only
Claude subagent (lifecycle tier 3); none of these reviews is driver-verified (Codex over quota until 2026-10-22 14:03,
claude CLI logged out — RECORDED in receipts).

| ID | capability | objective | implementation location | branch@commit | tests (count, result, commit tested) | independent review verdict (+record) | live verification (+commit, date) | canonical status | limitations | remaining work | dependencies | next action |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| RT-1 | Resident Runtime v1 freeze | One resident Qwen3.6-35B-A3B UD-IQ3_S on stock llama.cpp b11425 Vulkan, 32K, q8_0 KV, mmproj on GPU, MTP n=2 | `model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md`, `model_lab/integration/local_brain.json` (PROTECTED path in `scripts/ws_frozen_check.py`) | tag `accepted/runtime-v1-freeze-20261007` → `f791d65c` | Freeze-time qualification suites RECORDED in freeze record §6/§8 (2026-10-06/07); not re-run | User ruling (freeze record header); no independent code review applicable | Qualification + soak 2026-10-07 00:14 (RECORDED); reproduction runs `repro20261008_mtp2/nomtp` committed in `ea06d3b5` | INTEGRATED (E-1); frozen files unmodified at `ec2fab54` (E-2, E-3) | `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json` `model_runtime.runtime_v1.integration_state` still says "NOT WIRED into the Core composition" (stale since OI/WS integration); manifest `status` CANDIDATE | none for the freeze itself | — | Refresh the manifest wording (docs) in a later milestone; owner |
| RT-2 | MTP draft (Standard) | +decode on structured/code turns | frozen `extra_args` `-md … --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU` (`local_brain.json`); stripped by `runtime_profiles._strip_mtp` | `f791d65c` / `ec2fab54` | VRAM-R1 accuracy runs `vr1r2_c64k_mtpon/off` RECORDED rc=0 (on `research/runtime-vram-r1-20261017`, not in canonical) | VRAM-R1 rounds (see VR-1) | Standard live in qcc-1 (`fcc1f183`, 2026-10-18): decode 146.7-150.5 tok/s calibration (RECORDED, recomputed by QCC-R3) | INTEGRATED (frozen default) | MTP+vision costs ~1.1 GiB; Standard next to the app AT_RISK -321 MiB (RECORDED, closure) | none | — | — |
| RP-1 | Runtime profile derivation (VRAM-R1 accepted code) | Derived launch shapes: ctx 16/32/64/128K × vision off/gpu/cpu × MTP on/off; frozen key returns the frozen config object unchanged; admission only on measured MiB | `uri_operational_intelligence/runtime_profiles.py` (MEASURED_MIB table), `runtime_v1.py`, `scripts/ws_brain_host.py --profile` | accepted on `7c7a7776`; integrated via `adeb6d08` → `cd4a7963` | `test_runtime_profiles.py` 12 tests; part of E-4 at `ec2fab54` (1 skip = probe files absent in canonical) | VRAM-R1 r3 ACCEPT on `7c7a7776` — only secondary: `docs/operational_intelligence/RUNTIME_PROFILES_INTEGRATION_PLAN.md:3` and memory; **no committed r3 review file found** (gap G-1) | Probes 2026-10-17 RECORDED on research branch | INTEGRATED | KV type, model, binary, batch, checkpoint flags stay frozen (docstring); `describe().qualified` hard-coded `False` (R8-04/R2-07) | none in code | — | — |
| RP-2 | P2 "Long context" (65536, off, MTP off), 13,658 MiB | 64K text-only | `runtime_profile_selection.SELECTABLE`; QC catalog id `long` | qualified on `f3d5eb29`; D3 guard `c3fc8bbc`; integrated `cd4a7963` | Regression gates RECORDED `profiles_live/evidence/gates_integ` (cand 7,255 passed; failure set = canonical 6F/20E pre-existing); E-4 at `ec2fab54` | Subagent RPI-R1..R9 all ACCEPT WITH FINDINGS; R8 on `91f2b0bd` (2L+3I, fixed `d1545c9e`); R9 on `cd4a7963` (1L+1I). Files: `D:\uri-dev\uri-profiles-live\reviews\r1..r9\` (outside git); round table in `UI_QUALIFICATION_RUNTIME_PROFILES.json` and receipt `D:\uri-dev\lifecycle\RUNTIME-PROFILES-INTEG\INTEGRATION_RECEIPT_cd4a7963.md` | `e-p2-main` 68/68, `e-p2-ret` 12/12 on `f3d5eb29` (E-7, `live_summary.json`); soak-p2-e 60 min PASS (RECORDED); sw5 on `f3d5eb29`, sw6 on `c3fc8bbc` COMPLETED_WITH_RESULT, all recalled, worker pid constant (E-7); qcc-1 on `fcc1f183` | INTEGRATED (E-6) | n=1 soak on a light desktop; vision off | none | — | — |
| RP-3 | P3 "Standard, draft off" (32768, gpu, MTP off), 14,360 MiB | Vision kept, ~1.2 GB less than Standard | same; QC catalog id `standard-nodraft`, Draft chip | as RP-2; Draft chip in `ec2fab54` | as RP-2; QC gates at `fcc1f183`: pytest oi+ws 793 passed / 23 skipped (log header `HEAD=fcc1f183`, `brain_quick_controls/evidence/gates/closure_fcc1f183/pytest_oi_ws.log`) | as RP-2 + QCC-R1..R3 (QC-2) | `e-p3-main` 68/68, `e-p3-ret` 12/12 on `f3d5eb29`; soak-p3-e, assist-p3-e 3/3 (RECORDED); qcc-1 P3 via Draft + Assist vision on P3 (`fcc1f183`, 2026-10-18T11:22Z) | INTEGRATED | Near the estimated margin (AT_RISK +474 one evening); Assist check used session-process classes with stand-ins (L-2) | none | — | — |
| RP-4 | P1 (65536, gpu, MTP off), 14,764 MiB | 64K + vision | measured only; refused by `SELECTABLE`, `write()`, QC catalog `qualified: False`, host `_sync_selection_once` (R9-01 fix `4c61a0b3`) | — | refusal covered in E-4 | RPI rounds; R9-01 | `p1b-main` 52/57 with CRASH-1 (0xC0000409) on `fa0a70e6`; soak-p1 demotion 99→21 tok/s (RECORDED) | NOT SELECTABLE (refusal integrated) | CRASH-1 root cause unverified (hypothesis: host commit exhaustion); DEMOTE-P1 open | E1' experiment, fixed pagefile / crash dumps (owner) | owner approval for E1' | Owner decision: retire or investigate |
| QC-1 | Brain Quick Controls | Thinking per turn; Vision/Context load-time switches only to qualified catalog entries; host is second authority | `uri_operational_intelligence/brain_quick_controls.py`, `worker_bridge.py`, `scripts/ws_brain_host.py`, `uri_ui/lib/living/integration/brain_quick_controls.dart` | `4e827178` (code `5bcf1f24`) → canonical `feaabe3f` | gates RECORDED at `5bcf1f24`; E-4 | Subagent R1 REVISE → R2/R3/R4 AwF (`docs/operational_intelligence/brain_quick_controls/review/R1..R4_report.md`); integration IC-1/IC1-R2/FINAL (`docs/integration/qc_ember_20261018/review/`) | qc-1..qc-6 (RECORDED; qc-6 on the `cd4a7963` merge) | INTEGRATED | QC-F1,F2,F3,F5,F6,F7,F10 carried open (receipt) | see QC-2 | — | — |
| QC-2 | Brain QC closure (ec2fab54) | P3 via Draft; mismatch line; Assist vision lock | 7 files vs `feaabe3f` (receipt) | `milestone/brain-qc-closure-20261018` @ `ec2fab54` (code `fcc1f183`) | `fcc1f183`: pytest 793p/23s, flutter 788, release build OK, frozen ok (RECORDED); `ec2fab54`: 95p/1s (E-4, this audit) | QCC-R1 REVISE (`cde75580`), QCC-R2 AwF 4L (`0988176d`, committed `review/closure/REVIEW_QCC_R2.md`), **QCC-R3 ACCEPT on `ec2fab54`, 2 INFO** (`D:\uri-dev\lifecycle\BRAIN-QC-CLOSURE\REVIEW_QCC_R3.md`, outside git) | qcc-1 32/32 PASS, COMPLETED_WITH_RESULT, `source_head fcc1f183`, runtime_verified 361 files, `brain_config_digest_unchanged: true`, exit 0, 2026-10-18T11:22Z (E-7); qcc-uiv2 68/68 (RECORDED) | INTEGRATED (canonical tip) | Live Assist vision lock + mismatch line unit/widget-tested only; no physical input | — | — | — |
| R9-01 | Host selection write restricted to SELECTABLE | Host never writes a P1/research selection | `scripts/ws_brain_host.py:434-440` | `4c61a0b3` | catalog vs SELECTABLE test in `test_brain_quick_controls.py` (in E-4) | finding raised by RPI-R9 (LOW, doc); code fix not separately re-reviewed by an RPI round, covered by later QC IC reviews | n/a | **INTEGRATED — fixed in code** (memory note "open R9-01" is stale) | `RUNTIME_PROFILES_LIVE_RESULTS.md` §9 wording still the pre-fix text | none (docs wording only) | — | Optional doc touch-up |
| VF-1 | Automatic Standard→P3 vision fallback ("F-1") | Standard vision when it fits; 32K-no-MTP otherwise; clear refusal if neither; keep conversation | **Not implemented.** F-1 is a MEDIUM product-decision finding in `docs/ui/controls_typography_20261018/UI_CONTROLS_TYPO_REPORT.md` §6 (branch `milestone/ui-controls-typography-20261018` @ `e9ee7409`): from Long, Vision on always targets Standard (catalog order); if Standard does not fit the switch is refused (`REFUSED_DOES_NOT_FIT`) and vision cannot be regained | — | none for the fallback | UI-CONTROLS-TYPO R1 AwF calls F-1 "a real product limitation… owner decision" (`D:\uri-dev\uri-ui-controls-typo\docs\ui\controls_typography_20261018\review\R1_report.md`, untracked) | ui-2 (`22b53b78`, 2026-10-18) live-demonstrated the refusal (Standard 15.3 GB needed, 14.2 GB free) | NOT IMPLEMENTED. Canonical has: manual P3 via Draft; pre-stop fit refusal `REFUSED_DOES_NOT_FIT` (`ws_brain_host.py:514`); at cold start frozen waits `WAITING_FOR_GPU/GPU_CONTENDED` (`:262-265`), no automatic downgrade; conversation kept across switches (CONTEXT-1, sw5/sw6/qcc-1) | changes accepted catalog resolution order | owner decision, then plan, tests, live GPU run | UI-CONTROLS-TYPO (restore-after-failure) | Owner decides F-1 product rule |
| VF-2 | Restore after a failed switch (QC-F5) | One restore attempt to the last known-good qualified profile | `ws_brain_host.py` (+53), `worker_bridge.py`, `brain_quick_controls.py`, `tests/oi/test_ui_controls_switch_fallback.py` (12 tests) | `milestone/ui-controls-typography-20261018` @ `e9ee7409` (code `22b53b78`), 5 ahead of `ec2fab54`, local only | RECORDED at `22b53b78`: pytest oi+ws 805p/23s, flutter 799, frozen ok (`evidence/gates_22b53b78/`) | R1 ACCEPT WITH FINDINGS on `e9ee7409`: R1-01 MEDIUM + R1-02..R1-05 LOW, **unrepaired** (untracked review file) | ui-2 (`22b53b78`): injected failed start, restore READY 33.4 s; report says 30/30, reviewer counts 26 recorded checks (R1-02) | NOT INTEGRATED | failure injected before spawn (F-4) | repair R1-01..R1-05, re-review | owner approval | Repair + re-review before integration |
| GL-1 | GPU lease / fit check | Admission: margin = free − measured request; CONTENDED at shortfall ≥ 512 MiB, AT_RISK below +512 | `uri_operational_intelligence/gpu_lease.py` (`RUNTIME_V1_DEVICE_MIB=15626`, `AT_RISK_MARGIN_MIB=512`, `CONTENDED_SHORTFALL_MIB=512`) | canonical (WS hardening line, published `522939c` per memory) | `tests/ws/test_ws_hardening.py` etc. within RECORDED 793p gate at `fcc1f183`; not re-run here | Codex WS hardening rounds (RECORDED in commit subjects `9ae28f4f`, `b5fd75ca`) — record not re-read here | Lease histories committed (`docs/integration/final_20261010/evidence/gpu_lease_history_20261010.jsonl`) | INTEGRATED | no automatic downgrade | — | — | — |
| GL-2 | Performance/residency health | Detect silent eviction | `uri_operational_intelligence/perf_monitor.py` (`RESIDENCY_DROP_MIB=300` dedicated drop vs READY sample; `DEGRADED_DECODE_TPS=60`), `brain_health.py` | canonical | in recorded gates | — | OI-PERF-1 measured 2026-10-08 (docstring) | INTEGRATED | reports only, never restarts | — | — | — |
| GG-1 | `gpu_guard.py` (research) | Wait until no foreign GPU owner ≥ N MiB | `research/adaptive_runtime/r2/gpu_guard.py` | `research/adaptive-runtime` @ `7d035aa1` (also inside `research/vram-efficiency-20261010`) | `r2/test_r2_units.py` (RECORDED only) | none | research use only | NOT IN CANONICAL | contains no headroom formula | — | — | Archive as research |
| VR-1 | VRAM-R1 research record | Measured profile table, accuracy controls, audit trail | `research/runtime_vram_r1/` (157 files), `model_lab/evidence/runs/vr1*` | `research/runtime-vram-r1-20261017` @ `7c7a7776` (pushed to uri-repo), base `25048709` | "710 passed, 22 skipped" `tests/oi`+`tests/ws` — RECORDED in report §10 and `AUDIT_PACKAGE.md:80` only ("at 353347b2 and after the round-2 repair"); **no log file committed** | r1 REVISE on `c79ae681` (external), r2 AwF on `353347b2` (Claude reviewer session), r3 ACCEPT on `7c7a7776` — r1/r2 summarised in the report §13-14; **r3 not recorded in the branch** (report status line still "RE-CHECK PENDING") | probes and suite runs 2026-10-17 RECORDED | Code INTEGRATED (E-5); research record NOT in canonical (preserved on uri-repo branch) | worktree has untracked `research/runtime_vram_r1/crash_repro.py` + `evidence/crash_repro/20261017-141437_cr-p1/` (CRASH-1 repro attempt, uncommitted) | decide whether to import the record; commit or discard crash_repro | owner | Preserve; optional docs import |
| QW-1 | Qwen3.8-27B Brain experiment | Dev Brain candidate | `research/qwen38/` | `research/qwen38-27b-brain-20261016` @ `9689a666` (6 ahead, 168 behind) | lab harness RECORDED | Codex r1/r2/r3 REVISE; r4 not run (COOLDOWN until 2026-10-22 14:03); no independent ACCEPT (report header) | lab runs 2026-10-16/17 | NOT IN CANONICAL (research) | B4 integration not met; 7-task DV set | r4 re-check, larger DV set | Codex quota | Re-check after 2026-10-22 |
| AR-1 | Adaptive Runtime R2 | 128 MiB suballocation, planner, watchdog | `research/adaptive_runtime/r2/` | `research/adaptive-runtime` @ `7d035aa1` | `test_r2_units.py` RECORDED | none | campaign 2026-10-08/09; report §11-13 still `RESULTS_PENDING_*` placeholders | NOT IN CANONICAL | report incomplete; ledger "reading so far" shows AC1/AC3 failing | none planned | — | Archive |
| VE-1 | VRAM efficiency screening | 13-14 GiB combined target | `research/vram_efficiency/VRAM_EFFICIENCY_REPORT.md` | `research/vram-efficiency-20261010` @ `09c4b8ff` (contains AR-1 commits) | n/a | Codex verification findings repaired (`73089467` subject) | 2026-10-10 RECORDED | NOT IN CANONICAL | verdict: target not reachable without material regression | none | — | Archive |
| UC-1 | UI engine resource-cache cap | `URI_GPU_CACHE_MB` opt-in | `uri_ui/lib/main.dart` (+6) | `research/ui-vram-cache-20261010` @ `31dbd92a` | n/a | none | commit subject: "measured no effect" | NOT IN CANONICAL | no effect | none | — | Archive / drop |

## (c) Pending-integration candidate assessments

### C-1 VRAM-R1 research record (`7c7a7776`)
- Candidate `research/runtime-vram-r1-20261017` @ `7c7a7776`, base `25048709`, 4 commits ahead of canonical
  (`5b9bbca8`, `c79ae681`, `353347b2`, `7c7a7776`).
- **Code vs docs:** outside `research/runtime_vram_r1/` the branch touches 29 paths: 5 accepted files (already in
  canonical, identical or superseded — E-5), and 24 `model_lab/evidence/runs/vr1*` evidence files absent from
  canonical. Inside `research/runtime_vram_r1/` are report, audit package, acceptance criteria, probe/suite evidence
  and research harness scripts (`compare_suite.py`, `coexist.py`, `frozen_fit_record.py`, `switch_test.py`,
  `vlab`/`run_probe`), none imported by product code. **Nothing product-facing is pending**; the remainder is
  research record + research tooling.
- Acceptance evidence: r3 ACCEPT on `7c7a7776` is asserted only in the canonical plan and memory; the branch's own
  report still says round 3 PENDING. Required repair before any import: record r3 in the report (or attach the
  reviewer's file) and fix the stale status line.
- Risk: low (docs/evidence only). Frozen-file impact: none — it adds files under `model_lab/evidence/runs/`
  (additive, like `ea06d3b5`); `model_lab/integration/` untouched. Note `MEASURED_MIB` test skips without the probe
  files; importing `research/runtime_vram_r1/evidence/probe/` would turn that skip into a real check.
- Regression tests if imported: `tests/oi/test_runtime_profiles.py` (expect the skip to disappear), `ws_frozen_check`.
- Live requirements: none. Rollback: revert the import commit.

### C-2 UI Controls & Typography (`e9ee7409`, contains VF-2 restore logic)
- Base: cut from `feaabe3f`, merged `ec2fab54` at `a4935c2b`; 5 commits ahead, 0 behind; local only.
- Acceptance evidence: gates at `22b53b78` RECORDED; R1 subagent review ACCEPT WITH FINDINGS with R1-01 MEDIUM
  unrepaired (review file untracked in the candidate worktree), R1-02 live count overstated (26 recorded checks vs
  "30/30"), R1-03/R1-04 LOW truthfulness gaps in the restore path.
- Required repairs: R1-01..R1-05; correct 30/30 → 26/26; persist superseded restore record; gate stays closed while
  `fallback.result == IN_PROGRESS`.
- Risk: medium (changes `ws_brain_host.py` failure path and 43+ UI files incl. typography).
- Frozen-file impact: `ws_frozen_check` ok at `22b53b78` (RECORDED); touches frozen UI V2 files (additive claims
  not verified here).
- Required regression tests: `tests/oi` + `tests/ws`, `tests/oi/test_ui_controls_switch_fallback.py`, flutter test,
  release build, UI V2 68 journeys, `ws_frozen_check`.
- Live requirements: real failed-start (not injected) restore on GPU; Draft live switch (not exercised in ui-2).
- Rollback: revert commit on canonical.
- **F-1 is not addressed by this candidate**; it remains an owner product decision.

### C-3 F-1 automatic vision fallback (not yet a candidate)
- No branch implements it. A future candidate must: change catalog resolution (prefer a fitting qualified 32K+vision
  profile: frozen, else P3), refuse clearly when neither fits, keep the worker conversation (already true), and must
  not alter `local_brain.json` (frozen) or `SELECTABLE` semantics without review. Needs unit tests on resolution,
  a live GPU run where Standard does not fit but P3 does, and owner approval of the product rule.

## (d) Antigravity claim verdicts

Sources: `URI_HISTORICAL_RECOVERY_AUDIT_20261020.md` (Part 2) lines 104-122, `URI_AUTHORITATIVE_MASTER_REGISTER.md`
lines 77-78, Part 2 lines 16, 86, 91-99.

| # | Claim | Verdict | Primary evidence |
|---|---|---|---|
| A-1 | "768 MiB headroom = 400 DWM + 90 NVIDIA driver reserve + 278" used by `gpu_guard.py`; downgrade P1→P2/P3 when budget < 12,288 | **REFUTED (number exists elsewhere)** | 768 is `DEFAULT_HEADROOM_MIB` in `research/adaptive_runtime/r2/vram_planner.py:61` (`research/adaptive-runtime@7d035aa1`), rationale "burst 400 + reserve 90 + margin" (`:70`); 400 is desktop *burst*, not DWM; 90 is the adapter's never-handed-out reserve on an **AMD Radeon RX 7900 GRE** (freeze record header), not NVIDIA; 278 is never stated. `gpu_guard.py` contains no headroom formula. Research only, not in canonical. Canonical admission is `gpu_lease.py` (±512 MiB thresholds). No 12,288 downgrade rule exists in canonical. |
| A-2 | Dual-signal watchdog: `\GPU Non Local Memory Usage` rate > 256 MiB/s → AT_RISK; latency > 2.5× → DEGRADED and flush drafts; "in production" | **REFUTED** | Research prototype `research/adaptive_runtime/r2/residency_watchdog.py` (report §10, `ADAPTIVE_RUNTIME_R2_REPORT.md:114-134`): demoted **amount** > 256 MiB (not a rate) → AT_RISK; decode **throughput** < 0.6× expected (110 tok/s) for two windows → DEGRADED; never acts. Production (`perf_monitor.py`): dedicated drop ≥ 300 MiB and decode < 60 tok/s, report-only. No draft flushing anywhere. |
| A-3 | P2 uses q4_0 KV cache with MTP enabled | **REFUTED** | P2 key `(65536, "off", False)` (`runtime_profile_selection.py` SELECTABLE; QC catalog `long`); `runtime_profiles.py` docstring: KV cache type stays frozen (q8_0 in `local_brain.json`). |
| A-4 | P3 is "Fail-Safe, minimum VRAM footprint" | **REFUTED** | P3 = 32K + GPU vision, MTP off, 14,360 MiB; P2 (13,658) and 16K off/off (13,052) are smaller (`runtime_profiles.MEASURED_MIB`). The fallback/default is Standard (frozen). |
| A-5 | "Qwen3.8-35B-A3B" | **REFUTED** | `research/qwen38-27b-brain-20261016:research/qwen38/QWEN38_EXPERIMENT_REPORT.md:1,42`: Qwen3.8-**27B**, dense 64 layers. |
| A-6 | "Drop-in once standard GGUF (Q4_K_M) published; no pipeline redesign" | **REFUTED** | Same report: GGUFs UD-Q3_K_XL and IQ4_XS already used; recommendation provisional, B4 integration not met, no independent ACCEPT (lines 6-12, 20-30); KV 3.2×/token and 31 tok/s are structural limits. |
| A-7 | Qwen3.8 11/11 vs Qwen3.6 9/11 at 64K; code 5/7 → 6/7 | **REFUTED** | Report table line 115-117: Qwen3.6 64K 11/11, 128K 10/11; line 22: Qwen3.6 4/7 in every mode vs Qwen3.8 deep 6/7. |
| A-8 | Strata "heavily coupled to CUDA-specific memory management"; dropped as maintenance liability | **PARTIAL** | `model_lab/URI_ENGINE_STRATA_RESEARCH.md:509-516` and freeze record line 292/363-366: Strata is CUDA/HIP-only; URI runs Vulkan; rejection reason was "not applicable" (Strata targets non-resident experts; URI's model is resident), not porting cost. kv_stream.hpp is listed (verdict E). |
| A-9 | AR2: 27.6 tok/s collapse; prefill 1,771→916; TTFT 17.4→33.4 s | **CONFIRMED (as ledger data), PARTIAL as verdict** | `research/adaptive-runtime:research/adaptive_runtime/r2/SESSION_LEDGER.md:35` (`r2P_sub128_r1` 27.6), `:53` (30k fresh 916-933 vs 1,771-1,791; TTFT 33.0-33.7 vs 17.3-17.5). The formal AC1/AC3 verdict sections of the report are unfilled placeholders (`RESULTS_PENDING_SECTION_12`). |
| A-10 | Codex quota reset Oct 22; reviewer "OpenAI Codex / GPT-4o-code-review"; exhausted Oct 18 | **PARTIAL** | Reset 2026-10-22 14:03 CONFIRMED (`QWEN38_EXPERIMENT_REPORT.md:10-11`; `RUNTIME_PROFILES_LIVE_RESULTS.md` §8). Model REFUTED: auditor is "Codex gpt-6-sol via codex-exec" (same report line 8). Cooldown first recorded 2026-10-17 (qwen38 r4), not 10-18. |
| A-11 | P2/P3 "Accepted (RPI-R8)" / "Accepted (QCC-R3)", "Approved, Ready" (Part 1 rows 125-126) | **PARTIAL** | Verdicts are subagent ACCEPT WITH FINDINGS (RPI-R8) / ACCEPT (QCC-R3), not driver-verified; owner approved *integration* only, not default change/freeze/deployment (receipts). |

## (e) Evidence gaps

| ID | Gap | Effect on verdict |
|---|---|---|
| G-1 | No primary review file for VRAM-R1 rounds r1-r3 in git; r3 ACCEPT on `7c7a7776` asserted only in `RUNTIME_PROFILES_INTEGRATION_PLAN.md:3` and memory; branch report says "RE-CHECK PENDING". Background filesystem search for a `7c7a7776` review file was started but did not complete within this audit. | Does not affect canonical status (code later reviewed by RPI-R1..R9 and integrated). Affects the claim "VRAM-R1 independently ACCEPTED" → treat as REPORTED. |
| G-2 | "710 passed / 22 skipped" has no committed log; stated "at 353347b2 and after the round-2 repair", not explicitly at `7c7a7776`. Not re-run (would need a checkout of the research branch). | None for canonical (superseded by E-4 and the `fcc1f183` 793p gate). |
| G-3 | RPI-R1..R9, QCC-R3, UI-CONTROLS-TYPO R1 review files live outside git (`D:\uri-dev\...`). Only RPI-R8/R9 and QCC-R3 were opened here. | Verdicts are reproducible only while those folders exist; recommend importing. |
| G-4 | Live P2/P3 journeys, soaks, sw5/sw6, qcc-1 not reproduced (GPU forbidden); assessed from committed JSON. | None; positive live claims are RECORDED COMPLETED_WITH_RESULT with exact source heads. |
| G-5 | No driver-verified (Codex/claude CLI) review exists for any Brain/runtime milestone since 2026-10-17. | All acceptance is subagent-class; disclosed in every row. |
| G-6 | `URI_RUNTIME_AUTHORITY_MANIFEST.json` (2026-10-08) is stale ("NOT WIRED", CANDIDATE). | Documentation drift; no effect on frozen-boundary result (E-2/E-3). |
| G-7 | Untracked `crash_repro.py` + `evidence/crash_repro/20261017-141437_cr-p1/` in `D:/uri-dev/uri-runtime-vram-r1`; result not inspected. | Could bear on CRASH-1; P1 stays unqualified either way. |
| G-8 | GPU lease tests (`tests/ws/test_ws_hardening.py`) not re-run here; covered only by RECORDED gate at `fcc1f183`. | None (gate log has exact HEAD). |

## Self-review against AC-1..AC-6

- AC-1: each row separates IMPL/TESTED/REVIEWED/INTEGRATED/LIVE with SHAs; "integrated" checked by `merge-base` (E-1, E-6). MET.
- AC-2: counts re-derived where cheap (E-4 95/1; qcc-1 32 checks; live_summary e-p2/e-p3 68/12; p1b 52 with 2 failures); others marked RECORDED. Corrected one inherited claim: memory "open R9-01" is stale (fixed `4c61a0b3`). MET.
- AC-3: frozen boundary checked by git object diff at the tag and by `ws_frozen_check` at `ec2fab54`. MET.
- AC-4: C-1, C-2 complete; C-3 described as non-existent candidate. MET.
- AC-5: 11 claims, each with path. Initially I considered A-2 "PARTIAL" (dual-signal concept exists); repaired to REFUTED because every stated parameter (rate, 2.5×, draft flush, production) is wrong. MET.
- AC-6: gaps G-1..G-8 with effect. MET.
