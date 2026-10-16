> Latest source adds button and page-placement refinements. See [current pass](BUTTON_LAYOUT_REPORT.md). Flutter tests, fresh captures and independent acceptance remain **NOT VERIFIED** for this source.

# Functional coverage matrix

Owner visual approval applies to the image, not candidate code. Unit/widget fixtures, recorded render captures, independent acceptance, integration and deployment are separate evidence fields. No Figma node links are claimed.

| ID | Destination / component | Existing test evidence | Recorded verification | Independent integration | Deployment |
|---|---|---|---|---|---|
| UI-001 | Bootstrap | [bootstrap_screen_test.dart](../../uri_ui/test/bootstrap_screen_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-002 | Login | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-003 | Classic onboarding | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-004 | Brain setup | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-005 | Living setup | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-006 | Dashboard | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-007 | Artwork | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-008 | Companion click | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-009 | Companion buttons | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-010 | Detached chat | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-011 | Orbital layout | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-012 | Orbit pause | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-013 | Native overlay | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-014 | Native hit regions | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-015 | Audio level bars | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-016 | Voice activation | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-017 | Companion catalog | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-018 | Theme independence | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-019 | Gallery | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Engine capture + fixture interaction; native/runtime caveats in CURRENT_UI_EVIDENCE.md | None for new candidate | None |
| UI-020 | Shared composer | [living/ui_v2_test.dart](../../uri_ui/test/living/ui_v2_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-021 | Workspace | [living/living_shell_test.dart](../../uri_ui/test/living/living_shell_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-022 | OI stream | [ws/ws_integration_test.dart](../../uri_ui/test/ws/ws_integration_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-023 | Task review | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-024 | Supervised task | [supervised_execution_screen_test.dart](../../uri_ui/test/supervised_execution_screen_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-025 | Draft desk | [ws/ws_integration_test.dart](../../uri_ui/test/ws/ws_integration_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-026 | Providers | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-027 | Connections | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-028 | Memory | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-029 | Intelligence | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-030 | Settings | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-031 | Diagnostics | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-032 | Admin grants | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-033 | Scheduler | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-034 | Assist | [living/assist_mode_test.dart](../../uri_ui/test/living/assist_mode_test.dart) — fixture coverage, see raw suite log | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
| UI-035 | Runtime A2UI | Specific per-control coverage NOT VERIFIED; full-suite pass does not imply it | Source/test inspection; live journey NOT VERIFIED | None for new candidate | None |
