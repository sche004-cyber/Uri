# UI-CONTROLS-TYPO-20261018 - Interactive Controls & Typography Refinement: implementation report

Branch `milestone/ui-controls-typography-20261018`, worktree `D:\uri-dev\uri-ui-controls-typo`, cut from canonical
`feaabe3f`, merged with canonical `ec2fab54` (Brain QC closure) at `a4935c2b`. Local only: not pushed, not integrated.
The acceptance criteria were written first: `00_ACCEPTANCE_CRITERIA.md` (unchanged since). Conventions for future work:
`docs/ui/UIdevelopment.md`.

Status words: MET = shown by COMPLETED_WITH_RESULT evidence named in the row. PENDING = evidence not produced yet.

## 1. What changed

### 1.1 Push-to-enable Brain controls (`uri_ui/lib/living/integration/qc_toggle.dart`, `brain_quick_controls.dart`)
- New reusable widgets: `QcToggle` (on/off) and `QcSegmented` (one-of-many), states `off / on / loading / error`,
  plus hover, pressed and disabled-with-reason. Enabled = `accentSoft` fill, accent border, one static accent
  `BoxShadow` (the glow); no looping animation, a 140 ms transition on state change only.
- **Thinking** = toggle. Click: On (thinks first, glow) <-> Off (answers directly). The default **Auto** stays one
  menu choice away (caret `qc-thinking-menu`, with "Last answer: ..."). Justification: Auto is not "disabled" (URI
  may still think), so it cannot be the off state of a glow toggle; keeping it as the default and in the menu keeps
  the accepted three-way semantics without a hidden mode. Per message, nothing reloads.
- **Vision** = toggle, glowing only when the worker-verified `controls.active` has vision on. A click picks the
  qualified profile with the opposite vision (`toggleChoice` over `visionChoices`, after the closure's `lockVision`);
  because the catalog couples vision and context, the tooltip and the confirmation state the coupled change
  (Vision off => Long context 64K; Vision on from 64K => Standard 32K, and why 64K + vision is not offered: CRASH-1,
  DEMOTE-P1). Disabled with the reason while an Assist session holds vision (`vision_locked`).
- **Context** = selection (32K | 64K segments). The selected segment glows only when it is the verified active
  context. The unqualified 64K + vision is explained in the 64K segment's tooltip, never offered.
- **Draft** (closure ec2fab54) = toggle, shown only where `draftChoices` finds a qualified pair (On = Standard,
  Off = Standard, draft off / P3, vision and context kept).
- While a switch runs, Vision / Draft / Context show the loading state (spinner, no glow, not clickable) and the
  `qc-switching` pill says "Switching to ..." or, during an automatic restore, "Did not start; going back to ...".
- Notice tone: ok (soft ink), warning (refusals, waiting, restored), error (no Brain serving after the switch); the
  reload controls show the error look only when no Brain is verified. The closure's `qc-mismatch` line is kept.
- Keys kept: `qc-thinking`, `qc-vision`, `qc-context`, `qc-draft`, `qc-mismatch`, `qc-notice`, `qc-switching`,
  `qc-context-32K/64K`, `qc-confirm-switch(-go)`, `qc-thinking-<Auto|On|Off>`; new: `qc-thinking-menu`,
  `qc-confirm-changes`. Behaviour change for drivers: one tap acts (no menu) for Vision / Draft / Context segments.

### 1.2 Brain switch confirmation (`QcSwitchDialog`)
Before: `REFERENCE_confirm_dialog_before.png` (full window width, four paragraphs of equal weight, "Switch" button).
After: max 460 px content width; title (17/600); one-line summary; a "what changes" block (Vision / Context / Draft /
GPU memory, from -> to, unchanged values marked); blocked reasons; three facts with icons (reload time,
conversation kept, what happens on failure: automatic restore when a qualified Brain is running, otherwise "URI says
so"); Cancel (text button) and **Switch Brain** (filled, icon).

### 1.3 Restore after a failed switch (closes QC-F5) - `scripts/ws_brain_host.py`, `worker_bridge.py`, `brain_quick_controls.py`
- When the new profile's start ends FAILED (RuntimeManager's accepted 300 s load bound, or a rejected start), the
  host starts the previous profile **once**, on the lease it still holds, only if the previous profile was running on
  this host (known good) and is a qualified catalog entry (Standard, Long context, Standard draft off). Never for a
  Brain the user had stopped, never to a research profile (P1), never after a stop/exit, and a newer reconfigure
  request supersedes it. Nothing else is stopped; the fit pre-check before the stop is unchanged.
- Recorded truthfully: `profile_switch.result` stays `FAILED`; `profile_switch.fallback = {to, label, result,
  after, seconds}`; `restored` true only for READY / DEGRADED. The selection file, the lease's expected VRAM and the
  report's `profile` follow the restored profile, so the worker verifies against it again.
- The worker's gate stays closed until the host finishes the whole request (switch + restore), so turns wait; its
  health explanation says "did not start with X. URI is going back to Y" while the restore runs.
- ec2fab54 did not change the failure path (`ws_brain_host.py` unchanged by the closure; QC-F5 was carried over),
  so this is the only restore logic; it respects the closure's restrictions (no reload under an Assist answer is
  enforced before the request; the restore goes back to the profile that was running, which keeps vision whenever it
  had it).

### 1.4 Typography (`uri_ui/lib/theme/uri_theme.dart` + 43 files)
- Investigation (`evidence/typography_counts_before.json`, at `feaabe3f`): 334 numeric `fontSize` literals with 24
  distinct values (7.4 ... 48) in 46 files; family literals Segoe UI x2, Georgia x2 (login wordmark, Frost greeting),
  Consolas x2. The theme set `fontFamily: 'Segoe UI'` on `ThemeData`, but `textTheme.copyWith` replaced 8 roles with
  bare `TextStyle`s, which silently dropped the family (the engine default happened to be Segoe UI on Windows, so the
  family was right by accident, not by design).
- Decision: **Segoe UI** for all UI text, **Consolas** for code - both Windows system fonts (no package, no font file,
  no licence question). Segoe UI Variable was not chosen: absent on Windows 10 and it changes metrics app-wide.
- `UriType`: one scale of 12 steps (10, 11, 12, 13, 14, 15, 17, 20, 24, 28, 34, 48). All 15 TextTheme roles are
  defined on it and the family is applied to all of them; button text styles carry the family too.
- Migration (`evidence/tools/typo_migrate.py`): every numeric literal in `uri_ui/lib` replaced by a `UriType` token;
  half steps rounded up (12.5 -> 13, 13.5 -> 14, 11.5 -> 12 ...), others to the nearest step. Georgia replaced by
  Segoe UI (Light 300 for the wordmark and the greeting). Default body text (`bodyMedium`) moves 13.5 -> 14.
- After (`evidence/typography_counts_after.json`): 0 numeric literals and 0 family literals outside the exceptions;
  the whole tree still has 18 literals with 9 values, all in the two documented exceptions: the frozen classic
  dashboard board (`reference_dashboard.dart`, pixel-transcribed 1024x682 board units, "never hand-edit") and the
  protected `settings_shell.dart` (ws_frozen_check PROTECTED).
- Guard: `test/living/ui_controls_typography_test.dart` fails on a new numeric `fontSize`, any `fontFamily` string
  literal or Georgia, and checks every theme role's family and size for four palettes.

## 2. Files
- Ember-integration files (`lib/living/companion/*`, `oi_sources.dart`, `living_app.dart`, `companion_gallery.dart`):
  **none touched** (they had no font literals).
- Frozen / protected: none touched (`ws_frozen_check` ok). Runtime v1 config, `runtime_profiles.py`,
  `runtime_profile_selection.py`, `runtime_v1.py`: unchanged.
- `oi_conversation.dart` (frozen UI V2 file): unchanged by this milestone (the closure's +2 strings come from ec2fab54).

## 3. Live Windows verification (production `main()`, real worker, Core, Brain host, lease; no override)

Runtime `D:\uri-dev\uri-ui-typo-live\runtime`, materialized from `a4935c2b` (Python identical at `22b53b78`; later
commits change Dart / docs only), Core port 18350. Qwen3.6-35B-A3B MoE only. Automation input (flutter_test taps,
synthesized mouse hover, TestTextInput), not physical keyboard/mouse. Harness: `evidence/live_harness/` (copy of the
BRAIN-QC harness; `inject_host.py` runs the production host and fails the FIRST start of Long context inside a switch,
after the GPU fit / release wait and before any server is spawned; the running Brain is really stopped and really
started again by the candidate's restore code).

**Start profile:** the owner's desktop left too little GPU memory for Standard (fit CONTENDED -834 MiB: dwm 0.7 GB,
Chrome 0.4 GB, uri_ui 0.2 GB). Per the owner's instruction relayed by the main session ("try with no mtp and 32k context
size"), every run started the production host with `--profile 32768,gpu,0` (P3, Standard draft off; recorded in each
`session.json` `host_argv`).

| Run | Code | Result | Evidence |
|-----|------|--------|----------|
| ui-1 | `a4935c2b` | stopped by me after 15 checks. The restore worked live; 1 FAIL `UT-restored-notice` was a **driver defect** (`textOf` searched descendants of a key that sits on the Text itself; `05-restored-after-failed-start.png` shows the notice), and the driver waited for READY while Long context came up DEGRADED (slow, GPU short). Driver repaired; run kept as history. | `evidence/live/ui-1/` |
| **ui-2** | `22b53b78` | **30/30 PASS**, exit 0, end ui-finished | `evidence/live/ui-2/` |
| **uiv2-1** | `22b53b78` | **UI V2 journeys 68/68 PASS** (canonical driver unchanged, fresh prefs incl. onboarding) | `evidence/live/uiv2-1/` |

ui-2 journey and outcomes (from `live/ui-2/observations.json`, `samples.json`, `injection.json`):
- Start P3 verified: Vision glows, 32K selected, Draft subdued (off), Thinking Auto (`01-ready-controls.png`).
- Thinking click: On, glow, answer tier NORMAL; click again: Off, tier FAST (`02-thinking-on-glow.png`).
- Hover tooltip on Vision states the coupled change (`03-vision-hover-tooltip.png`).
- Vision click: confirmation (Vision On to Off, Context 32K to 64K, GPU 14.0 to 13.3 GB) (`04-confirm-vision-off-long.png`),
  injected failed start, host restore: `profile_switch` FAILED, `restored` true, `fallback` READY in 33.4 s; the pill
  read "Did not start; going back to Standard, draft off" while it ran; the notice "The Brain did not start with the
  new setting, so URI went back to Standard, draft off. Your conversation is kept."; Vision glows again only after
  verification (`05-restored-after-failed-start.png`).
- Context 64K segment: confirmation, real switch (loading look `07-switching-loading.png`), Long verified (DEGRADED:
  slow next to the owner's apps), recall "4817" correct (`08-long-ready.png`).
- Vision click at 64K: the confirmation lists "On at 64K: Not qualified yet ... (CRASH-1, DEMOTE-P1)"; the host refused
  BEFORE stopping anything (`REFUSED_DOES_NOT_FIT`: Standard needs 15.3 GB, 14.2 GB free); Long stays, Vision stays
  subdued, the notice explains (`09-confirm-vision-on-standard.png`, `10-after-vision-on.png`); recall correct.
- Glow honesty over every poll of every switch timeline: 0 violations (`UT-glow-honest-*`).
- Same worker and session throughout; no Flutter errors; typography tour `20..26-*.png` (Workspace conversation,
  tasks, intelligence/diagnostics, settings; Dashboard; Assist; Companion).
- Draft live switch: **not exercised** (Draft is offered only at 32K + vision; from Long the vision-on target is
  Standard, which did not fit). Draft is covered by widget tests here and by the closure's live qcc-1 (P3 via Draft).

## 4. Gates (final code `22b53b78`; later commits change docs only)
`evidence/gates_22b53b78/` (each log starts with HEAD and the tracked-file porcelain status, empty): pytest tests/oi +
tests/ws **805 passed, 23 skipped**; flutter test **799 passed** (5 skipped); flutter analyze **0 errors** (4
pre-existing infos in files this milestone did not touch; its exit 1 comes from the infos); Windows release build
**OK**; ws_frozen_check **ok**. The same gates at the merge `a4935c2b`: `evidence/gates_a4935c2b/` (same results).
Preliminary gates at `7bab14fe` were superseded and not kept.

## 5. Acceptance criteria status (`00_ACCEPTANCE_CRITERIA.md`)

| ID | Status | Evidence |
|----|--------|----------|
| A1 toggles | MET | widget tests; ui-2 UT-thinking-*, vision steps |
| A2 context selection | MET | `QcSegmented`; tests; ui-2 06/08 |
| A3 glow / subdued | MET | decoration tests; live screenshots in one theme (Solar Ember); 4 palettes in the theme test. Glow strengthened after the ui-1 review (`22b53b78`) |
| A4 states distinct | MET | widget test off/hover/pressed/on/disabled; loading and error tests; live loading 07 |
| A5 static glow | MET (code + test) | one BoxShadow; no frame scheduled when idle |
| A6 verified state only | MET | "never shown as current" tests; ui-2 glow honesty 0 violations |
| A7 confirm, indicator, glow after activation | MET | ui-2 04/06/07/09 |
| A8 conversation kept | MET | ui-2 recall after restore, Long and refusal; same worker/session |
| A9 restore after failure | MET | `tests/oi/test_ui_controls_switch_fallback.py` (12 tests: success, restore fails too, stop during load, stop during restore, restart during switch, no restore for a stopped Brain or a research profile, P3 restore, worker explanation, unchanged success path); live ui-2 |
| A10 Thinking semantics | MET | section 1.1; tests |
| A11 closure drop-in | MET (merged) | `a4935c2b`: Draft toggle, vision lock, mismatch line; tests |
| B1 one family | MET | `typography_counts_after.json`; typography test |
| B2 family on every role | MET | theme test (15 roles x 4 palettes) |
| B3 one scale | MET | 334 literals / 24 values to 0 outside 2 documented exceptions |
| B4 surfaces | MET (visual) | ui-2 20..26; uiv2-1 screenshots; `evidence/before_after/` pairs against the closure's qcc-uiv2 |
| B5 no font dependency | MET | pubspec unchanged by this milestone |
| C1 dialog | MET | `before/confirm_dialog_before_live_20261018.png` vs `live/ui-2/04, 06, 09`; width test |
| D1-D4 gates | MET | section 4 |
| D5 UI V2 journeys | MET | uiv2-1 68/68 |
| D6 live run | MET | ui-2 30/30 |
| D7 no performance regression | PARTIAL | by construction (no new animation, shader or font; one shadow per enabled control) and the idle-frame test; no before/after frame-time or memory measurement taken; Brain speed today is limited by the owner's desktop GPU use, so no speed number from these runs is attributable to this change |

## 6. Findings and limitations
- **F-1 (MEDIUM, product decision):** from Long context, Vision on and the 32K segment always target Standard
  (catalog order prefers the frozen default). When Standard does not fit but Standard draft off would (today's
  desktop), the switch is refused and the user cannot get vision back from the controls (Restart Brain restarts
  Long). A fix changes the accepted catalog resolution (e.g. prefer a fitting qualified 32K + vision profile); not
  done here.
- **F-2 (LOW):** the restore waits for GPU memory like any start; if another workload takes the memory between the
  failed start and the restore it keeps waiting (stoppable; a newer choice supersedes it), and the worker's turn gate
  can open after 600 s while the host still waits.
- **F-3 (LOW, pre-existing):** Assist "Also let URI point out possible mistakes" subtitle is clipped at its scroll
  viewport edge at 1264x681 (same in the closure's screenshot).
- **F-4 (INFO):** the live failure is injected before spawn; a real llama-server crash during load was not produced
  live (unit tests cover the same FAILED path).
- **F-5 (INFO):** `qc_driver.dart` (BRAIN-QC / closure evidence) no longer drives the controls (menus became toggles);
  kept unchanged; `SUCCESSOR.md` points to the new driver.
- Not verified: physical keyboard / mouse; light themes live (theme test only); Windows 10.

## 7. Parallel-closure merge points (for reviewers)
Merged at `a4935c2b` (merge commit, parents `8b25c44f` + `ec2fab54`). Only `brain_quick_controls.dart` conflicted:
the closure's chip calls (`_profileChip` for Vision / Context / Draft, the mismatch Text with `fontSize: 11`) were
re-expressed on the toggles; `draftChoices`, `lockVision`, `mismatchNotice` were taken unchanged. Python merged
cleanly (closure: `controls()` mismatch / assist / vision_locked, worker Assist refusals; this milestone:
`entry_by_profile_id`, the restore explanation in `_brain_health`).
