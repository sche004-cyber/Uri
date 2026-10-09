# Live voice: canonical integration receipt

Date: 2026-10-09. Mandate: owner brief "URI — Live Voice Integration, Brain Coexistence & Companion Activation",
which authorises integration into the canonical development branch after independent acceptance and combined gates,
and does not authorise production deployment, launcher or server cutover. None of those was done.

## 1. Commits

| Role | Commit |
|---|---|
| Canonical before integration | `integration/git-sync-20261008` on `github.com/sche004-cyber/Uri` = `1587449` (A2UI integrated at `dc1ce81` + ledger update; fetched before the merge) |
| Phase branch base | `b02ed4f` (canonical when the phase started) |
| Source (accepted) | `phase/live-voice` = `d7081c5` (Codex live-voice round 4 ACCEPT WITH FINDINGS on `3ea5350`; R4 repairs in `d7081c5`) |
| Merge | `3b88c67` (automatic; no conflicts; one shared file, `uri_ui/lib/living/living_scope.dart`, keeps A2UI's hub field and the live-voice members side by side) |
| Integration branch | `integration/live-voice-20261009` (worktree `C:\Users\cheta\Development\uri-voice-integ`) |
| Destination | the commit that adds this receipt, pushed as a fast-forward of `integration/git-sync-20261008` |

The phase branch's unpushed history was rewritten before integration to keep raw microphone recordings out of the
repository (privacy; `LIVE_VOICE_AUDIT.md`, "History rewrite"). No commit reachable from the integration branch
contains audio recordings of the room.

## 2. Scope of the change

`git diff --name-only 1587449 3b88c67`: only `uri_ui/`, `docs/` and `rnd/`. No file under `uri_core/`,
`uri_supervisor*/`, `uri_operational_intelligence/`, `uri_scheduler/`, `uri_a2ui/`, `scripts/`, `model_lab/`, `tests/`, the
root `.gitignore` or any launcher. New runtime asset: `uri_ui/assets/voice/uri_voice_service.py` (runs from the
installed app's asset folder with a provisioned interpreter); changed asset: `voice_engine.ps1` (new `serve` verb;
`list`/`speak`/`render` unchanged). New dev dependency: `integration_test` (Flutter SDK package; lockfile additions only,
resolved offline).

## 3. Gates on the integrated tree (`3b88c67`)

| Gate | Result | Evidence (`docs/voice/live/integration/`) |
|---|---|---|
| `flutter test` (all of `uri_ui`) | **482 passed, 4 skipped** (canonical alone per the A2UI receipt: 444 passed, 4 skipped; this line adds 38) | `flutter_test_all.log` |
| `flutter analyze lib test integration_test` | 2 infos, both in files this integration does not change | `flutter_analyze.log` |
| voice service tests (voice runtime) | 29 passed | `pytest_voice_service.log` |
| `scripts/ws_frozen_check.py` | ok: 121/121 Phase 1 checkpoint files byte-identical; no protected path changed | `ws_frozen_check.json` |
| `pytest tests/a2ui tests/scheduler tests/oi tests/ws` | 403 passed, 20 skipped, **1 failed** (canonical receipt: 404 passed, 20 skipped). The failure, `test_task_ctl.py::test_rollback_dry_run_only_targets_this_scheduler_service`, reproduces identically on canonical `1587449` alone with the same interpreter: the test compares the scheduler's pid with `Popen.pid`, and this virtual environment's `python.exe` is a launcher whose child is the real service. No Python file is changed by this integration | `pytest_a2ui_scheduler_oi_ws.log` |
| Python chain (phase2, authority, phase1-full, phase1-scope) | not re-run: the gate tree is materialised from `e8e3b65` plus the overlay and the OI/WS/scheduler/A2UI paths, none of which this integration changes; the canonical A2UI receipt's ALL_PASS applies unchanged | `docs/a2ui/canonical_integration/` |
| Live start-up of the integrated app | the integrated tree was materialised (`uri-voice-integ-rt`, candidate head `3b88c67`), provisioned and its server started; the app opened with the integrated worker, the voice service reported ready (model loaded in 499 ms, `Microphone (Sennheiser Profile)`, privacy allowed); Brain stopped by design | `live_startup.log`, `live_startup/` |

## 4. Independent review

Phase: Codex rounds 1-3 REJECT (all findings repaired with tests that fail before the repair), round 4 ACCEPT WITH
FINDINGS (repaired). Integration review: section 6.

## 5. Behaviour change after integration

The working-system app (Windows) now starts the voice process three seconds after launch (CPU only; about 160 MB),
shows a microphone button beside the send button in Companion mode and the Workspace, and gains "Voice input" settings
(microphone, mode, words to recognise, speak replies). The voice runtime must be provisioned once
(`uri_ui/tool/voice/provision_voice_env.ps1`); without it the button says so and nothing else changes.

## 6. Integration review (Codex)

(recorded after the review)

## 7. Known limitations carried into canonical

See `LIVE_VOICE_REPORT.md` section 8: no human-talker run; drafting by voice waits for the TI draft desk; short commands
with the assistant's name sometimes misheard; OI's error state outranks listening on the orb; the Runtime v1 start-order
demotion is measured but not solved; English only; noise-guard thresholds from a synthetic-voice sample; run 5's
start-up failure unexplained; no live run after the final repairs; the orb shows `speaking` while text streams.
