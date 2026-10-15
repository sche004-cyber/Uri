# UI V2 completion — evidence-based inventory

Classes: **A** implemented and working · **B** working, cosmetic work needed · **C** implemented but
integration-blocked · **D** incomplete existing UI functionality · **E** proposed, not implemented.
Row IDs (UI-0xx) refer to `../SCREEN_AND_FUNCTION_INVENTORY.md`. "Live" means the native runs of this milestone
(`UI_QUALIFICATION_UI_V2.json`); everything else is source inspection plus the Flutter suite.

| Area | Rows | Class before | What changed here | Class after |
|---|---|---|---|---|
| Production entry (paired installation) | — | C: V2 only in `main_v2*.dart` | `main.dart` opens V2 (BLK-INT-1); `URI_UI_VISUAL=living` keeps the old composition | A (live J1) |
| Bootstrap, login, classic onboarding, Brain setup | UI-001..004 | A (classic path, unchanged) | none | A |
| Living setup flow | UI-005 | A | none | A (live J1 first-time) |
| V2 Dashboard: destinations, composer, artwork | UI-006, UI-007 | B: one-column below 960 px height; "0 review needed"; count ignored worker decisions | medium layout, honest count (BLK-INT-3), plain labels, nav hints | A (live J2, J9, J11) |
| Companion click, floating actions, orbit | UI-008, UI-009, UI-011, UI-012 | C: native behaviour unqualified (BLK-NAT-1) | none to behaviour | A/NOT VERIFIED split in record (J7) |
| Detached chat | UI-010 | B: clipped bubble sliver under header | top fade | A (J7) |
| Native window: frameless, regions, drag, clamp | UI-013, UI-014 | C: not wired in production; unqualified | wired in `main.dart` | A for size/region facts; drag and physical hit-testing NOT VERIFIED |
| Voice waveform and voice buttons | UI-015, UI-016 | A in code; microphone NOT VERIFIED | none | unchanged (NOT VERIFIED physical audio) |
| Companion catalog, theme independence, gallery | UI-017..019 | A | none | A (J8, returning run) |
| Shared composer | UI-020 | A | none | A |
| Workspace regions | UI-021 | A; Documents tiles simulated in integrated V2 (D) | real turns (BLK-INT-2) | A (J6) |
| OI stream, confirmations, approvals | UI-022 | A; raw codes on chips (owned by FCV-R) | none (no duplicate of FCV-R) | A with FCV-R items recorded |
| Tasks, supervised tasks, drafts | UI-023..025 | A (preserved, frozen where noted) | none | A |
| Providers, connections, memory, intelligence, settings, diagnostics, grants | UI-026..032 | A (preserved) | none | A |
| Scheduler | UI-033 | A (needs `URI_SCHEDULER_STATE`; honest "unavailable" page otherwise) | none | A |
| Assist | UI-034 | A (permissions unchanged) | none | A (J2 navigation) |
| Runtime A2UI | UI-035 | A | none | A |
| URI Office Excel / O2 | — | not in canonical (Office thread) | none | out of scope (OUT-OFFICE-1) |
| Wake phrase "oii URI" | — | E (unsupported by the voice baseline) | none | E |
| Mission Control, Skill Command Center | — | E (future milestones) | none | E |

No accepted row was removed, disabled or replaced. Frozen files are untouched (protected-path diff empty).
