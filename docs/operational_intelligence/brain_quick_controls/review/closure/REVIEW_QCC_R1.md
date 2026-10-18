# REVIEW QCC-R1 — BRAIN-QC-CLOSURE-20261018 (code review before live verification)

Nonce: **QCC-R1-8b2e47**

- Reviewer: independent read-only subagent (did not write this work). Verification class: subagent code review; no live run.
- Target: detached worktree `D:\uri-dev\qcc-r1-review`, `git rev-parse HEAD` = `cde75580ad72b0b46a258241833851fb5935732f` (verified).
- Diff reviewed: `4e827178..cde75580` (12 files, +467/-29). `scripts/ws_brain_host.py`, `runtime_profiles.py`, `runtime_profile_selection.py`, `runtime_v1.py` are NOT in the diff (verified with `git diff --stat`); I read them as context.

## Worktree state

- Before: `git status --porcelain --ignored` empty.
- After pytest: still empty.
- After `flutter test`: tracked files unchanged, HEAD unchanged; new **ignored** entries only:
  `uri_ui/.dart_tool/`, `uri_ui/.flutter-plugins-dependencies`, `uri_ui/android/app/src/main/java/`,
  `uri_ui/android/local.properties`, `uri_ui/build/`, `uri_ui/windows/flutter/ephemeral/`.
- Nothing modified, added, committed, stashed or checked out. No GPU, Brain host, worker, server, app or harness process started; no lease file touched.

## Tests run (read-only)

- `runtime-e\.venv python -B -m pytest -c scripts/phase2d_pytest.ini --rootdir=. -q -p no:cacheprovider tests/oi/test_brain_quick_controls.py tests/oi/test_runtime_profile_selection.py` → **76 passed** in 10.83 s (COMPLETED_WITH_RESULT).
- `flutter test test/living/brain_quick_controls_test.dart` (in uri_ui) → **+25 All tests passed** (COMPLETED_WITH_RESULT).

## Acceptance criteria (defined before review)

- AC-1 Only frozen, P2, P3 are switch targets; P1 (65536,"gpu",False) is never selectable or shown as qualified through any normal control (worker, host, UI).
- AC-2 Brain host still refuses non-catalog/unqualified reconfigure targets and never writes a selection for a non-SELECTABLE profile (R9-01 fix 4c61a0b3 intact).
- AC-3 Worker fail-closed preserved (FOREIGN_INSTANCE for unfollowed host profiles; `active` only after worker verification).
- AC-4 UI / host / worker / persisted selection never disagree silently (R9-01 / QC-F9); no false positives during a known switch, none when the host is dead.
- AC-5 Assist: no reload under a running Assist answer; vision kept while an Assist session is held; Assist-state read is thread-safe and never breaks status.
- AC-6 UI truthfulness: loading/switching/readiness/failure/refusal text matches reality.
- AC-7 Frozen default unchanged; MTP optional; no speculative runtime changes; frozen UI V2 file `oi_conversation.dart` change purely additive.
- AC-8 Tests cover the new behaviour meaningfully.
- AC-9 Live harness checks would actually prove what they claim and cannot pass vacuously.

## Verdict

**REVISE** — one MEDIUM (harness vacuity, QCC-R1-01) blocks under the "HIGH/MEDIUM blocks" rule. The product code meets AC-1..AC-4 and AC-7; AC-5/AC-6 have LOW findings; AC-9 fails on QCC-R1-01.

## Criteria results

| AC | Result | Evidence |
|---|---|---|
| AC-1 | MET | `brain_quick_controls.py:45-49` P1 `qualified: False`; `switch_target` raises `PROFILE_NOT_QUALIFIED` (`:99-100`); offered set == `PS.SELECTABLE` (test `test_catalog_agrees_with_the_integrated_selectable_set`); `describe_key(P1)` reports `qualified: False`; `mismatch()` carries `host_qualified` from the catalog, so a host on P1 is described as "not a qualified choice" (`brain_quick_controls.dart:191-193`). UI `_firstQualified` uses `switchable` (qualified AND offered). Catalog order keeps Standard ahead of P3, so Vision/Context menus never resolve to P3 (Dart test asserts it). |
| AC-2 | MET | `ws_brain_host.py:157-169` reconfigure validated by `QC.switch_target` → `REFUSED_*`, nothing stopped; `sync_selection` `:416-437` unlinks the file and sets `selection_error=PROFILE_NOT_SELECTABLE` for non-SELECTABLE `--profile`. Unchanged by this diff. P3 is now accepted by the host's `switch_target` and is in `PS.SELECTABLE`, so a P3 switch writes a selection the worker follows. |
| AC-3 | MET | `controls()` `serving` still requires host profile == configured key (`:166-171`); test asserts `active is None` with a P1 host. `ProfileFollower`/`select_bytes` unchanged. |
| AC-4 | MET (LOW wording issue QCC-R1-05) | `mismatch()` `:139-155`: host dead → None (UI shows `BRAIN_HOST_NOT_RUNNING` via `cannot_switch_reason`); host report without `profile` → treated as frozen (correct for pre-profile hosts; current host always writes `profile`, `ws_brain_host.py:87,450`); pending switch → suppressed (`:182`, UI `pending ? null`); unreadable profile → `HOST_PROFILE_UNREADABLE`. Transient: `_brain_health` calls `self._status()` (selection refresh) before reading the host report, and the host writes selection + report together in `apply_pending_profile` while this worker's gate is still pending, so no false positive for this worker's own switches. A switch requested by some other writer can show a one-poll mismatch (acceptable, it is a real transient disagreement). |
| AC-5 | PARTIAL (LOW QCC-R1-02, QCC-R1-04) | Guard `worker_bridge.py:703-708`: `ASSIST_ASK_IN_PROGRESS` blocks every switch while an ask runs; `ASSIST_NEEDS_VISION` blocks vision-on→off while granted; vision-keeping switches (Standard↔P3) allowed (matches test and docstring). Thread-safety: lambda (`run_uri_integrated_worker.py:251-252`) reads `assist.asking` (takes `AssistCommands._lock`) then `access.snapshot()` (takes `AccessController` RLock) sequentially, never nested → no lock-order inversion with the ask thread (which nests access lock → `_lock`). The two reads are not atomic together (benign: the command loop is sequential and both are advisory). `_assist()` swallows exceptions → None (status never breaks; test covers). Gaps: PAUSED grant not treated as held (02); no reverse guard (04). |
| AC-6 | PARTIAL (LOW QCC-R1-03, QCC-R1-05) | Draft chip shown only when two switchable profiles differ only in MTP at the verified active ctx/vision; hidden when `active` is null or 64K (correct; no false "Draft: Off"). Refusal strings added. Lock reason text untruthful in the product (03). |
| AC-7 | MET | No change to runtime_profiles / runtime_v1 / ws_brain_host / selection; frozen remains first catalog entry and default. `oi_conversation.dart` diff = 2 added switch arms before the `_` default (`+2/-0`), purely additive. `RUNTIME-PROFILES-INTEG.json` change is one wording line (adds c3fc8bbc/sw6 as accepted binding). |
| AC-8 | MET with gaps (LOW QCC-R1-06) | New Python tests: P3 target, mismatch agree/disagree/unreadable/dead/pending, controls carry lock+mismatch, Assist guard both codes, assist failure, wiring order. Dart: draftChoices from Standard/P3/64K/null, lockVision, Draft chip widget flow, no chip on 64K, mismatch shown/cleared, refusal strings. |
| AC-9 | NOT MET (MEDIUM QCC-R1-01; LOW QCC-R1-03b/07) | See findings. |

## Findings

### QCC-R1-01 — MEDIUM — closure live steps can be skipped silently (vacuous pass)
- File: `docs/operational_intelligence/brain_quick_controls/evidence/harness/qc_driver.dart:334`; `go.sh` (whole); `run_qc_ui.py:48-58,63-68`; `summarize.py`.
- Evidence: the P3/Draft, Assist-on-P3 and back-to-Standard steps run only `if (Platform.environment['URI_QC_CLOSURE'] == '1')`. `go.sh` never sets it, `run_qc_ui.py` neither sets nor records it in the run record, and `summarize.py` has no list of required check IDs (grep finds no `QC-` / required-check handling). A run started without the variable records no closure checks and no failures, so its `failures` list is empty and it looks like a passing QC run. The owner requirement "P2 and P3 operate through the UI" and the Assist-on-P3 claim would then rest on absent evidence.
- Repair: add a `closure` kind to `go.sh` (or a flag) that exports `URI_QC_CLOSURE=1`; record the flag (and the driver's closure check list) in the `run_qc_ui.py` record; make the summary/acceptance require every closure check ID (`QC-draft-chip-standard`, `QC-confirm-dialog-p3`, `QC-header-truthful-p3`, `QC-truthful-switch-p3`, `QC-chips-p3`, `QC-no-mismatch-p3`, `QC-continuity-p3`, `QC-assist-vision-on-p3`, `QC-chips-standard-after-p3`, `QC-continuity-standard-after-p3`) to be present with PASS; a missing ID = FAIL.

### QCC-R1-02 — LOW — a PAUSED Assist grant does not keep vision on
- File: `scripts/run_uri_integrated_worker.py:252`; `worker_bridge.py:707`; `brain_quick_controls.py:186`.
- Evidence: `granted = snapshot()["state"] == "ACTIVE"`. `AccessController.pause()` (`uri_assist/access.py:147-153`) keeps the grant with state `PAUSED`; `resume()` restores it. While paused, the worker allows a switch to Long context (vision off) and the UI does not lock; after Resume the Assist session runs on a Brain without the projector. The code's own docstrings say "while Assist holds a grant", which a paused grant still is; the owner requirement says "during an active Assist session". Product impact is currently nil because the product's VisionGate is unqualified (see 03), hence LOW.
- Repair: `granted = state != "OFF"` (ACTIVE or PAUSED), or expose `held` and `active` separately; add a test with a PAUSED grant.

### QCC-R1-03 — LOW — lock / refusal text says "URI Assist is using vision" while product Assist vision is disabled
- File: `uri_ui/lib/living/integration/brain_quick_controls.dart:179`; `oi_conversation.dart` `ASSIST_NEEDS_VISION` arm; `run_uri_integrated_worker.py:248-249`.
- Evidence: the worker builds `ASSIST.AssistCommands(...)` without `vision_qualified`, so `VisionGate.qualified=False` and every screenshot ask is refused `VISION_NOT_QUALIFIED` (`uri_assist/vision.py:109-110`; status "NOT VERIFIED (disabled until PC qualification)"). With any grant the user is blocked from Long context with the stated reason "URI Assist is using vision", which is not true in the product. The conservative block itself follows the owner rule; only the reason is untruthful.
  - 03b (harness): `qc_session.py:78` calls the Assist step the "application path", but it is a separate `AssistCommands` instance in the session process with `vision_qualified=True` and a FakeAdapter. It proves "production Assist vision code gets a correct answer from the P3 Brain"; it does not exercise the worker's Assist guard, `vision_locked`, or the UI lock live. The stand-ins are disclosed in `stand_ins`; the wording should not imply the app path.
- Repair: reword to "URI Assist has an open session that may need vision. End it first." (or condition the wording on `vision.status()`); in the harness, change "application path" to "production Assist classes, session process" and state that the guard/lock are unit-test-only evidence.

### QCC-R1-04 — LOW — no reverse guard: Assist can start during a pending switch
- File: `uri_assist/bridge.py:213-250` (unchanged), worker wiring.
- Evidence: the guard prevents a reload under a running ask, but an `assist_ask` or `assist_grant` accepted while a switch is pending (Brain reloading, or loading the vision-off P2) is not refused; the ask then fails (`FAILED`) or a grant is held on a vision-off Brain. Truthful (no silent success), so LOW; "avoid reloads during Assist" is otherwise met.
- Repair (optional): pass `brain_idle=lambda: not oi.busy and not oi._restart_pending()` or refuse `assist_ask` with `BRAIN_RESTARTING` while a switch is pending.

### QCC-R1-05 — LOW — mismatch notice wording wrong in two branches
- File: `brain_quick_controls.py:146-148,151`; `brain_quick_controls.dart:187-197`.
- Evidence: (a) when keys agree but the host reports a non-`PROFILE_NOT_SELECTABLE` `selection_error` (e.g. `PermissionError` from `sync_selection`'s `except OSError`), the code is that error, `host_qualified=True`, and the UI says "The Brain host runs Standard but URI expects Standard. URI does not use it until they match", which is false (the worker does use it; `active` is set). (b) `HOST_PROFILE_UNREADABLE` puts the raw profile id in `worker` (other branch uses the label), so the UI shows e.g. "URI expects frozen".
- Repair: in `mismatch()`, when `hkey == configured` and only a selection error exists, return a distinct code (e.g. `HOST_SELECTION_WRITE_FAILED`) and give the UI a matching sentence; use `describe_key(configured_key)["label"]` in the unreadable branch. Add tests.

### QCC-R1-06 — LOW — test gaps
- `test_worker_wires_assist_state_after_assist_is_created` is a source-text check; nothing runs the lambda against a real `AssistCommands` (state names ACTIVE/PAUSED/OFF, `asking`). No Python test for a PAUSED or expired grant; no Dart test for `lockVision` with `active == null` (choices then stay enabled and the worker refusal is the only guard: acceptable, but untested) or with active vision off; no test for the selection-error-only mismatch (05a).
- Repair: one test building a real `AssistCommands` + `AccessController` with a fake clock (grant → ACTIVE lock, pause, expiry) feeding `IntegratedTurns.assist_state`; the Dart cases above.

### QCC-R1-07 — LOW — harness Assist check is weak and loads Assist code from the dev checkout
- File: `qc_session.py:85-89,114`.
- Evidence: (a) `toggles_ok` requires only that "voice" and "gmail" appear; an answer naming all four toggles as on also passes. `mentions_401` with empty DOM text (`text=""`) does show the image was read, so the check is not vacuous on vision itself. (b) `uri_assist`, `uri_web`, `tests.assist`, `lab` are imported from the receipt's `candidate_source` (`D:\uri-dev\uri-brain-qc-closure`, a dev worktree that may be dirty), inserted ahead of `RT`, while `uri_operational_intelligence` is already loaded from `RT`; the Assist code tested is therefore not bound to the materialized runtime. `runtime5` has its own `uri_assist/`, `tests/`, `model_lab/`.
- Repair: record `git rev-parse HEAD` + porcelain of `candidate_source` in `assist-result.json`, or import from `RT` only; add a negative check ("dark"/"backup" not called on) or record it.

## Points checked with no finding

- P1 never selectable/qualified (AC-1); host R9-01 behaviour unchanged (AC-2).
- `draftChoices` with active unknown → empty; with 64K → empty (only one switchable 64K/vision-off profile); key `qc-draft-On/Off` from `_profileChip` title (driver keys match).
- `lockVision` when active vision off → unchanged (correct: nothing to lose); duplicate menu keys impossible (titles preserved).
- From P3: Vision Off and 64K resolve to P2; 64K-with-vision shows P1 blocked with its reason; back to 32K resolves to Standard (draft on again; note says so).
- Assist-state exceptions (e.g., `assist` rebound to None) → `_assist()` returns None, status unaffected.
- `oi_conversation.dart` change additive; `RUNTIME-PROFILES-INTEG.json` wording-only.
- Driver P3 checks: header/active-early timeline checks are conservative (DEGRADED counts as "early", may false-FAIL, never false-PASS); missing `assist-result.json` → `{}` → FAIL.

## Self-review and re-check

- Draft 1 rated QCC-R1-02 MEDIUM; re-checked that product Assist vision is disabled (`vision_qualified` default False, worker passes none), so the paused-grant gap has no product effect today → LOW. Draft 1 considered the lock text MEDIUM; kept LOW because the block is the owner's conservative rule and only the reason wording is wrong.
- Re-checked QCC-R1-01 is not already handled: no `URI_QC_CLOSURE` in `go.sh`/`run_qc_ui.py`; no required-check list in `summarize.py` (grep). Kept MEDIUM.
- Re-checked AC-4 transient claim against `_brain_health` order (`self._status()` before `self._host()`) and `apply_pending_profile` (selection + report written while the request is still pending).
- Lock-order claim re-checked against `uri_assist/bridge.py` (`asking`, `_start.run`) and `access.py` (`snapshot`, `held`).

## Unverified

- No live behaviour verified (by design: pre-live round). Whether P2/P3 switches, continuity and Assist-on-P3 pass live is open; affects closure, not this code verdict.
- `summarize.py` read only by grep for required-check handling, not line by line.
- `RP.profile_id(P3) == "c32k-visgpu-mtpoff"` inferred from the existing P1 test id format, not executed separately.
- Earlier R1-R4 reports for 4e827178 were not re-audited; base behaviour outside the diff was read only where the diff depends on it.
