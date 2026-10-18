# Ember V2.1 - Independent review R2 (range 90ae2248..33459fa8)

**Verdict: ACCEPT WITH FINDINGS**

No high-severity defect was found.
- The transparency implementation is premultiplied-correct.
- Every gate reproduces on the committed atlases.
- The V2 path still reproduces V2.
- No protected path changed.
- NOT MET on AC-F1 is reported honestly.

The findings are about:
- measurement uncertainty that is understated (new evidence makes it larger than the reports say);
- a few wrong or unsupported numbers and references;
- test-scope limits;
- small R1 leftovers.

None of them changes a verdict.

## What I verified independently (read-only)

- **Working tree.** Clean at `33459fa8`, so R1-13 is resolved. `git status` was empty before and after every script I
  ran.
- **Transparency gates.**
  - I ran `python -B scripts/fire_companion/transparency_check.py --out <scratchpad>`. It printed ALL PASS on all 8
    shipped clips (456 frames) and the 7 blink rows.
  - My `transparency_gates.json` is identical to the committed one.
  - The atlases have not changed since `73e84a6d`.
  - The baseline JSONs match 07 section 2 (V2: border up to 255, opaque 13-21 %; painted: border 94, opaque 86 %).
- **Glow math (`export_v2.py:138-159`).**
  - `lum` is the max over **premultiplied** RGB.
  - `straight_col = blur(rgb*w) / blur(lum*w)` is at most 1 per channel, so the output `straight_col*ga, ga` is valid
    premultiplied.
  - It is composited *under* the frame (`big + glow*(1 - a)`), and the aura goes under both.
  - The glow alpha fades to 0 at the outermost pixel (0.08·side ramp).
  - With the global `strength: 0`, `aura()` returns an all-zero layer (alpha 0), so no pool remains.
- **Hard edges.** I scanned every frame of every clip for long straight alpha steps in translucent areas. The only
  structure found is the ground-light base under the feet (row about 266, about 107 px), a V2 design feature. It is
  soft on white and blue backgrounds (inspected). There is no panel-boundary cut: the panel layers have alpha 0 on
  their border rows and columns, and the panel sits well inside the 643 px square.
- **V2 path.**
  - With `stage={}` the glow is `None`, `edge_margin` is 0 and `effects` only gates the glow, so the code is V2's.
  - I re-rendered with `cp.V2_FRAME` and `cp.V2_STAGE` against the V2 atlas taken from git
    (`git show b73bd26c:uri_ui/assets/companions/ember/{idle,depleted}.webp`):

    | Clip and frame | Mean absolute difference | Max |
    |---|---|---|
    | idle 0 | 0.0022 | 0.059 |
    | idle 7 | 0.0021 | 0.059 |
    | depleted 0 | 0.0010 | 0.066 |
    | depleted 7 | 0.0010 | 0.059 |

    This confirms `diag_v21.json`.
- **Decoding.**
  - I re-ran `decode_v21.py p3` and `q2`. Both `*_decoded.md` files were unchanged afterwards, and pack integrity is OK.
  - Every number in P3_RESULTS and Q2_RESULTS matches the decoded tables, except the value noted in R2-02, which
    comes from the gates file, not the decoder.
  - The Q2 transparent-build images match the shipped atlas frames through `app_view` (mean absolute difference about
    0.31/255).
- **Raw answers and access.**
  - `p3_raw` and `q2_raw` `SHA256SUMS.txt` verify.
  - The answer JSONs are byte-identical to the scratchpad originals.
  - My own parse of all 6 transcripts finds tool use only on each reviewer's own `pack_rN` and `<round>_raw`
    (Read/Write only; 36 reads for P3, 84 for Q2).
- **Performance.** The 05 transparent table matches `perf_transparent/summary.json`. `lease_checks.txt` shows 12/12
  held with `ours=True` and `brain_resident=0`. The machine lease history shows benchmark pid 17660 holding the lease
  08:19:39-08:25:51Z.
- **Lease extract.** All 15 lines of `lease_history_extract_0700_0800Z.txt` match
  `%LOCALAPPDATA%/URI/gpu/history.jsonl`. Host pid 6384 (session `uri-fire-companion-v2-rt`) held the lease
  07:37:03-07:40:13Z. The coexistence turns are stamped 07:39:40-07:40:03Z in `observations-first.json`.
- **Tests.**
  - `full_flutter_test_final.json` has 588 successes not skipped, 5 skipped, 0 failures, and `done success=true`.
  - The 8 `ember_transparency_test.dart` tests pass.
  - `e792ddc8..33459fa8` changes only docs and test evidence, so the suite result applies to the final code.
- **Boundaries.**
  - `git diff --name-only b73bd26c..33459fa8` shows no file under `uri_ui/lib` and no Core, Runtime or shared-host
    file (`living_companion.dart`, `companion_presence.dart`, `companion_orb.dart`).
  - The only `uri_ui` changes outside the assets are `test/living/ember_transparency_test.dart` and
    `tool/capture/run_ember_perf_v21.ps1`.
  - `boundary_check.txt` agrees, although it omits the pack images (see R2-10).
- **UI V2 candidate (`uri-ui-v2-final-repair` @ `316e6475`, read only).** The claims hold:
  - `companion_window_adapter.dart:47-49` sets `setAsFrameless`, `setBackgroundColor(Colors.transparent)` and 440x680;
  - `living_companion.dart:106` computes `scale = presenceScale(id) * look.size * presentationScale`, with `SoftDisc`
    -> `CompanionOrb` at line 119;
  - `living_shell.dart:653` sets `presentationScale` to 1.85 only for Solar in companion mode, and only when
    `services.visualV2` (07 omits the visualV2 condition);
  - there is no `CompanionIdentity.ember`, no `ember_companion.dart` and no `assets/companions` folder.

  Stage 2 is correctly marked PENDING, and nothing about UI V2 integration is presented as done.

## R1 findings - recheck

| ID | Status | Note |
|---|---|---|
| R1-01 | DISCLOSED | **Changed:** FINAL:57-58 no longer says "exactly as the host computes them"; it gives the 316 px box and the 5.5/255 figure. C-4 item 5 and `diag_v21.py` `live_check` were added. **Still open:** `app_view` still uses `#130F0B`, and the live check scores only the inner disc (mask > 0.5), where the surround barely matters (0.0216 against 0.0228). It does not test the surround approximation itself (R2-09). |
| R1-02 | REPAIRED | 01 F-1 and FINAL section 2 item 2 now say the share explained is "not isolated" because the rubric and panels changed. |
| R1-03 | REPAIRED | **Changed:** Q1_RESULTS item 2 states that Q1 re-scored P1's identical images. "No artwork can pass" is withdrawn in P1_P2, 01 and FINAL. **Still open:** the "±2 points" uncertainty it introduced is now contradicted by the new rounds (R2-01). |
| R1-04 | REPAIRED | Q1_RESULTS item 1 reads "11 of 12 within 1; joyful r3 -2.0". FINAL:69-70 reads "equal in P1 and P2, 0-1.1 (state means) in Q1". |
| R1-05 | DISCLOSED | Disclosed in 01 F-2 and FINAL section 10 item 6. The code is unchanged. Exposure is reduced: the textured backdrop is now used only in depleted's 60 % haze. |
| R1-06 | DISCLOSED | **Changed:** item 2's wording is fixed ("with V2's `frame` and no `stage`"), and item 1's override is documented in 01. **Still open:** the per-clip `motion.aura` value is still dead apart from the `<= 0` guard, and the transparent build computes an all-zero aura layer for every clip. Harmless. |
| R1-07 | REPAIRED | `scripts/fire_companion/diag_v21.py` and `evidence/diagnosis/diag_v21.json` reproduce both numbers. Its V2 atlas defaults to an external worktree path (R2-09); I reproduced the same values from the git blob. |
| R1-08 | REPAIRED | 05 corrects "throughout" (pair 1 Ember 115.3). The lease is evidenced by the history extract, which I verified against the machine history. |
| R1-09 | REPAIRED | 06 corrects the greeting state sequence and cites `first-16` for `BRAIN_UNAVAILABLE`. |
| R1-10 | REPAIRED | The FINAL verdict table and section 6 state the rc=1 PRE-2 teardown failure for runs 2 and 3. |
| R1-11 | REPAIRED | C-4 items 1-4 record the lock-time gap, the transcripts in place of handback files, V2's worst-frame source and the prompt wording. Plan line 26 is reworded. The session-order claim in C-4 item 1 is not evidenced by a committed artefact; it is stated as such. |
| R1-12 | REPAIRED except one item | `boundary_check.txt` was added. The test summary names commit `e792ddc8`. The `_incoming$3` slip is explained in 05. **Open (trivial):** the usage line in `uri_ui/tool/capture/run_ember_perf_v21.ps1:5-6` still omits the mandatory `-Baked`. The ps1 file was not touched in the range. |
| R1-13 | REPAIRED | The worktree is clean. The glow and `edge_margin` changes were committed in `73e84a6d`. Protocol edits after Q1 are logged as C-2 to C-4. |
| R1-14 | REPAIRED | FINAL no longer says "everything else delivered". AC-R2 and AC-R3 are listed with their real state. Minor: the AC-R2 row says R1 was "repaired", while R1-01, R1-05 and R1-06 are disclosed rather than repaired and R1-12 has one open item. |

## New findings

### R2-01 (medium): panel variance is understated; Q2 re-scored identical images, which is not disclosed

- **Where:**
  - `Q2_RESULTS.md:62-66` ("about 6 points below [in P3]. That is consistent within the about +-2 point uncertainty
    per round mean");
  - `FINAL_QUALIFICATION_REPORT_V21.md:71-73` and `186`;
  - `Q1_RESULTS.md` item 2 ("about +-2 points");
  - `07_UI_V2_COMPATIBILITY_V21.md:58-60`.
- **Evidence:** I compared candidate images across rounds (reviewer 1 packs, mean absolute difference over RGB).
  - **Q2 against Q1, pixel-identical (0.0) for `painting_app`, `v2_app` and `v21_frame_only` in all four states.**
    Their scores moved between the two panels:
    - control +2.0 to +3.3 (85.7-86.8 -> 88.3-89.3);
    - `v2_app` +3.7 to +4.9 (72.3-73.5 -> 77.0-77.8);
    - `v21_frame_only` +2.5 to +3.4.
  - **Q2 against P3, the transparent candidate:**
    - Q2 `v21_worst` is pixel-identical (0.0) to P3 `t1_glow` in idle, joyful and fierce. It scored 79.7 in P3 and
      85.3-85.8 in Q2, a rise of **+5.6 to +6.1**.
    - Depleted differs from P3 `t3_glow_haze60` only by `edge_margin` (0.28/255). It scored 79.0 in P3 and 86.8 in Q2,
      a rise of **+7.8**.
  - **P3's `painting_app` equals Q1's (0.0).** Across P1, P3, Q1 and Q2, the same control image therefore ranged from
    85.7 to 89.3.
  - Within-panel "transparency cost" on identical stimuli was about 6.3 in P3 and about 3 in Q2.
- **What is wrong:**
  - Shifts on identical stimuli of up to 4.9 points between Q1 and Q2, and up to 7.8 between P3 and Q2, are well
    outside "±2 points per round mean".
  - The cost estimate "2.5-6 points" is itself panel-dependent by about 3 points.
  - Neither Q2_RESULTS nor FINAL says that Q2's transparent images are the P3 `t1` images, or that Q2's control, V2
    and frame-only images are Q1's.
  - The NOT MET verdict is unaffected: every round is below 90, and the threshold is not bent.
  - The owner's waiver decision, however, rests on "within a few points of the painting", and that statement carries
    this larger uncertainty.
- **Repair:**
  - State in Q2_RESULTS and FINAL which Q2 images are pixel-identical to Q1 and P3 images.
  - Report the observed shifts on identical stimuli (up to about 5 for Q1 to Q2, about 6-8 for P3 to Q2) as the
    measurement uncertainty, in place of ±2.
  - Present "transparency cost" as "about 3 (Q2) to 6 (P3) points, panel-dependent".

### R2-02 (low): the T2 worst value is misreported (79 against 73 in the committed gates)

- **Where:**
  - `07_UI_V2_COMPATIBILITY_V21.md:67` ("worst 79, depleted haze") and `:42-43` ("alpha <= 0.31 outside the figure");
  - `FINAL_QUALIFICATION_REPORT_V21.md:95`;
  - the `_comment` in `expressions.json` for the depleted clip stage.
- **Evidence:**
  - The committed `evidence/transparency/transparency_gates.json` gives depleted `ring_max` = **73** (0.29). My re-run
    is identical.
  - The atlases have not changed since `73e84a6d`, where the gates file was committed.
  - The 79 probably comes from a pre-`edge_margin` export. The error is in the conservative direction.
- **Repair:** quote 73 (0.29), or cite the source of 79.

### R2-03 (low-medium): live run 3 is undocumented in 06, its provenance is thin, and it exercised only the depleted clip

- **Where:**
  - `06_LIVE_QUALIFICATION_V21.md:29-30`;
  - `07_UI_V2_COMPATIBILITY_V21.md:71` and `:123`;
  - `FINAL_QUALIFICATION_REPORT_V21.md:108` and `153`;
  - `evidence/live/run3_returning_transparent/`.
- **What is wrong:**
  1. 06 says the transparency build "is covered by the live check in section 'Transparency build' below". No such
     section exists, and run 3 is not described anywhere in 06.
  2. `run3_returning_transparent/returning-brain_host.json` is byte-identical to `run2_returning/`'s copy. It is the
     run-1 recovery host record (host pid 4280, `updated_at` 07:42:35Z), not a run-3 artefact.
  3. Nothing in run 3 records the commit or atlas hash of the build. The timing (08:35Z, after `73e84a6d` at
     08:12:49Z) is consistent but is not proof.
  4. With the Brain stopped, run 3 showed only `unavailable`, which is the depleted clip with haze. The glow-only
     clips (idle, joyful, listening and the rest) were never seen in the live app on the transparent build. For them,
     B7 rests on the perf harness screenshots (`perf_transparent/v21_ember_r*/ember_*.png`, which do show them).
- **Repair:**
  - Add the "Transparency build" section to 06, covering run 3's journeys, rc=1 PRE-2, the build commit and an
    atlas-hash check.
  - Drop the stale `returning-brain_host.json` or label it.
  - State that only depleted was seen live.

### R2-04 (low): transparency tests can pass vacuously in parts, and their scope is narrower than the wording suggests

- **Where:** `scripts/fire_companion/transparency_check.py:69-120`; `uri_ui/test/living/ember_transparency_test.dart:78`;
  `07:68-70`.
- **What is wrong:**
  1. The Python check has no non-empty guard. A blank or fully transparent atlas passes T1-T4. The Dart test does
     guard this (`opaqueFraction > 0.005`).
  2. For depleted, T4 is vacuous. `semi_rim_px_median` is 0, because the haze keeps alpha at 128 or above next to the
     figure. No rim pixels are tested, and the threshold falls back to 5 px.
  3. T5 checks only the patch's outer edge and that the patch lies inside the cell. It does not check how the patch
     composites over the base frame.
  4. The Dart test renders `still: true`, which is frame 0 only with no blink patch (`ember_companion.dart:605-614`).
     It therefore checks 8 frames, not the 456. 07 does not claim all frames for it, but "B1 ... Flutter test" should
     be read with that scope.
  5. "It fails on the painted atlases (verified before the change)" has no committed output.
- **Repair:**
  - Add a non-empty assertion (for example, at least 0.5 % opaque) to the Python gates.
  - Report T4 as "not applicable" when `semi_rim_px` is 0.
  - Commit the failing run on the painted atlases, or drop the claim.
  - Optionally add a Dart case with blinks on (non-still) for one clip.

### R2-05 (low): the depleted haze is a translucent backdrop panel that the gates cannot detect; B2 PASS needs the qualifier

- **Where:** `07_UI_V2_COMPATIBILITY_V21.md:118` and `:120`; `FINAL:127`.
- **Evidence:**
  - In the shipped depleted frame 0, 58.6 % of the cell has alpha above 0.1 and 26.7 % above 0.5.
  - Composited on white, it reads as a grey rounded box around the figure; on blue, as a dark patch. I checked frame 0
    over white and blue.
  - It passes T2 (128) and T3 (opaque only) by design, because those gates allow up to half-opaque atmosphere.
  - B4 correctly asks for owner sign-off.
  - B2 ("no permanent opaque rectangular background: PASS") is literally true, since the haze is not opaque and not
    rectangular. It cites "contrast sheets" as evidence, though, and those show the panel.
- **Repair:** add the depleted haze qualifier to B2 as well (for example, "PASS; depleted carries a translucent
  backdrop, see B4"), so that the owner sign-off covers both.

### R2-06 (low): "Existing Ember tests 44/44" counts the 8 new tests

- **Where:** `07_UI_V2_COMPATIBILITY_V21.md:70`; `FINAL_QUALIFICATION_REPORT_V21.md:106`.
- **Evidence:** the final suite has 36 tests in `ember_companion_test.dart` and 8 in `ember_transparency_test.dart`.
- **Repair:** write "existing Ember tests 36/36, new transparency tests 8/8".

### R2-07 (low): two rounds ran after Q1, and the deviation from section 8 is not named as one

- **Where:** `03_FIDELITY_PROTOCOL_V21.md` section 8 ("At most one repair and one further round (Q2) after Q1"), C-2
  and C-3; `Q1_RESULTS.md` "Protocol consequence".
- **What is wrong:**
  - P3 (exploratory) and Q2 both ran after Q1.
  - P3 was used to choose the configuration that Q2 then qualified (glow for every clip, 60 % haze for depleted).
  - C-2 calls P3 exploratory, but does not say it exceeds section 8's round limit.
  - Q1_RESULTS' "Protocol consequence" mentions only Q2.
  - The owner directive makes this defensible, and no threshold was changed.
- **Repair:**
  - Add one sentence to C-2: "P3 is an additional round beyond section 8, justified by OD-V21-2; it selected the
    configuration measured in Q2."
  - Mention P3 in Q1_RESULTS.

### R2-08 (low): P3's "the haze made no difference" is an instrument-resolution result

- **Where:** `P3_RESULTS.md:25-26`; `07:43-44` ("Other clips gained nothing from haze in P3").
- **Evidence:**
  - In idle, joyful and fierce, `t1`, `t2` and `t3` received identical per-reviewer scores (for example, 80/80/80 for
    all three).
  - The images differ by 3.1-8.4/255 mean absolute difference (t1 against t3: 5.4, 8.4 and 4.9).
  - This is the class-scoring already noted in R1-03.
- **Repair:** write "reviewers did not distinguish the haze levels in idle, joyful or fierce". The choice of glow only
  remains reasonable on other grounds: it looks cleaner on light desktops.

### R2-09 (low): `diag_v21.py` reproducibility and scope

- **Where:** `scripts/fire_companion/diag_v21.py:66-77` and `:91-92`.
- **What is wrong:**
  - The V2 reproduction reads `idle.webp` from an external worktree
    (`C:\Users\cheta\Development\uri-fire-companion-v2\...`), not from this repository's history. The value is
    correct: I reproduced it from `git show b73bd26c:...`.
  - `live_check` scores only `mask > 0.5`, the inner disc. That is where the canvas approximation matters least, and
    the two surrounds differ by only 0.0012 there. It cannot test R1-01's surround concern.
  - The script writes into the repository with no `--out` option.
- **Repair:**
  - Default the V2 atlas to `git show b73bd26c:uri_ui/assets/companions/ember/idle.webp`.
  - Add a fade-ring MAD (mask 0.05-0.5) to `live_check`.
  - Add `--out`.

### R2-10 (low): evidence housekeeping

1. `perf_transparent/` has `census_after.json` but no `census_before.json`, although 05 says "the same series and
   harness".
2. "The bundled `idle.webp` was byte-checked against the committed asset" (05) has no committed output.
3. `boundary_check.txt` omits the reviewer pack images (about 970 PNGs), while FINAL:162 says it "lists every file
   changed since V2's `b73bd26c`". The protected-path conclusion is still correct.
4. 07:81-82 omits that `presentationScale` 1.85 also requires `services.visualV2`.

- **Repair:** add the missing census and hash outputs or reword, change "every file" to "every file except the
  reviewer pack images", and add the visualV2 condition.

## Summary against the review criteria

| Criterion | Result |
|---|---|
| Transparency code correctness | Premultiplied-correct glow and compositing. No hard edge or opaque background in any frame (gates plus my own scan). The V2 path reproduces V2 (git blob check). |
| Transparency tests | They test what they state, and ALL PASS reproduces. There are vacuity and scope gaps (R2-04), and the gates cannot see a translucent backdrop (R2-05). |
| Fidelity P3 and Q2 | Decoding reproduces, integrity and access are clean, and the numbers match. The uncertainty is understated, and Q2's reuse of identical images is undisclosed (R2-01). There are protocol notes (R2-07, R2-08). |
| Perf, lease and live | Perf and lease are verified. Live run 3 is under-documented and depleted-only (R2-03). |
| UI V2 claims | Verified against `316e6475`. Stage 2 is honestly PENDING. |
| Boundaries and suite | Confirmed: no `uri_ui/lib`, Core, Runtime or shared-host change; 588/5/0 at `e792ddc8`, and the final commit is docs-only. |
| R1 | 10 repaired, 3 disclosed. R1-12 has one trivial item open (the ps1 usage line). |

## Limits of this review

- Read-only.
- No Flutter build or test was run. The suite and live results were read from the committed evidence.
- The local transcripts were parsed from their committed hashes and the local `.gz` files.
- This review is not lifecycle acceptance (AC-R3 remains BLOCKED).
