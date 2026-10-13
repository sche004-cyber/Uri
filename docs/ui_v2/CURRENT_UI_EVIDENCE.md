> Current source has newer **unverified spacing refinements**. The captures and 567-pass suite below belong to `15a322d17aa54a4aec8316c6fc6628f70bf617ff`. See [refinement status](REFINEMENT_REPORT.md); do not treat earlier evidence as testing the new source.

# Current isolated UI evidence — 13 October 2026

Accepted canonical development base: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`, rechecked from `uri-repo/integration/git-sync-20261008`. Candidate branch: `ui/companion-v2-visual-qualification`; worktree `C:/Users/cheta/Development/uri-ui-v2`. Source repositories and other dirty worktrees were left unchanged.

| Surface | Implemented candidate | Automated evidence | Native/live evidence | Integration / deployment |
|---|---|---|---|---|
| Existing Companions | Eleven actual procedural 2D designs: four Living identities and seven Classic variants; existing shader/renderers preserved | Identity/theme, gallery and state tests; individual renderer captures | No true 3D rotation support | None / none |
| Themes | Exact Ivory Foundry, Snow Archive, Ash & Limestone; original-theme following or explicit independent interface theme | Contrast, combinations, legacy/fallback and persistence tests | Three actual engine dashboards/login captures | None / none |
| Companion | Approved detached chat; circular contextual local-A2UI actions; original single/double click recognition and local acknowledgement | Service submission once, no automatic listening, draft retention, double-click suppression | Transparent RGBA engine export; desktop compositor NOT VERIFIED | None / none |
| Native overlay | Frameless, separate bounds restoration, ellipse/button/arc/chat union, monitor work-area clamp, own-window cursor proximity | DTO/adapter tests and 96-DPI native region inspection in capture log | Cross-application clicking, multiple monitors and DPI changes NOT VERIFIED | None / none |
| Conversation | Shared AppState/OI and LivingComposer; compact classic bubbles; OI streamed/errors retained; review remains explicit | Shared-service fixture send/close/navigation tests and existing OI worker tests | No live Brain/auth/server/microphone exercised | None / none |
| Motion | 180-second button orbit, upright labels; existing paced clock; proximity/open-chat/focus/voice/reduced-motion suspension | Full-circle geometry samples and widget pause tests; 360x560/440x680 at 200% text | GPU/VRAM/native motion performance NOT MEASURED | None / none |
| Login/bootstrap | URI typography without logo; existing APIs, password obscuring, duplicate guard and form validation | Form/error callback tests; three themed engine captures; real entry build | No owner login, credentials or sessions used | None / none |
| Dashboard | Actual Solar, six functional panels, brass conduits, all preserved navigation and bottom-right faded engraving | Responsive tests; three themes and target-size engine exports | Owner comparison supplied; new code not visually accepted | None / none |

Current capture folder: `evidence/final/`, authoritative `capture_log.txt` and `result.json`. Older folders are iteration history. The harness uses the real Windows Flutter engine with fixture-only data and `RenderRepaintBoundary.toImage`, not desktop compositor screenshots. Voice events are injected; no private conversations/audio are used.

Analysis, full-suite logs and exact results are in `WORKING_STATE.json`, `analyze_final.txt` and `regression_final.jsonl`. A unit/widget test is not independent acceptance or deployment evidence. Frozen-path delta against the accepted base remains zero; the historical frozen checker already reports two unchanged baseline deviations (120/121 checkpoint hashes match, not 121/121).

Missing/unverified: wake phrase detection, live native transparency/hit testing, device/audio/auth/runtime journeys, DPI/multiple monitors, performance measurement and fresh exact-commit independent acceptance. No API, privilege, Core/security or production change was introduced.
