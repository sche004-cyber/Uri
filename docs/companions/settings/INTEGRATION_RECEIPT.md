# Companion visual, voice and settings: canonical integration receipt

Date: 2026-10-09. Mandate: owner brief "URI — Companion Visual, Voice & Settings
Completion", which authorises integration into the canonical development
branch after independent acceptance and combined regression gates, and does
not authorise production deployment, launcher changes, replacing the live URI
server or cutover. None of those was done.

## 1. Commits

| Role | Commit |
|---|---|
| Canonical development branch before integration | `integration/git-sync-20261008` on `github.com/sche004-cyber/Uri` = `71606148f89b3efb8ee7fb9bc1864d0132266ed0` (the working-system canonical receipt; verified with `git ls-remote` immediately before the push) |
| Source branch | `phase/companion-voice` (local) = `c0fc8b90df78c21f8b61b39b7ba302fe5e856132` |
| Source as accepted by Codex round 4 | `417cd26245eadb067fd7647b49ddff5f763a7eda` |
| Merge of the accepted source | `ab8f8227fae5e2d10a44de1630bcae723c52b173` (automatic, no conflicts; merge base `569cf7c`) |
| Integration wiring | `ed8a6559094fbf0c1874b927c89a00d53108fbbc` (working-system entry: voice catalog and minimise binding through an optional `configureServices` hook) |
| Merge of the integration-review repair | `6f06c3128c17222684774f5d172fb275b9c16723` (source `c0fc8b9`) |
| Integration branch | `integration/companion-settings-20261009` (worktree `C:\Users\cheta\Development\uri-companion-integ`) |
| Destination after this receipt | the commit that adds this file (docs only, child of `6f06c31`), pushed as a fast-forward of `integration/git-sync-20261008` |

## 2. Independent review (Codex CLI, gpt-6-sol, reasoning medium, read-only)

| Round | Reviewed | Verdict | Outcome |
|---|---|---|---|
| 1 | `a978cf5` | REJECT (2 blocking, 2 non-blocking) | repaired in `ebe3828` |
| 2 | `f73575d` | REJECT (2 blocking, 4 non-blocking) | repaired in `cecb911` |
| 3 | `a83efe7` | ACCEPT WITH FINDINGS (3 non-blocking) | repaired in `417cd26` |
| 4 | `417cd26` | **ACCEPT** for `037229c..417cd26` | — |
| Integration 1 | `ed8a655` (merge onto `7160614` + wiring) | ACCEPT WITH FINDINGS (1 non-blocking: window binding race) | repaired in `c0fc8b9`, merged as `6f06c31` |
| Integration 2 | `6f06c31` | **ACCEPT WITH FINDINGS** for the fast-forward | finding: the new test covers the no-plugin path and idempotent cleanup but does not simulate disposal during initialisation or a failing `isMinimized()`; recorded as a known limitation (§6) |

Codex found that both parents' behaviour is preserved in the auto-merged files
(`living_app.dart`, `living_scope.dart`, `workspace_mode_view.dart`,
`dashboard_mode_view.dart`): the working-system conversation, settings
section, context panel and Brain tile remain alongside the companion
additions.

## 3. Gates on the integrated tree (`6f06c31`, run unsandboxed by the candidate)

| Gate | Result | Evidence |
|---|---|---|
| `flutter test` (all of `uri_ui`) | **427 passed, 3 skipped** (canonical alone: 313 passed, 3 skipped; this line adds 114) | `integration/flutter_full.txt` |
| `flutter analyze` on every changed Dart path plus `test/ws` | no issues | `integration/flutter_analyze.txt` |
| `scripts/ws_frozen_check.py` | ok: 121/121 Phase 1 checkpoint files byte-identical; no protected path changed against `037229c` | `integration/ws_frozen_check.json` |
| `pytest tests/oi tests/ws` (OI and working-system Python) | **226 passed, 20 skipped**, identical to the canonical receipt | `integration/pytest_oi_ws.txt` |
| Python chain (phase2, authority, phase1-full, phase1-scope) | not re-run: the gate tree is materialised from `e8e3b65` plus the listed overlay and OI/WS paths (`scripts/oi_materialize_test_runtime.py`), none of which this integration changes; the canonical receipt's ALL_PASS therefore applies unchanged | `docs/working_system/canonical_integration/` |
| `git fsck --no-dangling` | clean | — |

## 4. Boundary verification

* `git diff --name-only 7160614 6f06c31`: 936 paths, all under `uri_ui/`
  (51), `docs/` (851) and `rnd/` (34). Nothing under `uri_core/`,
  `uri_supervisor*/`, `uri_harness_adapters/`, `model_lab/`, `scripts/`, the
  root `.gitignore` or any launcher.
* No protected path of `scripts/ws_frozen_check.py` changed; no Phase 1 frozen
  file drifted.
* Line endings: every text file this phase added or changed is LF. 21 files
  from earlier, never-normalised phases are CRLF and one is mixed: 15 sampler
  CSVs and `matrix_log.txt` (mixed) under `docs/companions/voice/evidence/perf/`
  (voice phase), the two voice timing fixtures
  `uri_ui/test/fixtures/voice/*.timing.json` (voice phase; the tests read them
  as JSON), and `docs/orb_solar/evidence/shaders_v2.js`,
  `rnd/orb_solar/{app.js,index.html,shaders.js}` (solar R&D). They are kept
  byte-unchanged rather than rewritten during integration.
* No secret pattern was added; absolute paths in the documents are local
  development paths only.

## 5. What the integration contains

The companion line from `569cf7c` on: solar orb R&D (`07a2f38`), the living
companions Solar, Sakura, Lunar and Moonlit Blossom (`bd542f2`, `d7a052f`),
the voice presence and state system (`4c463e6`, `8fad876`), and this phase:
the companion everywhere, companion-driven theme, Companion Settings,
preferences, frame clock and adaptive governor, render quality, minimise
suspension, voice catalog and previews, voice service interface, the voice
stage beside the companion, and their evidence. The working-system entry now
installs the voice catalog and the minimise binding.

**Behaviour change in the working-system app:** the default companion is
Solar (its theme follows), where it was the classic Energy Orb; the classic
orb remains selectable in Settings with its styles, palettes and free theme.

## 6. Known limitations carried into canonical

1. No live voice: no microphone capture, recognition or URI speech exists on
   canonical; the voice frames in the evidence are a scripted recording
   labelled SIMULATED.
2. Start order: opening a URI window after Runtime v1 has loaded left the
   Brain at about a third of its speed until it restarted (one controlled run;
   VRAM demotion inferred, not measured). Owner decision, outside this phase.
3. Adaptive back-off verified by tests, not yet against a sustained live
   Brain load.
4. Native memory grows slowly in every Flutter window on this machine,
   including a no-companion control; no plateau shown within 30 minutes.
5. Windows only; one GPU; device pixel ratio 1.0.
6. The window-binding test does not simulate disposal during initialisation
   or a failing `isMinimized()` (Codex integration round 2).
7. Covered (not minimised) windows still render.
8. Production deployment, the live `\URIServer` task, launchers and cutover
   are untouched and remain owner-authorised steps.
