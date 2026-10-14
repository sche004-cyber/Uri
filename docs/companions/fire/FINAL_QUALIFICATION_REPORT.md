# URI Fire Companion "Ember" - Qualification Report and Integration Proposal

Milestone FIRE-COMPANION-20261014 · branch `phase/fire-companion-20261014` · worktree
`C:\Users\cheta\Development\uri-fire-companion` · base canonical `integration/git-sync-20261008` @ `1b5423bc`.
Nothing is merged, pushed or deployed. **STOP: waiting for the owner's decision.**

## Status at a glance

| Item | State |
|------|-------|
| Researched | YES - `01_RESEARCH_AND_APPROACH.md` |
| Planned | YES - `00_PLAN_AND_ACCEPTANCE_CRITERIA.md` (AC-1..AC-10, owner decisions OD-1..OD-4) |
| Implemented | YES - Blender source + 8 shipped clips + Flutter integration as an additional companion |
| Tested (automated) | YES - see section 9 |
| Live verified (Windows, real server + Brain) | PARTIAL - 7 of 10 journeys fully, 2 partial, 1 not available (section 10); automated input, not a human |
| Visual fidelity >= 90 % | **NOT MET** in any state (section 5) |
| Independently accepted | NO lifecycle-driver acceptance (OD-4: Claude CLI logged out). Separate-reviewer rounds: R1 REJECT, R2 ACCEPT WITH FINDINGS, R3 see section 14 |
| Ready for integration | **NO** as specified (AC-2 not met); integrable as-is only if the owner accepts the fidelity result (section 17) |

## 1. Research findings
- URI companions are identities drawn through one seam (`LivingCompanion` -> `CompanionOrb`) from the authoritative
  `CompanionState` (9 values). Ember plugs into that seam; no surface, state source or contract changed.
- Real-time options compared (shader, sprite loops, 2.5D rig, glTF, alpha video, Rive/Lottie): pre-rendered sprite
  loops won on fidelity-per-cost; measured cost confirms it (section 11).
- Video reference (owner-supplied) used for motion: idle sway and tail flicks, joyful hop and orbiting sparks, fierce
  stance and hand fireballs, depleted flame dying to smoke.
- Wake word: canonical URI has none (push-to-talk only). Not built, not simulated.
- Provenance: references are AI-derived from a Fiverr illustration; owner decision OD-2 (owner holds or will license).

## 2. Selected implementation
Blender 5.2.2 (portable, official checksum-verified zip; the MSI install stalled on UAC) builds the character from
`companion_art/fire/build_ember.py`: armature rig, one control object with 40+ expression controls, geometry-nodes
flame strands with exactly periodic noise (seamless loops), shape-key mouth, lid plates, ember particles. `states.json`
defines each clip; `render_ember.py` + `postprocess.py` (glow and glow-derived alpha) + `export_sprites.py` produce
WebP atlases. Flutter `EmberCompanion` plays them, cross-fades additively, sleeps between sprite frames and frees its
atlases when not shown.

## 3. Blender assets
`companion_art/fire/ember.blend` (276 KB, rebuildable), scripts above, `states.json`. No third-party assets.

## 4. Previews
`evidence/fidelity/fidelity_sheet.jpg` (reference vs render), `evidence/perf/grid.jpg`, `evidence/perf/ember_idle_bg.jpg`,
`evidence/live/live_grid.jpg` and `evidence/live/screens/` (real app).

## 5. Fidelity per state (`04_FIDELITY.md`)
| State | Automated (0 = generic fire spirit, 100 = the painting) | Independent critique | Same character by another artist (critique) |
|-------|------|------|------|
| Idle | 0.3 | 51 % | 66 % |
| Joyful | 13.2 | 41 % | 63 % |
| Fierce | 6.1 | 46 % | 66 % |
| Depleted | 21.5 | 50 % | 67 % |
Target 90 - **NOT MET**. On this target, even the same character redrawn by another artist reaches 63-67 % (critique)
and 0-19 (automated): 90 effectively requires reproducing the painting. Biggest gaps: flame structure, head material,
per-state poses, joyful eyes, painterly surface.

## 6. Additional animation states
Five derived clips beyond the reference: listening, thinking, speaking, focused (working), concerned (error).
Fierce is rendered but not shipped (no state may show anger at the user).

## 7. Animation / state matrix
`02_STATE_MATRIX.md` - all 15 lifecycle situations mapped to the 9 existing states; 8 shipped clips.

## 8. Flutter integration
Ember is a sixth `CompanionChoice` (Solar stays default; classic and the four shader identities unchanged); theme
follows the existing Solar Ember palette; settings hide controls that cannot change Ember (particles, atmosphere,
render quality) and show a 15 KB still in the picker; reduced effects -> classic orb, reduced motion -> still frame.

## 9. Automated tests
Full `flutter test`: baseline `1b5423bc` 543/543 pass; candidate (run 1) 558/558 pass, one test renamed, 16 new
(`evidence/tests/run1_test_compare.json`). Final full suite on the code of `d7093fbf`: 570/570 pass, one renamed,
28 new (`evidence/tests/final_test_compare.json`); after the R3 repairs the four companion suites were re-run
(141/141; log not kept - superseded by the R4 run, `evidence/tests/r4_companion_suites.log`, 143/143). Ember-specific: 26 test declarations, 28 executed tests in ember_companion_test.dart (the cadence test runs at three motion speeds)
(mapping, assets, manifest validation, decode-wait fade, failed loads, shared library, VRAM release, cadence at three
motion speeds, still mode) + 2 shell/settings tests.

## 10. Live Windows results (`05_LIVE_QUALIFICATION.md`)
Real production `main()`, real worker/Core/Brain, automated input (not human): start PASS, select PARTIAL (the
fixture already held Ember, so a change of companion was not exercised in the recorded run), idle PASS,
wake phrase NOT AVAILABLE, conversation PARTIAL (typed turn only, no microphone turn), mode switching PASS, real task
with approval PASS, completion PASS for the task but the joyful expression is never reached in the integrated profile
(F-SUCCESS), recoverable error PASS, return to idle PASS. The test process reported failure only because of 12
pre-existing framework assertions in canonical voice settings (PRE-1).

## 11. Performance (`03_MEASUREMENTS.md`)
Profile build, real window, 476 px: Ember GPU 3D median 0.23 % vs Solar 6.2 %; raster p50 0.68 vs 0.83 ms; 35-60
frames requested per second vs 145-160; dedicated VRAM +40-65 MB vs Solar while shown (decoded atlases). Release of
the atlases when another companion is selected is asserted by a unit test, not measured live. App bundle +~14 MB.

## 12. GPU and Brain coexistence
Runtime v1 (15.3 GB) does not fit next to the desktop on the 16 GB card without oversubscription; with the owner's
one-run override it loaded and then demoted (URI reported 1.0 GB moved to system memory); decode 48-82 tok/s.
Ember vs Solar under that condition: INCONCLUSIVE (2 samples each). Ember adds 40-65 MB of VRAM pressure while shown.

## 13. UX improvements made / found
Made: picker still instead of blank tile; no dimming in fades; fades wait for decode; atlases freed when hidden;
non-applicable controls hidden. Found, not changed (outside scope): F-SUCCESS, PRE-1, UX-1 (prompt bubble overlaps
status label, all companions), blinks repeat every 4 s, Brain-loading start shows the depleted (sad) Ember to a
first-time user for ~5 minutes.

## 14. Independent audit
Fresh separate Claude reviewers (no lifecycle driver - OD-4): R1 REJECT (2 blocking MEDIUM) -> repaired `7d83947d`;
R2 ACCEPT WITH FINDINGS (3 MEDIUM) -> repaired `96bcc319`, `59157120`; R3 on `d7093fbf`: REJECT on evidence
integrity (four MEDIUM: unsupported preference-hash claim, wrong screenshot citation and an unlogged 133 tok/s figure,
critique scores and eye self-check not committed, journey 2 marked PASS without a change of companion) plus LOW code
findings (failed clips retried on every rebuild, a stale pending wake delaying the next) -> repaired in `c9d91758`;
R4 on `c9d91758`: REJECT (R4-01 MEDIUM: the R3 retry window introduced a regression - an expired failure was never
reloaded and polled at 20 Hz; R4-02 MEDIUM: VRAM release overstated in this report) plus LOW items -> repaired in
the commit after `c9d91758`; R5: see the addendum at the end.
Visual critique by a separate reviewer: section 5. Not lifecycle-ACCEPTED.

## 15. Remaining defects and limitations
AC-2 fidelity not met · Brain coexistence inconclusive · no microphone/voice turn in the live run · wake word absent ·
F-SUCCESS · PRE-1 · UX-1 · periodic blinks · 320 px cells upscaled at the largest size · 35-60 frames/s instead of 24 ·
eye component of the scorer unreliable on joyful/fierce · reference images and 14 MB of derived assets are committed
on the branch (licence OD-2; nothing pushed) · graphify graph not regenerated (to be run at integration to avoid graph
conflicts).

## 16. Branch, worktree, commits
Branch `phase/fire-companion-20261014` in `C:\Users\cheta\Development\uri-fire-companion`, local only (not pushed):
`8a1438ec` feature, `9508281a`/`4e3e0ed0` live harness, `7d83947d` R1 repairs, `96bcc319` R2 repairs, `59157120` pacing,
`d00211ab`/`d7093fbf` docs and evidence, `626639c9` report draft, `c9d91758` R3 repairs, then the R4 repair commit
(see addendum). Disposable runtime `C:\Users\cheta\Development\uri-fire-companion-rt`
(materialized from `59157120`). Live harness folder `C:\Users\cheta\Development\uri-fire-companion-live`.

## 17. Canonical integration readiness and proposal
Not ready as specified: the owner's AC-2 (>= 90 % fidelity) is not met, and it is not reachable by tuning this
approach. Options for the owner:
1. **Do not integrate; commission fidelity v2** (swept-sheet flame, NPR/painterly shading, per-state poses and eyes),
   then re-qualify. Recommended if the reference look is the point.
2. **Integrate as "Ember (preview)"** with the measured fidelity accepted, after resolving the licence (OD-2) and
   choosing whether reference images stay in git.
3. **Keep on the branch** as research.
Any integration needs explicit owner authorisation; follow-ups F-SUCCESS and PRE-1 are proposed separately.

## Addendum - review rounds after the first draft

(Filled in as rounds complete; nothing above is rewritten except where a correction is marked.)

- **R4** on `c9d91758`: REJECT - R4-01 (MEDIUM, a regression introduced by the R3 retry window: an expired failure
  was never reloaded and the widget polled at 20 Hz), R4-02 (MEDIUM, VRAM release overstated in section 11), LOW
  R4-03..R4-08. Repaired in `e6ae4712`. Full suite on `e6ae4712`: 572/572 pass, one renamed, 30 new
  (`evidence/tests/r4_full_suite_compare.json`).
- **R5** on `e6ae4712`: ACCEPT WITH FINDINGS, no HIGH or blocking finding. The reviewer reproduced R4-01/R4-03
  repairs with its own probes. LOW findings: R5-01 a still or reduced-motion companion never retried a failed clip;
  R5-02 wake arbitration used a different clock from the injectable one; R5-03 test count and log binding in this
  report; R5-04 the preference-copy time is not evidenced. Repaired in the commit after `e6ae4712`
  (R5-04: the time is marked unverifiable; the conclusion rests on the unchanged hash and the 2026-10-10 last write).
- **R6**: see below.
