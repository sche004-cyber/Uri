# Independent visual critique - reviewer output (verbatim scores)

Reviewer: a separate Claude subagent that did not make the images, run 2026-10-15 (session of this milestone),
read-only. Inputs it was given: `reference/uri_emotions_sheet.png`, `evidence/fidelity/fidelity_sheet.jpg`,
`evidence/perf/grid.jpg`, `evidence/perf/ember_idle_bg.jpg`, `reference/video_frames/key_{idle,joyful,fierce,depleted}.jpg`.
Rubric: nine dimensions, 0-10 each (10 = indistinguishable in identity and intent from the reference panel; 5 = the
same kind of thing but noticeably different; 0 = unrelated); fidelity % = average x 10. The same rubric was applied
to the AI video redraw of the same character for calibration. The reviewer stated that its scores are perceptual
judgements, not measurements. This file transcribes its table; the implementer did not change any value.

| Dimension | Idle | Joyful | Fierce | Depleted |
|---|---|---|---|---|
| Silhouette | 5 / 6 | 5 / 6 | 5 / 7 | 5 / 6 |
| Proportions | 5 / 7 | 5 / 7 | 5 / 7 | 5 / 7 |
| Eye shape/position | 7 / 8 | 3 / 6 | 6 / 8 | 6 / 8 |
| Facial expression | 7 / 8 | 4 / 8 | 6 / 7 | 6 / 9 |
| Flame structure | 3 / 5 | 3 / 5 | 3 / 5 | 4 / 5 |
| Colour accuracy | 6 / 6 | 5 / 6 | 4 / 6 | 6 / 6 |
| Material appearance | 3 / 6 | 3 / 6 | 3 / 6 | 3 / 6 |
| Lighting/atmosphere | 5 / 6 | 5 / 6 | 4 / 6 | 5 / 6 |
| Overall identity | 5 / 7 | 4 / 7 | 5 / 7 | 5 / 7 |
| **Average** | **5.1 / 6.6** | **4.1 / 6.3** | **4.6 / 6.6** | **5.0 / 6.7** |
| **Fidelity %** | **51 % / 66 %** | **41 % / 63 %** | **46 % / 66 %** | **50 % / 67 %** |

(render / video redraw)

Reviewer's verdict (summary): the >= 90 % target is not achieved in any state. Ember reads as the same idea
(white egg head, big black eyes, flame crown, dark ragged robe, stick limbs) but not yet as the same character.
Largest differences: flame structure (thin radial strands vs a dense swept painterly mane with a white-hot core),
head material (crisp matte ellipse vs soft emissive head melting into the flame), per-state poses (no joyful kick,
no depleted slump), joyful eyes (round black vs squinted brown smiling), no painterly surface; fierce overexposed
yellow-white; depleted smoke too light and flames too large. It also noted the colour-fringed halo disc in the
transparent real-app capture `grid.jpg`; the composited view (`ember_idle_bg.jpg`) shows that this is the capture
viewed without its alpha, with only a faint disc edge remaining on a light background.
