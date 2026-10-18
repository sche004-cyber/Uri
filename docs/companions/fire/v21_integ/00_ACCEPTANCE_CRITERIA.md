# EMBER-V21-INTEG-20261018 - Acceptance criteria (defined before qualification)

Milestone: reconstruct the preserved Ember V2.1 candidate (`d6a83131`, handoff `4a70d9e7`) on canonical
`348677b7`, keep UI V2 behaviour, and verify true transparent, borderless rendering on Windows.
Branch `milestone/ember-v21-integ-20261018`, worktree `D:\uri-dev\uri-ember-v21-integ`. Local only.

Not in scope (separate owner approval): canonical integration, freeze, tag `accepted/*`, push, deploy.
Owner decisions carried unchanged from the closure receipt: fidelity (AC-F1/AC-F3 NOT MET), F-LIGHT-1, T4 depleted,
F-SIZE-1, F-START-GAP, OD-2 licensing, AC-P1. This milestone does not decide or waive them.
Added by this milestone for owner ruling (review R1-02): D-1 - on canonical, a host waiting for the GPU lease
(`WAITING_FOR_LEASE`) keeps the FCV-10 unavailable "Waiting for GPU" look instead of the Ember handoff's Initializing.
**D-1 owner ruling 2026-10-18: APPROVED** - retain canonical FCV-10 Brain-state semantics ("Waiting for GPU" when GPU
resources are unavailable, "Initializing" when the Brain is genuinely starting or loading, ready only after verified
readiness, unavailable/failed only when the authoritative state confirms it). Ember controls visual presentation, not
Brain-state authority. The acceptance criteria below are unchanged by this ruling.

Evidence rule: only a check that ran to completion with a recorded result counts (COMPLETED_WITH_RESULT).

| ID | Criterion | Evidence required |
|---|---|---|
| AC-1 | Branch is cut from exactly `348677b7`; first parent of the Ember merge is `348677b7`, second is `d6a83131`; no commit from `62d564cf` lineage outside `348677b7` | `git rev-parse`, `git log --format=%P`, `git merge-base --is-ancestor` |
| AC-2 | Every non-doc file the handoff section 3 lists is present and equal to `d6a83131`, except where a recorded conflict resolution changed it | per-file diff vs `d6a83131` |
| AC-3 | Excluded material (reference artwork, fidelity reviewer packs, V1/V2 history docs, V1 Blender art) is absent from the tree | `git ls-tree` check |
| AC-4 | Frozen and protected paths unchanged vs `348677b7`: `scripts/ws_frozen_check.py` PROTECTED list, `uri_operational_intelligence/`, `scripts/run_uri_*`, launch scripts, `.gitignore`, Runtime v1 config; UI V2 freeze `7893aaed` files changed only where the handoff names a UI V2-owned edit (design count pin) | boundary diff log; `ws_frozen_check.py` run |
| AC-5 | UI V2 behaviour kept: FCV-10 Brain startup headline/detail unchanged; all UI V2 tests pass; Ember Initializing never shown where FCV-10 shows unavailable or error | `ui_v2_test.dart`, `ws_integration_test.dart`, new conflict-resolution tests |
| AC-6 | `flutter analyze lib test tool`: 0 errors | log |
| AC-7 | Full Flutter suite: 0 failures (skips listed) | log |
| AC-8 | Atlas gates T0-T5 (`scripts/fire_companion/transparency_check.py`) and `ember_transparency_test.dart` give the same results as at closure (T4 depleted FAIL is carried, not new) | log |
| AC-9 | Windows release build of the integrated V2 app succeeds | build log |
| AC-10 | Live Windows: companion window is borderless (no caption, no sizing frame, no visible DWM border or shadow) | window style read-back + screenshot |
| AC-11 | Live Windows: true per-pixel transparency - over a known coloured backdrop, pixels inside the window where Ember has no alpha show the backdrop unchanged; Ember's own pixels blend; no opaque matte, black/white box or fringe from the window | composited-screen pixel samples + screenshots on dark and light backdrops |
| AC-12 | Live Windows: click-through outside the companion hit region reaches the window behind; clicks on Ember reach URI | live input probe |
| AC-13 | Live Windows: drag and scale options (incl. 1.25x) work; F-SIZE-1 crop measured, not hidden | screenshots/measurements |
| AC-14 | Live with real Core + Runtime v1 Brain (Qwen3.6-35B-A3B MoE) under own GPU lease (`our_brain: true`): Ember selectable in the UI V2 gallery, persists, idle/thinking/speaking/success observed, Initializing during Brain start, unavailable when Brain stopped | live journey record |
| AC-15 | Independent review of the exact candidate commit: ACCEPT or ACCEPT WITH FINDINGS after repair/re-review; reviewer type recorded (Codex / claude_cli / independent subagent) | review records |
| AC-16 | Qualification receipt with exact SHAs, results and every open finding classified | receipt file |
