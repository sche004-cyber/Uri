# Ember V2.1 - controlled canonical integration, stage 2 receipt

**Status: QUALIFIED ON CURRENT CANONICAL - CANONICAL INTEGRATION BLOCKED (OD-2 licensing).**
Ember is NOT integrated and NOT pushed. Owner authorization (2026-10-18) permits integration after gates but "does not
authorize ... waiving licensing requirements" and says "Do not push Ember while licensing clearance remains
unresolved". Canonical is the `uri-repo` branch, so integration requires a push; that push would publish the reference
art (section 6). Reviewer verdicts are independent read-only subagents (Codex quota-blocked until 2026-10-22), not
owner approval.

## 1. Provenance

| Item | Value |
|---|---|
| Canonical now | `integration/git-sync-20261008` = `ec2fab54` (Brain QC closure, integrated by the runtime-profiles session; fast-forward from `feaabe3f` = Brain Quick Controls stage 1) |
| Ember source | `milestone/ember-v21-integ-20261018` tip `0b853288` (code `67d61d3a`), qualified R1-R4 |
| Candidate branch | `integration-candidate/ember-on-canonical-20261018`, worktree `D:\uri-dev\uri-integ-ember` |
| Commits | `55405e7e` merge Ember onto `feaabe3f`; `b07bd496` IC1-03 (companion Initializing during a Brain switch); `8f883bbf` review F-1/F-2; `bb61e976` merge canonical `ec2fab54`; this receipt (docs) |
| Merge quality | all merges clean (no conflicts); QC/closure and Ember touch disjoint UI files; closure keeps the `switch.pending` semantics Ember reads |

## 2. Code changes beyond the qualified Ember candidate

| Commit | Change | Review |
|---|---|---|
| `b07bd496` | During a Brain Quick Controls profile switch the companion shows Initializing "Switching Brain" (target named) instead of ready/idle (turns are refused then); GPU wait / failure keep FCV-10 (D-1) | IC1 (QC integration) finding IC1-03; stage-2 review |
| `8f883bbf` | switching derived from worker controls only (F-1); a FAILED host during a switch shows the FCV-10 error "Brain failed to start" (F-2); test fixture with RECOVERING | stage-2 review F-1/F-2 |

Stage-2 review (`ember_stage2/review/EMBER_INTEG_report.md`, at `b07bd496`): ACCEPT WITH FINDINGS (3 LOW, 2 INFO); F-1/F-2/F-3
repaired; F-4/F-5 INFO recorded (F-5: STOPPING/RELEASE_WAIT during a requested switch shown as Initializing - an
interpretation of D-1 "genuinely starting", owner may disagree).

## 3. Automated gates at `bb61e976`

| Gate | Result |
|---|---|
| pytest `tests/oi tests/ws` | 793 passed, 23 skipped |
| `ws_frozen_check` (full output) | `unapproved_protected_changes: []` |
| flutter analyze | 0 errors, 5 info |
| full flutter test | 855 passed, 5 skipped |
| Windows release build | rc 0 |
| T0-T5 atlas gates (at `b07bd496`; atlases unchanged since) | unchanged from Ember qualification: only T4 depleted (fringe 14 px) - carried owner decision |

## 4. Windows live verification (Debug build via integration_test, synthesized taps + Win32 probe with OS input; real worker, Core, Runtime v1 Brain; own lease; no override)

| Run | Code | Brain | Result |
|---|---|---|---|
| `e-first` | `8f883bbf` (pre-`ec2fab54` merge) | frozen Standard | ALL PASS: Ember selected, Initializing -> idle (calibration 154.7 tok/s), borderless, per-pixel transparency, click-through, Ember click, drag, 1.25x, conversation thinking->speaking->success, Brain stop -> unavailable, recovery -> "15", choice persisted |
| `e-returning-switch` | `8f883bbf` | frozen | harness defects (INVALID for switch): fact prompt triggered the remember_fact approval card; Ember harness host is in-process. Window checks passed |
| `c-uiv2` | `8f883bbf` | frozen | UI V2 journeys PASS |
| `c-qc` | `8f883bbf` | - | Brain never started: production host refused, GPU CONTENDED (owner's Chrome ~660 MB + dwm). Correct safety behaviour; no QC evidence from this run |
| `p3-ember-switch` | `bb61e976` | **P3 (32K + vision, no MTP), owner instruction** | Window checks ALL PASS (borderless; 90.8 % transparent / 7.1 % blended; click-through; Ember click reaches URI; drag; 1.25x). Brain switches P3 -> Long -> P3 under Ember: companion Initializing while switching and never idle (both switches); idle after; recall "4817" after each switch; Ember transparent on Long (89.8 % / 5.4 %). One check `R-initializing-seen` failed because this harness starts the Brain before the app (READY 12:28:48, first app sample 12:29:20) - not applicable here; startup Initializing passed in `e-first` |
| `p3-uiv2` | `bb61e976` | P3 | UI V2 journeys PASS |

Owner instruction 2026-10-18: "Close crome or try with no mtp and 32k context size". A normal close request ended only
Chrome helper processes; Chrome restarted its GPU process (438 MB). The browser was not force-closed. Final live runs
use P3 (`--profile 32768,gpu,0`, a qualified profile).

Performance under the owner's desktop contention (not comparable with qualified baselines): P3 calibration 63.3 tok/s
with ~2.1 GB of the Brain non-local (demotion caused by foreign GPU use; fit AT_RISK +250..+431 MiB). Ember's own
cost: window 178.5 MiB dedicated (Debug runner), unchanged from Ember qualification runs (173-179 MiB). No Ember-
attributable regression; Brain throughput comparisons need an uncontended desktop (NOT VERIFIED on `bb61e976`).

## 5. Findings carried (owner decisions, unchanged)

Fidelity AC-F1/AC-F3 NOT MET; F-LIGHT-1 light-desktop visibility; T4 depleted; F-SIZE-1 size crop; F-START-GAP
startup gap; AC-P1 peak VRAM. Accepted limitations vs mandatory: none of these is waived here; they remain open owner
decisions recorded since the Ember V2.1 closure. Additional: INTEG harness notes above; HARN-2 (Ember probe gate
looseness, recorded in the Ember receipt).

## 6. Licensing (OD-2) - BLOCKING for canonical integration

Investigation (`ember_stage2/review/OD2_licensing_investigation.md`, repository evidence only):
- OD-2 asks the licence of the reference art ("Fiverr illustration; emotions sheet carries a Gemini mark"); the recorded
  owner answer is "I hold rights / will license"; no licence, receipt or attribution is in the repository.
- The 12 shipped Ember files (`uri_ui/assets/companions/ember/`) are pixel-level derivatives of that art (signature and
  generator mark inpainted out).
- `git log feaabe3f..bb61e976` contains the reference art and reviewer packs (15 commits, from `8a1438ec`); pushing the
  candidate publishes them.

Options (owner decisions): (A) confirm rights to the Fiverr illustration and Gemini output, then push as is; (B) push a
history-clean port of the shipped files only (keeps reference art out of history; atlases still derivative, still needs
rights; also waives handoff §12 "keep Ember history"); (C) keep Ember integrated locally only (no canonical change);
(D) replace the art with licensed or owner-made art and requalify.

## 7. Rollback

Nothing was pushed for Ember; canonical is unaffected. The candidate branch is local; discarding it is the rollback.
Brain Quick Controls stage 1 rollback is in `01_BRAIN_QC_INTEGRATION_RECEIPT.md` section 6.
