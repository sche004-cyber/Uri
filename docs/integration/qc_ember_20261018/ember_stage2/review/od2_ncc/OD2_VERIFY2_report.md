# OD2_VERIFY2 - independent review of 03_EMBER_OD2_PROVENANCE.md, revision 2

Record: D:/uri-dev/uri-integ-ember/docs/integration/qc_ember_20261018/03_EMBER_OD2_PROVENANCE.md at 401a2964. The file is unchanged at branch tip a6f47902: `git diff 401a2964 HEAD` on the file is empty.
Reviewer: read-only. Nothing was edited, committed, pushed or uploaded. Evidence was extracted from V1 commit 8a1438ec into this folder.

## Acceptance criteria
- AC1: each fact F1-F8 is supported by the artefacts.
- AC2: I1-I4 are labelled as inferences and are not overstated.
- AC3: the status and policy text matches the owner policy. OD-2 is a deferred distribution gate and not an integration blocker. No replacement or further research is demanded. Nothing claims OD-2 is resolved.
- AC4: the corrections section is accurate.
- AC5: the terms summary makes no legal conclusion.

## Verdict: ACCEPT WITH FINDINGS (1 MEDIUM, 4 LOW, 3 INFO). The artefacts contradict none of the facts.

## Facts check (documented = seen by me in the artefacts)
| # | Result | Evidence |
|---|---|---|
| F1 | VERIFIED, with one wording error (L1) | shot.jpg is 1080x2340 RGB. The string is in the EXIF **Software** tag: 'Android BP2A.250605.031.A3.S906EXXSEGZH4'. There are no Make or Model tags. DateTimeOriginal is 2026:10:14 09:23:37 +05:30. The URL bar shows 'chatgpt.com/c/6acef' (truncated). The image is in a full-screen viewer with close (X) and bookmark icons. The embedded image fills rows 746-1825 (1080x1080). |
| F2 | VERIFIED | The card under the image shows the Fiverr favicon, 'fiverr', and 'Digital illustration - Hire a Freelance Illustrator ...' (truncated). |
| F3 | NOT VERIFIED by me, because I did not access the web (see L2) | The visible card text is a truncated prefix. That prefix is consistent with the stated page title. F3 rests on a web page, not a repository artefact. |
| F4 | VERIFIED | A faint scribbled mark sits at about (830,850) of the 1080x1080 image, right of the figure at ground level. |
| F5 | VERIFIED and quantified | The sheet is 896x1200. A 4-point sparkle sits at about (775,1079), lower right of 04 DEPLETED. In the IDLE panel the mark is at about (414,512) in sheet coordinates, in the same position relative to the figure (right, ground level). It lies inside the rig.json idle erase rectangle (crop y0=95, so sheet 398,497-448,525). Numbers below. |
| F6 | VERIFIED, with imprecise count wording (L3) | layers.py reads the sheet (SHEET constant) and applies the `erase` rectangles before matting. The rig.json comment says "'erase' rectangles are inpainted before matting (artist signature, generator mark)". The idle erase is [398,402,448,430]. The depleted erase is [292,422,362,490], which is sheet 740,1047-810,1115 and contains the sparkle. animate.py says "Every pixel the companion shows comes from the painting". The asset directory holds 11 .webp files plus manifest.json, 12 files in all; manifest.json is not an image derivative. I did not re-render the assets. |
| F7 | VERIFIED | PROVENANCE.md at 8a1438ec records the video as not committed, with its sha and size. video_frames/ holds 11 jpgs (contact_*, key_*, vcrop_*). |
| F8 | VERIFIED within the limits of the search | `git log --all --grep` for fiverr, commission, purchase and licen[cs]e finds no Ember purchase or licence commit. `git grep` for 'fiverr' at HEAD hits only the OD-2 docs, receipts and reviews. 'chatgpt' hits only unrelated files (skill text, process census JSON). No prompt, file id or generation record was found. |

### F5 quantitative check (scratch ncc.py)
- **Template:** the character region of the screenshot image (x 200-900, y 150-910 of the 1080x1080 embedded image), in grayscale.
- **Matching:** for each sheet panel, a brute-force search over scale (0.24-0.78) and offset found the best NCC. Both crops were then resized to 128x128 and NCC was recomputed.
- **Why gradient NCC:** grayscale NCC is inflated because every panel shares a dark background with a bright head. Gradient-magnitude NCC compares structure instead.

| Panel | search NCC | NCC 128x128 | gradient NCC 128x128 |
|---|---|---|---|
| 01 IDLE | 0.907 | **0.915** | **0.642** |
| 02 JOYFUL (control) | 0.581 | 0.590 | 0.170 |
| 03 FIERCE (control) | 0.576 | 0.587 | 0.151 |
| 04 DEPLETED (control) | 0.403 | 0.393 | -0.033 |

**Reading:**
- IDLE matches strongly and selectively: its gradient NCC is about 3.8x the best control.
- IDLE is not pixel-identical (gradient NCC 0.64). That fits a re-rendered (image-to-image) derivative, not a crop.
- This supports F5 "closely matches" and I4.
- Side-by-side image: ncc_compare.png.

## Inferences (AC2): PASS
I1-I4 sit under "Reasonable inferences (not proven)", and each is hedged. I1 says outright that it does not prove retrieval or ownership. I3 is explicitly inconclusive. INFO-1 covers I2. I4 now has the numbers above behind it.

## Status / policy (AC3): PASS except M1
The header matches the owner policy:
- OD-2 is a deferred distribution-release gate and not an integration blocker.
- No external distribution until the rights review is done.
- OD-2 is not reopened without new material risk.
- The rule applies to future companions too.

It also says "no replacement or further owner research is required now". The revision 2 evidence standard is in the header and in E4: a Fiverr card is not conclusive, recollection is not verified provenance, and a negative reverse search proves nothing. Nothing claims OD-2 is resolved; chain link 1 is marked UNRESOLVED. Replacement appears only as a condition in the §6 resolution rule ("only then").

## Corrections (AC4): accurate but incomplete (L4)
Revision 1 did say "UNPROVEN; contradicted by repository evidence" (0a0cddbe lines 3 and 35). The correction is accurate and git keeps the history. The PROVENANCE.md wording is quoted correctly.

## Terms (AC5): PASS (INFO-2)
The section is labelled a summary, says "confirm against the current official text", and the record says "Not legal advice". It draws no conclusion on whether the owner holds rights.

## Findings
- **M1 (MEDIUM): §8 Boundaries contradicts the status header.**
  - Problem: "Ember stays outside canonical and unpushed while OD-2 is unresolved" makes OD-2 a precondition for integration. That goes against the owner policy and against the record's own header ("Not an integration blocker"; canonical integration needs technical acceptance plus owner authorization).
  - Fix: write "Ember is not distributed externally until the distribution-phase rights review is complete. Canonical integration requires technical acceptance and separate owner authorization; OD-2 does not block it."
  - If pushing to a remote counts as distribution, say so explicitly and tie it to the distribution gate, not to OD-2 being resolved.
- **L1 (LOW): F1 says "EXIF model string".**
  - Problem: the value is in the EXIF Software tag ('Android BP2A...'), and there is no Model tag.
  - Fix: write "EXIF Software tag 'Android BP2A.250605.031.A3.S906EXXSEGZH4'; DateTimeOriginal 2026-10-14 09:23:37 +05:30".
- **L2 (LOW): F3 is not a repository fact.**
  - Problem: section 2 is titled "from repository artefacts", but F3 rests on an external web page. The card text is truncated, so only its prefix can match.
  - Fix: mark F3 "external, checked <date>; card text truncated - prefix match only", or move it into a sourced note.
- **L3 (LOW): F6 says "12 shipped Ember assets are pixel-level derivatives".**
  - Problem: 11 of the files are .webp images. The 12th is manifest.json, which is metadata and not a pixel derivative.
  - Fix: write "the 11 image files (9 clip atlases, blink atlas, thumbnail) are pixel-level derivatives; manifest.json describes them".
- **L4 (LOW): §7 misses other places that still say "Fiverr illustration".** They are:
  - the OD-2 question text in `docs/companions/fire/00_PLAN_AND_ACCEPTANCE_CRITERIA.md` (8a1438ec): "Fiverr illustration";
  - `01_RESEARCH_AND_APPROACH.md` §2.3, as quoted in the investigation: "AI-generated derivatives of an illustration listed on Fiverr";
  - `ember_stage2/review/OD2_licensing_investigation.md`: "The original painting is a third-party illustration found on a Fiverr listing";
  - `02_EMBER_STAGE2_INTEGRATION_RECEIPT.md` §6, lines 84 and 93; option A reads "confirm rights to the Fiverr illustration".

  Fix: list these in §7 as superseded by §2. The historical docs do not need editing.
- **INFO-1:** I2's wording is acceptable. "That seller would then be the likely rights holder" is doubly conditional. A gig thumbnail can itself be reused art, and the record already says the card does not establish authorship.
- **INFO-2:** The §5 OpenAI summary cites a third-party summary site (conductatlas.com), not openai.com; consider citing the official Terms of Use instead. The Google sentence "does not remove rights a third party may hold" is a hedged general statement, not a conclusion about this case.
- **INFO-3 (not in the record; optional):** sheet.png contains an EXIF block (zTXt 'Raw profile type APP1') with Software='Picasa'. It changes no fact. It could be recorded as a metadata observation: it suggests the file went through Google Photos/Picasa tools, but it is not evidence of authorship.

## Documented vs inferred (this review)
- **Documented:** the F1, F2 and F4-F8 observations, coordinates, EXIF values, erase rectangles, file counts, NCC numbers, revision 1 wording and git searches.
- **Inferred:** that the NCC pattern points to image-to-image derivation (I4).
- **Unverified: F3.** I did no web check. This does not affect the verdict, because F3 only corroborates.
- **Unverified: pixel derivation of the shipped assets.** I did not regenerate them, only read the code. This does not affect the verdict.

## Scratch artefacts (local only, not uploaded)
shot.jpg, sheet.png, PROVENANCE.md, shot_img.png, shot_zoom_r.png, idle_zoom_r.png, gem_zoom.png, ncc.py, ncc_*.png, ncc_compare.png
