# BRAIN-QC-20261018 — independent review R4 (refresh onto canonical cd4a7963)

Reviewer: subagent, read-only. Repo D:/uri-dev/uri-brain-quick-controls. Date 2026-10-18.

## Verdict: ACCEPT WITH FINDINGS (2 LOW, 3 INFO; none blocks)

## Acceptance criteria (set before review)
A1 HEAD = cfb877e5; canonical = cd4a7963 on uri-repo. A2 0226e7ee is a clean merge (tree identity) or every manual change is justified.
A3 No QC path asks the worker/host for a profile canonical refuses; refusals shown truthfully. A4 R9-01 correct, fails closed,
no Standard/Long regression, tests meaningful. A5 catalog qualified set == SELECTABLE; only Standard/Long offered; P1 refused;
UI never says the backend is "qualified". A6 gate .head = 76088dad; no non-doc code change after 4c61a0b3; numbers match logs.
A7 qc-6 re-derives identically; numbers and the demotion ordering hold. A8 boundaries: frozen paths and runtime files unchanged vs cd4a7963.

## Results
| # | Result | Evidence (R = ran, D = read) |
|---|---|---|
| A1 | MET | R: `git rev-parse HEAD` = cfb877e5; `git ls-remote uri-repo refs/heads/integration/git-sync-20261008` = cd4a7963. Parents: 0226e7ee = f7c08dbc + cd4a7963. |
| A2 | MET | R: `git merge-tree --write-tree f7c08dbc cd4a7963` = 58f67b16 = `0226e7ee^{tree}`. No manual change. |
| A3 | MET with R4-01 | D: worker and host both validate with `QC.switch_target`; only Standard (FROZEN_KEY) and Long (65536,off,False) pass, both in `PS.SELECTABLE`. The host never calls `PS.write`; it writes the file itself, now gated by SELECTABLE (R9-01). P3 → PROFILE_NOT_OFFERED, P1 → PROFILE_NOT_QUALIFIED at both layers. Interaction gap: R4-01. |
| A4 | MET | D: 4c61a0b3 adds 6 lines to `Host.sync_selection`. For a non-SELECTABLE `cfg.profile` it unlinks the file (missing_ok), sets `selection_error=PROFILE_NOT_SELECTABLE`, and writes nothing. The worker then reads absent = frozen and fails closed: the argv does not match, so FOREIGN_INSTANCE. A P1 host can still switch to Long: the host's `same` check compares against its own cfg, and a later sync writes Long and clears the error. Standard/Long are covered by the existing tests `…switch…` (Long written, Standard leaves no file) and `test_host_start_removes_a_stale_selection_for_the_frozen_config`. The new test proves that the stale file is removed, the error is recorded and `PS.select` falls back to frozen. Meaningful. |
| A5 | MET | D: catalog qualified = {frozen, P2, P3} = SELECTABLE; offered = {frozen, P2}; P1 qualified False; pinned by `test_catalog_agrees_with_the_integrated_selectable_set`. UI strings: only "Not qualified." / "No qualified Brain profile offers this." / "…not qualified yet." are refusals. `qualified` is read only from catalog option views, never from `runtime_profiles.describe`. |
| A6 | MET | D: 5 .head files = 76088dad. R: `git diff 4c61a0b3 76088dad -- . ':!docs'` and `git diff 4c61a0b3 cfb877e5 -- . ':!docs'` are both empty. The harness change b653c154 (runtime3→runtime4 in go.sh, qc_session.py, run_qc_ui.py) is under docs/. Logs: pytest "778 passed, 23 skipped" exit=0; flutter "+779 All tests passed" exit=0; analyze "4 issues found", all info, in office_o2_live_check.dart, providers_screen.dart, chat_supervised_handoff_test.dart, assist_mode_test.dart (not QC files); uibuild-release.log "Built … uri_ui.exe" exit=0; frozen_check.json ok:true, unapproved_protected_changes []. UI V2: `git diff --numstat 7893aaed 76088dad` gives oi_conversation.dart 98/0 and living_composer.dart 37/0. |
| A7 | MET | R: copied qc-6 and summarize.py to scratch, deleted summary.json, re-ran `python -I -B summarize.py qc-6`. The output is IDENTICAL (deep compare) to the committed summary. 22/22 PASS, classification COMPLETED_WITH_RESULT. Switches 30.1 s (FITS +1,648.5) and 37.2 s (AT_RISK −325.5); stop 3.548/3.559 s. Turn decode 40.58 / 99.81 / 149.17 tok/s. recall-long and recall-standard both answer "4817". worker_processes constant (17420, 17532). lease_after FREE; brain_config sha256 before = after (112c0595…); runtime_verified ok 360/0, runtime_candidate_head b653c154. I also hashed 8 runtime4 code files (`git hash-object`): they equal the b653c154 blobs. |
| A7 ordering | MET | D: brain-ready.json says READY at 07:57:42.48–42.52 UTC. The first observation (the app's automation transport) is at 07:57:45.85. uri_ui.exe is missing from the 07:57:40.8 GPU census and first appears at 07:57:46.34. Calibration was healthy (frozen calibration 142.2). The 773.5 MiB demotion of llama-server (dedicated 15,555.7→14,782.2; non-local 1,120.6→1,894.1) falls between the 07:58:14.2 and 07:58:19.7 samples, while uri_ui grew to 164 MiB. The perf turn at 07:58:25.6 then measured 40.6 tok/s. After the switch, frozen calibrated at 149.8. The report's explanation holds. (host_state_sequence shows READY at 07:57:46.3: that is the sample time, not the transition time.) |
| A8 | MET with R4-02 | R: `git diff --stat cd4a7963 cfb877e5` over every ws_frozen_check PROTECTED path + scripts/ws_frozen_check.py: empty. runtime_profiles.py, runtime_profile_selection.py, runtime_v1.py, model_lab/: empty. The non-doc diff touches 10 files: 4 added (catalog, QC dart, 2 test files) and 6 modified (see R4-02). |

Ran: `python -m pytest tests/oi tests/ws -q -p no:cacheprovider` → 778 passed, 23 skipped, exit 0 (independently matches the gate). `flutter test --no-pub test/living/brain_quick_controls_test.dart` → 18 passed. A scratch probe test (outside the repo, `tests` imported read-only) confirms R4-01. Working tree clean afterwards.
Not verified: the full flutter suite (779), analyze and the release build were not re-run by me; I read them from the logs only. Live qc-6 was not re-run (no GPU, by brief). Neither affects the verdict.

## Findings
**R4-01 LOW — worker_bridge.py `_brain_reconfigure` (merge-semantics interaction with canonical SELECTABLE).**
A host started with `--profile` on a non-SELECTABLE research profile (P1) no longer writes a selection. Before R9-01 the canonical code ignored it anyway as PROFILE_NOT_QUALIFIED. So the worker's `self.cfg` stays frozen. `_brain_reconfigure("standard")` then calls `RP.plan_change(RP.describe(self.cfg), …)`, which answers `reload: False`. The reply is `{"requested": None, "already_active": True}` and no host request is sent, although the host runs P1.
The UI offers Standard because `active` is null, and the user gets past the confirm dialog. The result is a silent no-op: no notice. The chips read "Vision: On (not running)" and "Context: 32K (not running)".
The probe reproduced this: REQUESTS [] for "standard". "long" sends the request correctly.
Impact: fail-closed is preserved, and the path is reachable only through a research `--profile` launch, not the product launcher. Recovery is via Long, or by relaunching the host.
Fix: when an alive host reports a `profile` whose key differs from the target, send the reconfigure; the host's own `same` check still yields ALREADY_ACTIVE when it really is active. At minimum, return a refusal that the UI explains. Add a unit test: host profile P1, worker cfg frozen, target standard → one reconfigure request.

**R4-02 LOW (doc) — BRAIN_QC_REPORT.md lines 231–234; BRAIN_QC_QUALIFICATION.json line 510.**
The text says "BRAIN-QC changes three existing files: ws_brain_host.py, brain_health.py, run_uri_integrated_worker.py". Against cd4a7963 it actually modifies six existing files. The other three are `uri_operational_intelligence/worker_bridge.py` (106 lines changed in the diff stat), `uri_ui/lib/living/integration/oi_conversation.dart` (+98) and `uri_ui/lib/living/widgets/living_composer.dart` (+37); see diff_stat_vs_canonical_cd4a7963.txt.
The earlier wording (line 146) correctly said "three files that the runtime-profiles plan counts in IC-1"; the refresh bullet dropped that qualifier. My review brief inherited the same wording.
Fix: say "three IC-1 files", and list all six modified existing files in the integration note.

**R4-03 INFO — evidence/gates/.**
`uibuild-release-final.log` and `brain_quick_controls_test-final.log` are R3 leftovers (`HEAD=d65b122c`) sitting next to the 76088dad gate logs. The 76088dad logs have no in-log HEAD line; only the .head sidecars name it. Fix: move the R3 logs to a subfolder or rename them.

**R4-04 INFO — ws_brain_host.py `sync_selection`.**
`selection_error: PROFILE_NOT_SELECTABLE` is recorded only in the host report. Neither worker `controls` nor the UI reads it, so the user sees only a generic not-ready/foreign state. Optional: surface it in `controls.cannot_switch_reason` or `host_profile` (ties in with R4-01).

**R4-05 INFO — oi_conversation.dart `brainSwitchRefusal` and the host's profile refusal path.**
A host-side `REFUSED_PROFILE_*` code is recorded in `last_request` only, not in `profile_switch`, and has no plain-words mapping. The UI would therefore show no notice. This is unreachable today: the worker applies the identical `QC.switch_target` first. Note it for any future divergence between the worker and the host.
