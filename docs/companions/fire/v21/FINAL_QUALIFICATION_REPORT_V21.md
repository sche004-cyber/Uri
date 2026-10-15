# Ember V2.1 - Final Qualification Report

Branch `phase/fire-companion-v21-20261015` (local only), cut from V2 `b73bd26c`. Plan and criteria:
`00_PLAN_AND_ACCEPTANCE_V21.md`. Owner decisions in this milestone:
- **OD-V21-1:** the GPU override authorization from V2 (OD-8) extends to the V2.1 live runs.
- **OD-V21-2:** the UI V2 compatibility directive (mandatory transparency).

## Verdict

| Record | Result |
|---|---|
| **A. Visual fidelity (AC-F1, >= 90 %)** | **NOT MET** (final round Q2: 85.3-86.8 %) |
| A. Character identity (AC-F3) | MET (92.2-93.1 %) |
| A. Animation (AC-F2) | MET (no regression against V2) |
| A. Performance (AC-P1) | MET (GPU 0.28 %, VRAM same as V2) |
| A. Brain coexistence (AC-P2) | MET with limits (own Brain, lease evidenced; 3 pairs) |
| A. Live Windows (AC-L1) | PASS; known pre-existing PRE-2 teardown failure in returning runs |
| A. Regression (AC-R1) | PASS: 588 passed, 5 skipped, 0 failed at `e792ddc8`; no protected path changed |
| A. Independent review (AC-R2) | R1 and R2 (recheck): ACCEPT WITH FINDINGS. Findings repaired or, where noted, disclosed (`evidence/review/`); no high-severity finding |
| A. Lifecycle acceptance (AC-R3) | **BLOCKED**: the Claude CLI is logged out |
| **B. Transparency readiness (Stage 1)** | **PASS** on all technical gates; the depleted haze look needs owner visual sign-off |
| **C. UI V2 integration (Stage 2)** | **PENDING**: UI V2 is not at its integration checkpoint, and Ember is not in UI V2 |
| Stage 3 canonical integration | **NOT ELIGIBLE** |

## 1. What changed

| Step | Change | Commit |
|---|---|---|
| Painted refinement | The painting behind the character recovered with its brushwork (`Panel.backdrop`); a panel-centred frame so the host's disc shows the whole composition; FP-21 protocol and rounds P1, P2, Q1 | `9933ca2b`, `90ae2248` |
| **Transparency (owner directive)** | No opaque backdrop. A translucent emissive flame glow (alpha <= 0.45) baked into the atlases. Painted backdrop kept only as a 60 % haze on depleted. Ember's own edges fade before its cell border. Transparency gates and a Flutter render test added. | `73e84a6d` |
| Q2, perf, live, review repairs | Final fidelity round on the transparent build; transparent perf; live run 3; R1 repairs | `3a09d438` and later |

What did not change:
- the nine clips, all motion and blinks;
- the runtime Dart code under `uri_ui/lib`;
- Core and Runtime v1;
- the shared companion host.

With V2's `frame` and no `stage`, the exporter reproduces V2 (mean absolute difference 0.0022, WebP noise;
`evidence/diagnosis/diag_v21.json`).

## 2. Diagnosis (`01_DIAGNOSIS_V21.md`)

1. V2's gap was presentation, not character or animation: a frozen cut-out scored the same as the animation.
2. **The host crops Ember.** The host zooms Ember 1.19x and fades it to a disc. In the app, V2 showed 79-91 % of the
   character's alpha; the V2.1 framing shows 95-98 % (`diag_v21.json`).
   - How much of the change from V2's reported 82 to 72-78 under FP-21 this explains is **not isolated**: the
     rubric and the panels changed too (review R1-02).
3. FP-21 added a control: the unmodified painting shown in the app.

## 3. Fidelity (record A) - FP-21

Protocol `03_FIDELITY_PROTOCOL_V21.md` (change log C-1..C-4).
- **Rounds:** three fresh blind reviewers per round.
- **Raw evidence:** each reviewer wrote its own answer file; the full transcripts are kept locally with hashes; the
  access audits are clean.
- **App view:** host arithmetic is exact. The surround is approximated by `#130F0B` and the box is 490 px; the live
  check gives a 316 px box and a mean absolute difference of about 5.5/255 inside the disc (R1-01).

| Round | Build shown | V2.1 visual | Painting control | V2 in the app | Valid |
|---|---|---|---|---|---|
| P1 | painted | 89.0-89.2 | 89.0-89.2 | 78.0-78.2 | yes |
| P2 | host probe | 84.5-86.3 | 85.3-86.3 | - | yes |
| Q1 | painted | 85.7-86.3 | 85.7-86.8 | 72.3-73.5 | yes |
| P3 | transparency variants | 73.8-79.7 (transparent) / 85.7-86.0 (painted) | 85.7-86.0 | - | yes |
| **Q2 (final)** | **transparent, shipped** | **85.3-86.8** | **88.3-89.3** | **77.0-77.8** | **yes** |

Reading:
- **Painted build.** It was level with the painting in the same app presentation: equal in P1 and P2, and within
  0-1.1 points (state means) in Q1.
- **Transparent build.** It costs about 2.5-6 points against that control, depending on the panel.
- **Ceiling.** The control itself scored 85-89 in the app presentation. 90 was not reached by any app-presented
  candidate. So "no artwork can pass" is not established. What is established is that, with this rubric and panel
  size, the painting itself did not reach 90 in the app (review R1-03).
- **Measurement uncertainty is larger than first stated (review R2-01).** Pixel-identical images moved between
  panels by up to 4.9 points (Q1 -> Q2: control, V2 and the ablation all rose 2.0-4.9) and the transparent images by
  5.6-7.8 points (P3 t1 -> Q2). Comparisons across rounds are therefore unreliable. Only within-round differences
  should be used: in Q2, the shipped transparent build is 2.4-3.5 below the control; in Q1, the painted build is
  0-1.1 below.
- **Gain over V2.** V2.1 is 7.5-14 points above V2 as users see it (Q2 transparent: +7.5 to +9.6).

## 4. Transparency and UI V2 compatibility (records B and C)

Full record: `07_UI_V2_COMPATIBILITY_V21.md`.

**Implementation.** Ember carries its own alpha.
- Straight-alpha atlas, premultiplied paint path, minimum-alpha matting (kept).
- An emissive glow encoded as translucent light: desktop compositors blend source-over only, so additive blending
  is impossible.
- A translucent painted haze for depleted only.
- Edges transparent in the outer band of every frame.
- No runtime shader and no UI-specific code.

**Alpha-compositing results** (`evidence/transparency/transparency_gates.json`, every frame of every shipped clip):

| Gate | Result | Baseline V2 / V2.1 painted |
|---|---|---|
| T1 outer band alpha <= 2/255 | worst 0 | 255 / 94 (FAIL) |
| T2 outside the central circle alpha <= 128 | worst 73 (depleted haze); others 64 or less | 255 / 255 (FAIL) |
| T3 opaque area <= 25 % | worst 7.0 % | 21 % / 86 % |
| T4 dark-matte fringe | 0 pixels | - |
| T5 blink patches | edge alpha <= 1 | - |
| Flutter render test (real `EmberCompanion`, transparent layer, no host mask) | 8/8 clips pass | fails on the painted atlases |

**Screenshots against contrasting backgrounds:** `evidence/transparency/contrast_<clip>.jpg`. Each shows three frames
over black, white, blue, grey, a gradient, a checkerboard and noise.

**Existing companion compatibility:**
- no change under `uri_ui/lib`;
- Ember tests 36 existing + 8 new transparency tests, 44/44;
- full suite at the final commit (section 7);
- live run 3 in today's host: Ember restored, blinks, Settings clean.

**GPU and VRAM:** transparent build 0.28 % GPU, 147 MB VRAM, frame p99 2.75-2.78 ms, the same as V2. Solar 6.6-7.5 %
GPU, about 107 MB. Disk 10.35 MiB.

**UI V2 (read-only check of candidate `316e6475`):**
- Companion Mode is a frameless, transparent window that draws companions through the same `LivingCompanion` ->
  `SoftDisc` path. Ember's transparent cell fits it without changes on either side.
- Ember is not yet in UI V2.

**Integration dependencies:**
- port `CompanionIdentity.ember` and `ember_companion.dart` through UI V2's approval process;
- the size preference above 1.0 crops the figure;
- Ember's own presentation scale;
- the startup state.

| Gate | Status |
|---|---|
| B1 genuine alpha | PASS |
| B2 no opaque rectangular background | PASS |
| B3 no visible boundaries (Ember's own) | PASS |
| B4 painterly lighting blends into transparency | PASS technically; the depleted haze look needs owner visual sign-off (PENDING owner) |
| B5 alpha for flames, smoke, particles | PASS; dark smoke is faint on dark desktops (inherent) |
| B6 existing rendering interfaces | PASS |
| B7 existing interaction and animation | PASS (UI V1 host) |
| B8 minimal GPU/VRAM | PASS |
| B9 no regressions to existing companions | PASS (588/5/0; Solar perf unchanged) |
| Real transparent desktop window | **PENDING (Stage 2)**: not exercised; isolated rendering tests do not prove it |
| C1-C10 UI V2 live checks | **PENDING** |

## 5. Performance (`05_MEASUREMENTS_V21.md`)

- **Lease:** all measured runs held our own GPU lease, with ownership and no-Brain checks before and after every run
  (24/24 across both series).
- **Disclosed:** one defective attempt (overwritten frame-timing files) and one lease refusal.
- **Live Brain coexistence:**
  - our own Brain; the machine lease history shows our host holding the lease during the pairs;
  - 139-152 tok/s, except Ember's first pair turn at 115.3, which had lower draft acceptance;
  - no material slowdown, but 2-5 % cannot be excluded with 3 pairs.

## 6. Live (`06_LIVE_QUALIFICATION_V21.md`)

Runs:
- **Run 1, first-time user, painted build:** all journeys PASS, including the recoverable error and recovery.
- **Run 2, returning user, painted build:** journeys PASS. The test process exited rc=1 from the pre-existing PRE-2
  teardown race (`OiConversation` used after dispose), as in V2.
- **Run 3, returning user, transparent build:** journeys PASS, with the same PRE-2 teardown failure.

The interaction was automated; this is not a human usability study. The wake phrase does not exist in URI.

## 7. Regression and integrity

- **Full Flutter suite at `e792ddc8`:** 588 passed, 5 skipped, 0 failed (`evidence/tests/full_flutter_test_final*`).
  That is 580 as in V2, plus the 8 new transparency tests.
- **Boundary and frozen-file check:** `evidence/tests/boundary_check.txt` lists every file changed since V2's
  `b73bd26c`, except the reviewer pack images (`evidence/fidelity/<round>/`). The protected-path check covers all
  files. None is under `uri_ui/lib`, Core, Runtime v1 or the shared host files.

## 8. Startup (`04_STARTUP_PROPOSAL_V21.md`), AMBER

This needs a shared `CompanionState.starting`. It is proposed, not implemented. The `kindling` clip is ready and
unshipped.

## 9. Reference assets and git history

- The art entered history in V1 `8a1438ec` (on canonical `1b5423bc`).
- `git branch -r --contains 8a1438ec` is empty: nothing is published, and no shared history needs rewriting.
- Publication would need a re-cut branch or a `git filter-repo` pass on a copy. That is the owner's licensing
  decision (OD-2).
- Reviewer transcripts stay local.

## 10. Remaining limitations and risks

1. AC-F1 is NOT MET. FP-21 has its own limits:
   - language-model reviewers, judging stills;
   - about +-2 points of panel noise;
   - class-scoring;
   - a dark-canvas surround approximation;
   - it does not score the desktop backgrounds of a transparent window.
2. Transparency costs fidelity on today's dark canvas: within-round, about 2.4-3.5 points below the control in Q2 and about 6 below the painted build in P3. Cross-round numbers carry 5+ points of panel variance (R2-01).
3. The depleted clip's translucent haze is a visual-identity choice.
4. Dark smoke is faint on dark desktops.
5. UI V2 integration is untested (PENDING). The size preference above 1.0 crops the figure inside the disc.
6. The textured haze can hold a faint static flame residue (R1-05). It is now used only in depleted.
7. Pre-existing:
   - F-STARTUP (sad face while loading);
   - PRE-2 (teardown race);
   - the launcher attaches to any running Runtime v1 server (the harness guards against this).
8. Lifecycle acceptance is BLOCKED.

## 11. Recommendation for the owner

1. **AC-F1.**
   - Option 1: accept Ember V2.1 under a waiver. Evidence: within each round it scores 0-3.5 points below the painting shown the same way. Panel variance between rounds is about 5 points, so the absolute level is uncertain.
   - Option 2: redefine the target relative to the painting shown in the app (an owner decision, not applied here).
   - Otherwise V2.1 is not eligible for Stage 3.
2. **Approve or adjust the transparency look**, especially the depleted haze, from `evidence/transparency/`.
3. **Startup state:** approve or decline the shared `starting` state.
4. **Licensing (OD-2)** before any publication.
5. **Log in the Claude CLI** so the lifecycle can accept the exact final commit.
6. **Stage 2:** when UI V2 reaches its controlled integration checkpoint, port Ember through UI V2's process and run
   the Stage 2 live list.
