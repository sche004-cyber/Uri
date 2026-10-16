> Latest source adds button and page-placement refinements. See [current pass](BUTTON_LAYOUT_REPORT.md). Flutter tests, fresh captures and independent acceptance remain **NOT VERIFIED** for this source.

> Current source has newer **unverified spacing refinements**. The captures and 567-pass suite below belong to `15a322d17aa54a4aec8316c6fc6628f70bf617ff`. See [refinement status](REFINEMENT_REPORT.md); do not treat earlier evidence as testing the new source.

# Visual qualification — isolated candidate

The owner approved [Detached chat](evidence/reference/companion-approved.jpg) on 13 October 2026. Dashboard authority is [the supplied image](evidence/reference/owner-current.jpg) plus the three approved theme studies. Approval applies to those references, not this new code.

Current captures: `evidence/final/`. [Companion side-by-side](companion-review.html) · [dashboard / three themes](dashboard-review.html). These are actual Windows Flutter engine RGBA exports with fixtures, not desktop-compositor screenshots. The comparison-page gray is outside the application. No private conversations, credentials or microphone recordings were used.

## Reference repairs and remaining differences

Circular floating actions now have proportional icons, upright labels and sparse visible brass arcs. The actual Solar renderer remains central. Voice level bars sit below the complete orbital path; detached shared chat sits below them. Chat close/Escape preserve drafts; no decorative interaction authorizes work. The dashboard retains six conduit-linked destinations and a background-free, unframed, faded engraving at bottom right. No logo or new renderer was introduced.

| Severity | Difference / qualification |
|---|---|
| Medium | The generated sun reference and actual procedural Solar have different filament, corona, hue and phase details. Existing shader/rendering identity was preserved. |
| Medium | Compact 440x680 and 360x560 adaptations retain 80px controls and readable labels; they are larger proportionally than a downscaled reference. The matching 828x1280 layout is also captured. |
| Medium | Actual chat font, bubble padding, composer spacing and icons still differ. Long/streaming/error/review content needs scrolling beyond the two-line sample. |
| Medium | The requested stronger artwork fade changes linework and contrast; generative background removal reconstructed some linework. Original source and exact edit prompt are preserved. |
| Medium | At 360x560, the detached transcript has room for only a small scrollable excerpt. At 390px dashboard width the supporting heading copy is clipped by the compact central composition; this needs responsive repair before qualification. |
| Unverified | Native compositor, cross-application hit testing, movement, DPI/monitors, hardware audio, real auth/runtime and GPU/VRAM/frame cost. |

## Reproducible screenshot checkpoint

`tools/compare_final_references.py` reads the original reference and current capture without modifying either image. It computes equal-weight local luminance SSIM over six Companion regions and eight dashboard regions. Transparent Companion pixels are composited over comparison gray only in memory. The Companion comparison uses the exact reference viewport, 828x1280. The dashboard reference is resampled from 1280x889 to 1440x1000. Bounds and SHA256 values are in the JSON reports.

- Dashboard: **0.879**, exceeding the 0.80 screenshot checkpoint ([report](evidence/final/dashboard_comparison.json)).
- Companion: **0.634**, **below 0.80** ([report](evidence/final/companion_comparison.json)).

This metric is not a literal percentage of design accuracy or visual acceptance. The owner's requested 80% Companion fidelity is **not established**. Earlier 440x680 comparison measured 0.419; older reports remain iteration history. Improving geometric resemblance must not replace the approved working Companion with an imitation.

## Verification and verdict

`regression_final.jsonl`, `analyze_final.txt`, `build_real_final.txt`, `build_preview_final.txt` and `WORKING_STATE.json` record available gates. Capture `result.json` reports success, with fixture-only data and desktop_compositing_verified=false. Native region inspection at 96 DPI reports cornerHit=false for collapsed/expanded layouts; this does not prove clicking through into unrelated apps.

**NOT READY — BLOCKERS.** The Companion screenshot checkpoint, native/live/performance qualification and fresh exact-commit independent acceptance remain outstanding. The isolated preview is available for owner inspection. No push, merge, production integration or deployment occurred.

Skills applied: Flutter widget-test guidance; installed Anthropic frontend-design and Vercel web-design-guidelines; imagegen for the requested cutout; repository uri-development-lifecycle for exact-commit review. No new runtime renderer/package dependency was added.
