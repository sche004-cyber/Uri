# Ember V2.1 - Independent review R1 (range b73bd26c..90ae2248)

**Verdict: ACCEPT WITH FINDINGS**

The NOT MET verdict on AC-F1 is honest and reproducible. No high-severity defect was found. The findings below are
about overclaims, confounded reasoning, measurement fidelity and missing evidence. They weaken parts of the "the cap
is the presentation" argument, but they do not change the NOT MET result.

## What I verified independently (read-only)

- **Decoding.** `decode_v21.py` was re-run for q1, p1 and p2. `git diff` was empty afterwards for all three
  `*_decoded.md` files. Pack integrity is OK in every round.
- **Raw evidence.**
  - The reviewer packs in the session scratchpad (`fp21/q1/pack_r1..3`) are byte-identical to
    `evidence/fidelity/q1/reviewer1..3`.
  - Every raw answer file (p1, p2, q1) is byte-identical to its scratchpad original.
  - `q1_raw/SHA256SUMS.txt` verifies.
  - My own pass over all 9 transcripts confirms that each reviewer touched only its own pack and its own answer
    file. The Glob calls were on each reviewer's own `pack_r3` folder.
- **App-view arithmetic.** `critique_pack_v21.app_view` and `host_mask` match the Dart host:
  - `presenceScale` = clamp(0.50 / 0.42, 1, 1.4) = 1.190;
  - `OverflowBox` with a centred `size*scale` square;
  - `SoftDisc` `RadialGradient` stops `[0, 0.72/scale, 1/scale]` on the scaled square, which is opaque to 0.72 of
    the box radius and zero at the box edge;
  - `EmberPainter` draws the cell to the square with `FilterQuality.medium` (bilinear on upscale).

  The only residuals are sub-pixel: a 0.5 px crop offset from `(583-490)//2` and r = 583 against 583.3. Canvas and box
  size are covered in R1-01.
- **Shipped atlases against the pack.** Taking the worst frame from the committed
  `uri_ui/assets/companions/ember/{idle,joyful,depleted}.webp` and running it through the same app view gives the
  Q1 `v21_worst` images with a mean absolute difference of 0.46-0.85 / 255.
- **Backdrop formula.** It is correct for `src = bg*(1-a) + F*a` with straight `F` (`layers.py` stores straight RGB,
  and `Panel.pm` premultiplies).
  - Wherever `F` was not clipped, `(src - F*a)/(1-a)` equals `bg` exactly.
  - Where `a = 0` it equals `src`.
  - The aura layer is returned premultiplied (`bg*a, a`) and composited correctly with `big + au*(1 - big_a)`.
- **V2 path.** `Framing(..., stage={}, frame={"side":490,"feet_at":0.955})` follows V2's code path term by term:
  - strength is not overridden;
  - pool (0.55, 1.0), edge 0.12 and the non-rounded fade are unchanged;
  - the bg plate is the same expression.
- **Performance.** The 05 table matches `perf/summary.json` (V2 r1 GPU 0.285 rounds to 0.29). `lease_checks.txt` has
  12/12 checks held, ours=True, brain_resident=0. Atlas bytes are 9.72 MiB at b73bd26c and 3.31 MiB at 90ae2248.
- **Tests.** `full_flutter_test.json` contains 580 successes not skipped, 5 skipped and 0 failures, and
  `done success=true`.
- **Boundaries.** The range changes no file under `uri_ui/lib`, no Core or Runtime file and no shared host file. The
  only `uri_ui` changes are the assets and the new `uri_ui/tool/capture/run_ember_perf_v21.ps1`. `kindling` has
  `"ship": false`; it is not in `manifest.json` and there is no `kindling.webp`.
- **Numbers.** Every number quoted in FINAL, Q1_RESULTS and P1_P2_RESULTS matches the decoded tables, except where
  noted in R1-04.

## Findings

### R1-01 (medium): the pack's canvas and box are not what the live app shows, and the promised screenshot check was not done

- **Where:** `scripts/fire_companion/critique_pack_v21.py:47-49`; `03_FIDELITY_PROTOCOL_V21.md:40-43`;
  `FINAL_QUALIFICATION_REPORT_V21.md:62`.
- **What is wrong:**
  - The pack composites on a flat `#130F0B` (19,15,11) in a 490 px box.
  - The live companion screen is a warmer, lighter radial field with a vignette, and the companion box there is
    about 300 px.
  - The protocol says "the live run checks it against screenshots". `06_LIVE_QUALIFICATION_V21.md` reports no such
    check.
  - FINAL calls the rendering "exactly as the host computes them". The host arithmetic is exact, but the surround is
    not.
- **Evidence:** I sampled `evidence/live/run1_first/first-05-idle-brain-ready.jpg` (5x5 means):
  - next to the disc: (29,20,11), (29.4,20,11) and (29.8,20,11);
  - window corners: (26,17,10);
  - only far out at (200,250) and (1000,400): about (16-19,13-14,8).
- **Bias:** this works **against** V2.1 and the control alike. The reviewers' most-named cost is the "dark
  surround", and the real surround is lighter and browner. The absolute level of the "ceiling" is therefore probably
  understated by an unknown amount. Relative comparisons within a round are unaffected.
- **Repair:**
  - Measure the actual background behind the companion from a live screenshot, or render the real background
    widget, and use it in `app_view`.
  - Record a pixel comparison of `app_view` against a live crop at the same box size, as the protocol promised.
  - In FINAL, replace "exactly as the host computes them" with "host arithmetic exact; surround approximated by
    #130F0B; box 490 px against about 300 px live".

### R1-02 (medium): "V2's 82 was measured on a kinder view" is confounded by the rubric and panel change

- **Where:** `01_DIAGNOSIS_V21.md:91-92` and `110-115`; `03_FIDELITY_PROTOCOL_V21.md:11-14`;
  `FINAL_QUALIFICATION_REPORT_V21.md:53-55`; `P1_P2_RESULTS.md:77`.
- **What is wrong:**
  - The drop from V2's about 82 (V2 rubric: 7 dimensions, mostly character; CP8 panel) to 72-78 (FP-21: 10
    dimensions, 4 of them presentation; new panels) is attributed to the app crop.
  - Rubric, panel and view all changed at once. No same-rubric, same-panel comparison of the V2 square view against
    the V2 app view was run.
- **Evidence:**
  - In P1, `v2_app` **character %** is 82.2-82.5, the same as V2's reported 82. The visual drop to 78 comes from the
    newly added presentation dimensions (71.7).
  - In V2's CP8, V2 (80.5-83.5) sat level with the blurred-painting anchor (81-83). In FP-21 P1 it still sits level
    with `ref_copy` (78.0-78.2 against 77.7-78.3).
  - Relative to the anchor, P1 shows no "kinder view" effect. Q1 shows some (`v2_app` 72-73.5 against `ref_copy`
    80).
  - The alpha-mass share (79-91 % against 95-98 %) is real geometry, but its effect on the score was not isolated.
- **Repair:**
  - Reword F-1 and FINAL section 2 item 2: the crop is real, but how much of the 82 -> 73-78 change it explains is
    not measured, because rubric and panel also changed.
  - Alternatively, add a `v2_square` candidate (V2 cell on canvas, no disc) to a round, to isolate the effect.

### R1-03 (medium): the "presentation ceiling / no artwork can pass" claim is stronger than the noise allows; Q1 and P1 used pixel-identical images

- **Where:** `FINAL_QUALIFICATION_REPORT_V21.md:12-19` and `76`; `P1_P2_RESULTS.md:95-100`;
  `01_DIAGNOSIS_V21.md:107-108`; `Q1_RESULTS.md:35-36`.
- **What is wrong:**
  - Every P1 candidate image is pixel-identical to its Q1 counterpart (mean absolute difference 0.0 for `v21_worst`,
    `painting_app`, `v2_app` and `v21_frame_only` in all four states; P2 `v21_disc` = Q1 `v21_worst`). The
    3.3-point drop from P1 (89.0-89.2) to Q1 (85.7-86.3) is therefore pure panel variance on the same stimuli. This is
    disclosed only as "panels move by about 3-4 points", not as "identical images".
  - In P1 the control scored 89.0-89.2, with one reviewer at 90, within that noise of the threshold.
  - Reviewers scored by template:
    - in P1 every reviewer gave the same visual vector (89/90/88) to `painting_app`, `v21_worst` and `v21_mid` in all
      four states;
    - character was 94/94/94 for every reviewer and state;
    - in P2 `ref_reframed` was 98/93/96 in every state.

    This shows the instrument has low resolution and clusters "app-presented" candidates as one class.
  - "No artwork can pass" and "cannot be shown for any in-app presentation" (P1_P2:99) are therefore not established
    at 3 reviewers × 1 round per presentation.
  - The correct reading is that V2.1 is statistically indistinguishable from the painting in this presentation. This
    is also expected by construction: I measured a mean absolute difference of 2.6/255 between Q1 `painting_app` and
    `v21_worst`/`v21_mid` for idle, reviewer 1.
- **Repair:**
  - State explicitly that Q1 re-scored the same images as P1.
  - Report the panel-to-panel spread as measurement uncertainty, about ±2 points on a round mean.
  - Soften "no artwork can pass" to "the painting itself scored 85-89 in this presentation across three panels; with
    this rubric and panel size, 90 was not reached by any candidate including the control."
  - The NOT MET verdict is unaffected.

### R1-04 (low): "within one point in all twelve pairs" and "equals the control in every valid round" are inaccurate

- **Where:** `Q1_RESULTS.md:28-30`; `FINAL_QUALIFICATION_REPORT_V21.md:13`; `P1_P2_RESULTS.md:98`.
- **Evidence:** I recomputed from the raw answers and the key, comparing per reviewer `min(v21_worst, v21_mid)`
  with `painting_app`:
  - Q1 joyful: reviewer 1 -0.5, reviewer 2 -1.0, **reviewer 3 -2.0**;
  - Q1 fierce: reviewer 2 -0.5;
  - all P1 and P2 pairs are exactly equal (P1_P2 "24 pairs" is correct).

  The "0.1-1.1 below" in Q1_RESULTS:30 is the mean difference, not the per-reviewer range.
- **Repair:**
  - In Q1_RESULTS, write "11 of 12 pairs within 1 point; joyful reviewer 3 2.0 below (per-reviewer range 0 to
    -2.0)".
  - In FINAL:13, write "equals the control in P1 and P2, and is within 0-1.1 of it (state means) in Q1".

### R1-05 (low-medium): the textured backdrop bakes static flame residue under moving flames (possible ghosting), undisclosed

- **Where:** `companion_art/fire_v2/animate.py:136-143`; claim at `01_DIAGNOSIS_V21.md:100-102` ("recovered
  exactly").
- **What is wrong:**
  - Where `layers.py` clipped `F` to [0,1] (bright flame cores at low alpha), `(src - F*a)/(1-a)` keeps part of the
    flame's own light in the **static** backdrop.
  - The faint flame fringes suppressed by the alpha floor also live only in the backdrop.
  - When the flow warp, sway and flicker move the flame layer, that residue stays still.
- **Evidence:** I computed max over RGB of |backdrop - bg| on `work/<panel>_layers.npz`, by alpha band:
  - alpha 0.02-0.3: mean 0.034-0.036 and p99 0.18-0.20 (about 50/255) in idle, joyful and fierce;
  - alpha 0.3-0.6: p99 up to 0.22 (idle).

  A P1 reviewer noted for V2.1 idle: "some frames show faint doubled or ghosted wisps"
  (`p1_raw`, motion note). The A3 artefact means are not worse than V2's (P1 8.67 against 8.58; Q1 8.96 against
  8.46), so this is not a measured regression.
- **Repair:**
  - Disclose the effect in 01 and FINAL.
  - Optionally limit the residual where `a > ~0.02` and `F` was clipped: replace it there by `bg`, or blur it more,
    so that only true background strokes stay in the backdrop.
  - Check the change with a motion strip.

### R1-06 (low): exporter semantics: stage strength silently overrides per-clip `aura`; "without stage reproduces V2" needs the V2 frame too

- **Where:** `companion_art/fire_v2/export_v2.py:79`, `44-46` and `126-128`; `FINAL_QUALIFICATION_REPORT_V21.md:46-47`;
  `01_DIAGNOSIS_V21.md:136-138`.
- **What is wrong:**
  1. `strength = self.stage.get("strength", strength)` replaces every clip's `motion.aura` with 1.0. Only the
     `<= 0` guard still reads the per-clip value. The per-clip knob is now dead, and the `_aura` cache key (per-clip
     aura) no longer reflects the content. This is harmless today because all clips are 0.95.
  2. The default `frame` in `expressions.json` is now V2.1's, so omitting `stage` alone does **not** reproduce V2.
     V2 needs both `stage={}` and `frame={"side":490,"feet_at":0.955}`, which is how `critique_pack_v21.py:52-53`
     calls it. The report sentence reads as if `stage` alone were enough.
  3. Informational: `ox = round(97.5)` uses Python's round-half-to-even, giving 98, while `pt()` uses the float
     `x0`. The resulting 0.25 cell-px offset is self-consistent for blink rects and relative eye offsets. No defect.
- **Repair:**
  - Either honour the per-clip aura (multiply instead of override) or remove the per-clip value and document it.
  - Reword the report to "with V2's `frame` and no `stage`, the exporter reproduces V2".

### R1-07 (low-medium): two quantitative claims have no committed script or output (violates D-1)

- **Where:** `01_DIAGNOSIS_V21.md:82-89` (character alpha-mass shown: V2 79-91 %, V2.1 95-98 %) and `:137-138`
  (V2 reproduction "mean absolute difference 0.0022"); FINAL:47 and 54.
- **Evidence:** a grep of `scripts/`, `companion_art/` and `docs/companions/fire/v21` finds these numbers only in the
  two documents. No script, log or JSON produces them. D-1 says every claim cites something that can be re-run.
- **Repair:** commit the measurement snippet (or add it to `critique_pack_v21.py` / `demo_v21.py`) and its output,
  then cite them.

### R1-08 (low-medium): live coexistence wording overstates the evidence

- **Where:** `05_MEASUREMENTS_V21.md:119` and `141-143`; `FINAL_QUALIFICATION_REPORT_V21.md:27-28`.
- **What is wrong:**
  1. "Here the rates held at 139-152 tok/s throughout" is contradicted by pair 1, Ember: **115.3 tok/s**
     (`observations-first.json` entry "coexistence ember 0", predicted_per_second 115.3, draft 48/78).
  2. "Our own Brain **under the lease**":
     - the runner only checks that the lease is FREE before starting the host (`run_fire_v21_live.py:105-156`);
     - the committed `first-brain_host.json` is the post-stop record of the restarted host (`"lease": {"held":
       false}`, history without lease states);
     - `runner-log-first.json` records the lease only as FREE.

     No committed artefact shows the lease held by the Brain during the coexistence pairs. Ownership (pid 12336) is
     proven; the lease is not.
- **Repair:**
  - Change the sentence to "139-152 tok/s except pair 1 Ember (115.3, lower draft acceptance)".
  - Either add lease-state samples taken during the run (`gpu_lease status` per turn) or reword to "own Brain,
    started only when the lease was free; lease holding during the run not recorded".

### R1-09 (low): small live-journey wording gaps

- **Where:** `06_LIVE_QUALIFICATION_V21.md:41` and `47`.
- **What is wrong:**
  - The greeting turn records `companion_states: ["thinking", "success"]`, with no `speaking`. The table says
    "thinking -> speaking -> success". `speaking` was recorded in the coexistence and recovery turns, not in the
    greeting.
  - For journey 9 the structured record has `answer_status: null, core_code: null`. `BRAIN_UNAVAILABLE` is evidenced
    only by screenshot `first-16-error-visible.jpg`; I checked, and the text is visible there.
- **Repair:**
  - Correct the greeting sequence.
  - Cite the screenshot as the evidence for `BRAIN_UNAVAILABLE`, or capture the code in the driver.

### R1-10 (low): the headline "first-time and returning users PASS" hides that run 2's test process failed

- **Where:** `FINAL_QUALIFICATION_REPORT_V21.md:29-31`.
- **Evidence:** `run2_returning/runner-log-returning.json` records "flutter test finished" with rc 1.
  `flutter-test-returning.log` ends with "Some tests failed" (PRE-2, `OiConversation` used after dispose). The R1-R3
  observations completed and `ui-finished` is true. 06 discloses this; the FINAL headline does not.
- **Repair:** in the FINAL bullet, write "returning-user journeys PASS; test process rc=1 from pre-existing PRE-2 at
  teardown".

### R1-11 (low): protocol-process deviations not recorded

- **Where:** `03_FIDELITY_PROTOCOL_V21.md:3`, `36`, `53-54` and the prompt text.
- **What is wrong:**
  1. **"LOCKED before P1" is not evidenced in git.**
     - The protocol was first committed in `9933ca2b` at 12:09:35.
     - That is after the P1 key (11:54), the P1 answers (about 12:02) and the P2 answers (about 12:08).
     - It is unchanged between 9933ca2b and 90ae2248, so it was not edited after Q1.
  2. **The `reviewer<N>_handback.txt` files promised in section 3 do not exist.** The hand-back is only inside the
     local, gitignored transcripts.
  3. **"The loop frame the automated scorer ranks furthest"** is taken from V2's `auto_cp8/scores_v2.json`
     (`critique_pack_v21.py:55` and `146`), not re-scored for V2.1. The impact is negligible, because worst and mid
     scored identically.
  4. **The prompt primes class-scoring.** It tells reviewers that some candidates are "shown as they would appear
     inside an app, on a dark background with a soft round vignette". This applies to all candidates equally, but it
     may contribute to the template scoring noted in R1-03.
- **Repair:**
  - Add a change-log note covering items 1-3: lock time evidenced by file times or session log; transcripts replace
    the handback files; worst frame taken from V2's scorer.
  - For future rounds, commit the protocol before the first pack is built.

### R1-12 (low): evidence housekeeping

- **Where:** `00_PLAN_AND_ACCEPTANCE_V21.md:17`; `evidence/tests/`; `uri_ui/tool/capture/run_ember_perf_v21.ps1:6`;
  `evidence/perf/attempt1_overwritten/_incoming$3/`.
- **What is wrong:**
  - AC-R1 names "frozen-file integrity", but `evidence/tests/` holds no such check. I confirmed the boundaries
    independently with `git diff --name-only`.
  - The test JSON does not record the commit it ran on. It started at 07:28Z, before both commits' docs; the code
    did not change between 9933ca2b and 90ae2248.
  - The usage line in the ps1 omits the now-mandatory `-Baked` parameter.
  - The folder name `_incoming$3` looks like a shell-expansion slip in the attempt-1 tooling.
- **Repair:**
  - Add a short frozen-file / boundary check output, such as `git diff --name-only b73bd26c HEAD` filtered to
    protected paths, and a HEAD hash next to the test summary.
  - Fix the usage line.
  - Mention the odd folder name in 05's attempt-1 note.

### R1-13 (low, informational): uncommitted working-tree change in the reviewed file

- **Where:** working tree, `companion_art/fire_v2/export_v2.py` (not in the range).
- **What is wrong:** `git status` shows an uncommitted 26-line addition: `Framing.glow`, a "transparency mode", and a
  call in `big_frame` gated on `stage["glow"]`. The committed `expressions.json` has no `glow`, so it is inert for
  this build. It does mean the worktree is not the reviewed commit.
- **More changes during the review:** by the end of the review, someone other than me had also modified or added
  these working-tree files:
  - modified: `expressions.json`, `03_FIDELITY_PROTOCOL_V21.md`, `decode_v21.py`, `critique_pack_v21.py`;
  - added: a `p3` round, `scripts/fire_companion/transparency_check.py` and
    `uri_ui/test/living/ember_transparency_test.dart`.

  None of these are reviewed here. My decode re-runs happened before those edits, when only `export_v2.py` was
  modified, and they left the decoded files unchanged. A later edit to the **locked** protocol after Q1 would need a
  change-log entry.
- **Repair:** commit it on a separate branch or discard it before lifecycle acceptance of "the exact final commit".
  Any re-export or re-pack should come from a clean tree.

### R1-14 (low): "Everything else that was asked for is delivered" while AC-R2 and AC-R3 were outstanding

- **Where:** `FINAL_QUALIFICATION_REPORT_V21.md:9` and `101`.
- **What is wrong:** at 90ae2248, `evidence/review/` did not exist (AC-R2 was not done) and AC-R3 is BLOCKED.
  Section 7 points to a folder that was not yet there.
- **Repair:** write "everything else is delivered and measured, except independent review (in progress) and
  lifecycle acceptance (BLOCKED)". Update the line after R1 repairs.

## Summary against the review criteria

| Criterion | Result |
|---|---|
| 1. Code correctness | Correct for the layer model; V2 path reproduced given V2 frame + empty stage; findings R1-05, R1-06 |
| 2. Measurement validity | Host arithmetic exact; surround colour/box size differ from live, bias against V2.1 and control equally (R1-01) |
| 3. Protocol integrity | Decoding reproducible, integrity and access verified; numbers match except R1-04; deviations R1-11; confounds R1-02, R1-03 |
| 4. Perf and live | Perf table matches; live wording overstated in R1-08, R1-09, R1-10 |
| 5. Boundaries | Confirmed: no Dart source under `uri_ui/lib`, no Core or Runtime code, no shared host file; kindling not shipped; 580/5/0 supported |
| 6. Honesty | Threshold not bent; NOT MET reported. Overclaims in R1-02, R1-03, R1-04, R1-08, R1-10, R1-14 |
