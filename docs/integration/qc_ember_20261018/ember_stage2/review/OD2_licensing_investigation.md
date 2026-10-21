# OD-2 (Ember reference-art licensing): evidence report

Read-only research, 2026-10-18. Repo `C:/Users/cheta/Development/Uri/_V1`. I made no edits, commits, checkouts or pushes.

## Acceptance criteria (set before drafting)
1. Give the exact OD-2 text and where it was first defined, quoted from git objects.
2. State the provenance of the reference art from repository evidence only. Say "unknown" where the evidence stops.
3. Show from the pipeline source whether the shipped atlases are derived from the references.
4. Account for the third-party inputs in the shipped path.
5. Use `git` to list the history commits and paths that carry reference art or reviewer packs, and check the effect of a squashed port.
6. Give the options and mark which ones only the owner can decide. Give no legal conclusions.

## 1. What OD-2 says and where it comes from
- **First defined:** `docs/companions/fire/00_PLAN_AND_ACCEPTANCE_CRITERIA.md`, line 14. The file entered history in V1 commit `8a1438ec` and is unchanged at `d6a83131`. It sits under "Owner decisions recorded before work (2026-10-14)".
  - The question: "Licence of the reference art (Fiverr illustration; emotions sheet carries a Gemini mark)".
  - The recorded owner answer: "I hold rights / will license", followed by "not independently verifiable by the implementer."
- **`reference/PROVENANCE.md`:** "the owner holds or will obtain the rights to this character". It adds that everything in `companion_art/fire/` and `uri_ui/assets/companions/ember/` is derivative, and that distribution should wait for the licence.
- **V2 plan, AC-12:** reference and derived art must not enter any pushed history, and any push needs OD-2 resolved first.
- **Status now:** unresolved. The following all list OD-2 as open:
  - `v21/FINAL_REPORT_V21_FINAL.md` §9 and §11 item 6;
  - the handoff `INTEGRATION_HANDOFF_UI_V2.md` §11 (`4a70d9e7`): "No push of any branch containing them until OD-2 is resolved";
  - the integration receipt `v21_integ/01_QUALIFICATION_RECEIPT.md`, lines 8 and 128;
  - memory notes `uri-fire-companion-ember*.md` and `uri-ember-v21-integ-20261018.md`.
- **Two ambiguities:**
  - The owner's answer is "hold **or** will license". The record does not say which applies.
  - A different OD-2 (M36 harness rulings, `e26d98c5`) uses the same ID. It is unrelated.

## 2. Who made the reference art
| Item | Repository evidence | Creator / terms |
|---|---|---|
| `uri_emotions_sheet.png` (four panels: Idle, Joyful, Fierce, Depleted) | PROVENANCE: "Owner upload, 2026-10-14", plus "Carries a Gemini generator mark". I checked the image: a sparkle mark sits at the lower right of the Depleted panel. | Very probably AI-generated with Google Gemini, going by the mark and `01_RESEARCH_AND_APPROACH.md` §2.3 ("AI-generated derivatives of an illustration listed on Fiverr"). Who prompted it, which account, and which Gemini terms apply are **unknown**. |
| `idle_source_screenshot.jpg` | PROVENANCE: "image search result attributed to a Fiverr illustration listing". I checked the image: it is a phone screenshot of an image viewer on chatgpt.com, captioned "fiverr — Digital illustration - Hire a Freelance Illustrator…". | The original painting is a **third-party illustration** found on a Fiverr listing. The artist's name, the listing, and any purchase or licence are **unknown**: the repo records nothing. The Idle panel of the sheet closely matches this illustration in pose, palette, tail and composition, and a faint signature-like mark appears in both images. |
| `motion_reference_gemini.mp4` (not committed, hash only) | PROVENANCE says it came as `gemini_generated_video_2821f24a.mp4` and carries a Gemini mark. | Gemini-generated, used for motion only. 11 key frames and contact sheets extracted from it **are** committed under `reference/video_frames/`. |

There is no evidence that the owner made or commissioned the art, and no evidence of a Fiverr purchase. "Owner-made" and "commissioned" are both unsupported.

## 3. How the atlases were made: they are derivative
- **Shipped atlases:** the manifest records `"source": "companion_art/fire_v2 (painting-derived 2.5D)"`. The 12 asset blobs are byte-identical at `d6a83131` and at `0b853288`, about 13.3 MB in total.
- **Pipeline:**
  - `fire_v2/layers.py` loads `docs/companions/fire/reference/uri_emotions_sheet.png` directly and cuts each panel into RGBA layers.
  - `fire_v2/animate.py` docstring: "Every pixel the companion shows comes from the painting".
  - V2 research: "The source of the pixels has to be the painting." V2.1 also brings back the painting's own background ("painted backdrop").
- **Artist mark removed:** `rig.json` and V2 research §4 say "The artist signature (idle) and the generator mark (depleted) are inpainted out." The shipped art therefore has the artist signature and the Gemini mark removed. This is a significant fact for the owner to weigh. I give no legal view.
- **Conclusion from the evidence:** the shipped atlases and `thumbnail.webp` are pixel-level derivatives of the reference sheet. That sheet in turn appears to derive from a third-party Fiverr illustration.
- **V1 art:** the V1 Blender art (`companion_art/fire/ember.blend` and the V1 atlases) is a 3D redraw of the same character design. It is in history, not in the candidate tree.

## 4. Third-party inputs in the shipped path
- **Runtime:** `ember_companion.dart` imports only Dart and Flutter SDK libraries. The candidate makes no `pubspec` change apart from the asset folder. No new packages, fonts or models.
- **Offline tools:**
  - The V2 pipeline uses Python with numpy, Pillow and scipy (Pillow writes the WebP).
  - V1 used Blender 5.2.2 (portable zip, SHA-256 checked, OD-7) and ffmpeg for the video frames.
  - **No licence record for these tools exists in the repo.** None of them is redistributed in the shipped assets.
- **Inside the art:**
  - PROVENANCE says V1's Blender asset uses no third-party textures, add-ons or fonts.
  - The atlases are cut from the sheet's panels. The sheet's text labels are excluded according to `04_FIDELITY.md`; I did not verify this frame by frame.
- **Not verified:** I did not inspect every atlas frame for leftover marks or text.

## 5. History and what a push would carry
The candidate `milestone/ember-v21-integ-20261018` @ `0b853288` adds 78 commits over canonical `348677b7`, including all of the Ember V1 to V2.1 history through merge `ce972cc2`.

**Material in history that is not in the candidate tree:**

| Path | Commit(s) that added it |
|---|---|
| `docs/companions/fire/reference/**` (sheet, Fiverr screenshot, 11 video frames, PROVENANCE) | `8a1438ec` (V1) |
| `docs/companions/fire/v2/evidence/fidelity/**` (reviewer packs) | `8a585108`, `90f0f8a2`, `fce51708`, `a86ed350`, `1fcddab3` |
| `docs/companions/fire/v21/evidence/fidelity/**` (reviewer packs, FP-21R) | `9933ca2b`, `90ae2248`, `73e84a6d`, `3a09d438`, `e792ddc8`, `6adf8fbf`, `23fb2878`, `269821cd`, `0484afdc` |
| `v21/evidence/demos/before_after.jpg` (shows the painting) | `9933ca2b` |
| `companion_art/fire/` (V1 Blender art) and V1 `evidence/` | `8a1438ec` and the V1 review commits |

**The candidate tree itself:**
- AC-3 holds: no reference blob appears in it (I matched blob IDs, none found). Reviewer packs and `before_after.jpg` are also absent.
- It still contains derived Ember imagery:
  - the 12 shipped assets;
  - `companion_art/fire_v2/*`: scripts plus `rig.json`, which holds the signature-erase coordinates;
  - `v21/evidence/demos/*.gif`, `final/haze`, `size_crop`, contrast JPGs and live screenshots;
  - `v21_integ/live/**`.

**Remote state:** no remote-tracking ref contains `8a1438ec`, `d6a83131` or `0b853288`. Canonical `cd4a7963` and `348677b7` are on `uri-repo/integration/git-sync-20261008`. Remote refs reflect the last fetch only.

**Effect of a squashed port:** a single commit on canonical containing only the shipped files would carry no reference or reviewer-pack blobs in what gets pushed.
- Shipped files means: the Dart code, tests, `pubspec`, and `uri_ui/assets/companions/ember/`, optionally with `companion_art/fire_v2` scripts.
- It would still push the derivative atlases.
- It **conflicts with the handoff** (§12: "keep Ember history (merge, no rewrite)"). That handoff rule needs an owner waiver.
- A squash of the whole `0b853288` tree would also push the derived evidence images listed above.

## 6. Options

| Option | Effect | Evidence-based assessment | Owner-only? |
|---|---|---|---|
| A. Owner confirms rights to the reference and its derivatives, then push the candidate as is | Pushes the full history, including the Fiverr screenshot, the Gemini sheet and the reviewer packs | Possible only if the owner actually holds rights covering both the Fiverr illustration and the Gemini output. The repo has no proof of either. The only record is "hold / will license". | Yes |
| B. History-clean port of the shipped files only | Reference and reviewer packs stay out of pushed history | **The atlases are still derivative**, so this still needs OD-2 settled for the derived art. It reduces exposure; it does not resolve OD-2. It needs a waiver of handoff §12 (no rewrite). | Yes (rights, plus the waiver) |
| C. Local-only canonical integration, no push | Nothing published | Consistent with every recorded constraint (AC-12, handoff §11, receipt). It leaves local canonical and the remote diverged, which affects later git-sync. | Yes (integration approval) |
| D. Replace the art (licensed, commissioned, or owner-made character, or a non-derivative redesign) | Removes the dependency | Needs new art and re-qualification. Fidelity was already NOT MET against the current reference, so the fidelity target would need redefining. The scripts can be reused. | Yes (direction and budget) |
| A+B | Owner confirms rights and also prefers a clean port | Lowest exposure if rights exist | Yes |

**What only the owner can establish or decide:**
1. Whether they purchased or licensed the Fiverr illustration, and its terms: commercial use, derivatives, distribution.
2. Who generated the Gemini sheet and video, under which account, and whether those terms permit this use.
3. Whether removing the artist signature is acceptable to them, or to the artist.
4. Whether public or remote distribution (GitHub) is intended at all.
5. Whether to waive the no-rewrite handoff rule.

I give no legal conclusion. The repo has no licence, receipt or artist attribution anywhere.

## Self-check
- All quotes come from git objects at the commits named.
- The two image observations come from viewing the committed blobs, extracted to the scratch folder.
- **Unverified:**
  - the Fiverr listing and artist identity (no evidence in the repo; not fetched online);
  - Gemini terms;
  - current remote state beyond the last fetch;
  - frame-by-frame atlas content.

  None of these changes the verdict: OD-2 is open, and the shipped atlases are derivatives of third-party-origin art.
