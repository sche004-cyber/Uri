# Ember V2.1 - OD-2 provenance record (task EMBER-OD2-PROV-20261018)

**Status: OD-2 = DEFERRED DISTRIBUTION-RELEASE GATE (owner policy 2026-10-18). Not an integration blocker.**
Owner decision: "Artwork provenance and licensing clearance belong to the DISTRIBUTION phase, not routine
development. Reclassify Ember OD-2 from an integration blocker to a deferred distribution-release gate." Ember
development, qualification, review and preparation for canonical integration continue; canonical integration still
needs technical acceptance and separate owner authorization. **Ember artwork must not be distributed externally until
the distribution-phase rights review is completed.** OD-2 is not reopened during ordinary development unless new
evidence establishes a material legal or security risk. The same lifecycle distinction applies to future URI
companions and other generated visual assets.

The licensing questions below remain open and are recorded for the distribution-phase review; no replacement or further
owner research is required now. Not legal advice.

Revision 2 (2026-10-18) applies the owner's evidence standard: a Fiverr source card is not conclusive proof of
third-party ownership; the owner's recollection is not independently verified generation provenance; a negative
reverse-image search alone would not establish ownership or AI-only provenance. Revision 1 called the first link
"contradicted"; that overstated the evidence and is corrected here (history kept in git).

## 1. Statements (recorded, not verified)

- Owner, 2026-10-14 (OD-2 origin, `docs/companions/fire/00_PLAN_AND_ACCEPTANCE_CRITERIA.md` at `8a1438ec`): rights
  "held / will license".
- Owner, 2026-10-18: "The original Ember artwork was generated using ChatGPT and subsequently refined using Google
  Gemini. The artwork was not commissioned from Fiverr."
- Owner, 2026-10-18 (later): "The original Ember image was obtained through a ChatGPT conversation and subsequently
  refined using Gemini. The repository screenshot contains a Fiverr source card. The original image's provenance
  remains uncertain."

## 2. Verified facts (from repository artefacts)

| # | Fact | Evidence |
|---|---|---|
| F1 | A phone screenshot shows the first image inside a ChatGPT conversation | `docs/companions/fire/reference/idle_source_screenshot.jpg` at `8a1438ec` (1080x2340; EXIF Software tag `BP2A.250605.031.A3.S906EXXSEGZH4`, DateTimeOriginal 2026-10-14 09:23:37 +05:30; URL bar `chatgpt.com/c/6acef...`; full-screen viewer with close and bookmark controls) |
| F2 | Under the image the viewer shows a source card: a favicon, "fiverr", and "Digital illustration - Hire a Freelance Illustrator ..." | same screenshot |
| F4 | The image shows a faint signature-like mark to the right of the figure | same screenshot |
| F5 | The Gemini sheet `uri_emotions_sheet.png` (896x1200) carries a Gemini sparkle mark (lower right of the Depleted panel); its "01. IDLE" panel closely matches the screenshot image (pose, flame shape, tail curl, ground glow) including the signature-like mark at the same relative position; panels 02-04 (Joyful, Fierce, Depleted) are new variations. Measured (independent review, 128x128 after alignment): IDLE vs screenshot image grayscale NCC 0.915 / edge NCC 0.642; controls JOYFUL 0.590 / 0.170, FIERCE 0.587 / 0.151, DEPLETED 0.393 / -0.033 - strong match for IDLE only, not pixel-identical (consistent with an image-to-image re-render) | sheet at `8a1438ec`; `ember_stage2/review/od2_ncc/` |
| F6 | The 11 shipped Ember image files (9 clip atlases, the blink atlas, the thumbnail) are pixel-level derivatives of the sheet (`manifest.json` describes them); the signature-like mark (idle) and the Gemini mark (depleted) were inpainted out | `companion_art/fire_v2/layers.py`, `animate.py`, `rig.json`; `uri_ui/assets/companions/ember/manifest.json` |
| F7 | A Gemini-generated motion video (not committed) was used as motion reference; frames are in `reference/video_frames/` | `PROVENANCE.md` at `8a1438ec` |
| F8 | Nothing in the repository records a purchase, commission or licence from Fiverr, and nothing records a ChatGPT generation (prompt, generated-image output, file id) | search of history, docs, commit messages |

## 3. Reasonable inferences (not proven)

- I0 (external check, not a repository artefact): the card's visible text "Digital illustration - Hire a Freelance
  Illustrator ..." (truncated) matches the prefix of the title of Fiverr's public category page "Digital illustration -
  Hire a Freelance Illustrator Services" (sources).

- I1: A website source card under an image in ChatGPT is typical of images ChatGPT retrieved from the web; generated
  images are normally shown without a website card. This is an inference from product behaviour; no official OpenAI
  documentation of the card format was found. It does not prove the image was retrieved, nor who owns it.
- I2: Because the card names a Fiverr category page (which shows sellers' gig thumbnails), if the image was retrieved
  it was probably a thumbnail of a seller's gig - that seller would then be the likely rights holder. Fiverr gig images
  can themselves be AI-generated; the card does not establish authorship.
- I3: The signature-like mark is consistent with a human-signed original, but image generators also produce
  pseudo-signatures; it is not conclusive either way.
- I4: The close match between the Idle panel and the screenshot image (F5) indicates the Gemini sheet was made from
  that image (image-to-image), consistent with the owner's "refined using Gemini".

## 4. Provenance chain

| Link | Status |
|---|---|
| Source -> first image (ChatGPT-generated vs web-retrieved) | **UNRESOLVED.** Owner recollection: obtained through a ChatGPT conversation. Artefact: shown in ChatGPT with a Fiverr source card (F1-F3). Neither is conclusive |
| First image -> Gemini sheet | Supported (F5, I4, owner statement) |
| Gemini sheet -> derived atlases | Verified (F6) |
| Atlases -> Ember V2.1 | Verified (shipped assets, qualified receipts) |

Independently copyrighted third-party artwork: **neither established nor excluded.** If the first image was a
third-party work, the Idle panel and the atlases derived from it would be derivatives of it regardless of the later
Gemini refinement; the Joyful, Fierce and Depleted panels are Gemini variations that still take the character design
from it.

## 5. Terms (summary; confirm against the current official text)

- OpenAI Terms of Use: OpenAI assigns to the user its rights in Output, if any; similar outputs may be produced for
  others; copyright in AI output depends on national law. The assignment covers content OpenAI generates - not
  third-party content shown in ChatGPT search results.
- Google (Gemini API Additional Terms; consumer Gemini app terms not retrieved): Google does not claim ownership of
  generated content; similar content may be generated for others; the user is responsible for lawful use. An
  image-to-image result does not remove rights a third party may hold in the input image.

## 6. Evidence that would resolve OD-2 (owner-held)

| Evidence | What it would settle |
|---|---|
| E1. The ChatGPT conversation `6acef...` (shared link or a ChatGPT account data export with that conversation) | Whether the image appears as a generated output (prompt + image-generation result) or as a web/search result with a source |
| E2. If retrieved: the source page behind the card (open it from the same conversation) and the seller/gig | Who the likely rights holder is; whether a licence is needed |
| E3. The Gemini conversation that produced the sheet (input image + prompts) | Confirms the Gemini step and its input |
| E4. Reverse-image searches (e.g. Google Lens, TinEye) of the screenshot image, with dates and results | Supporting only: a positive hit identifies a prior source; a negative result does not establish ownership or AI-only provenance |

Resolution rule (proposed): E1 showing a generated output, plus E3, closes OD-2 as an AI-generated chain with the
residual limitations of AI-output copyright and the removed pseudo-signature. E1/E2 showing a retrieved third-party
image requires the rights holder's licence or replacement art - only then.

## 7. Corrections to earlier records

- "Fiverr illustration" (earlier licensing investigation) and "image search result attributed to a Fiverr illustration
  listing" (`PROVENANCE.md`): the repository shows a Fiverr **source card** in ChatGPT, not a Fiverr illustration
  listing, purchase or commission. These phrases are superseded by section 2.
- Nothing in the repository supports "commissioned from Fiverr"; the owner states it was not.
- Also superseded (historical documents not edited): the OD-2 question text "Fiverr illustration" in
  `docs/companions/fire/00_PLAN_AND_ACCEPTANCE_CRITERIA.md` (`8a1438ec`); "illustration listed on Fiverr" in
  `docs/companions/fire/01_RESEARCH_AND_APPROACH.md` section 2.3; the third-party Fiverr-listing statement in
  `ember_stage2/review/OD2_licensing_investigation.md`; section 6 of `02_EMBER_STAGE2_INTEGRATION_RECEIPT.md` (option A
  wording "rights to the Fiverr illustration").

## 8. Boundaries

Artwork, history, animation, rendering and qualified Ember functionality are unchanged. Ember artwork is not
distributed externally until the distribution-phase rights review is complete. Canonical integration requires technical
acceptance and separate owner authorization; OD-2 does not block it. The canonical remote (`uri-repo`,
`sche004-cyber/Uri`) is private; a push there is not treated as external distribution (any change to its visibility, a
public mirror or a release would be distribution and falls under the gate).

Sources: [Fiverr - Digital illustration category](https://www.fiverr.com/categories/graphics-design/digital-illustration);
[OpenAI community - image attribution in ChatGPT image results](https://community.openai.com/t/feature-request-image-attribution-provenance-and-source-linking-in-chatgpt-image-results/1379995);
[OpenAI Terms of Use output provision (third-party summary; official text at openai.com/policies/terms-of-use)](https://conductatlas.com/platform/openai/openai-terms-of-use/user-generated-content-and-output-ownership/);
[Gemini API Additional Terms](https://ai.google.dev/terms).
