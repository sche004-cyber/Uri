# O2 against the UI-first qualification policy (owner directive 2026-10-15)

Date: 2026-10-15. Policy: `uri-development-lifecycle` skill Stage 8 and
`docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md` section 8, introduced by milestone DEV-LIFECYCLE-3 (branch
`milestone/dev-lifecycle-3-ui-first-20261015` on the canonical repository; under independent review, not yet
integrated). Code commit assessed: `89134547` (review round 4 ACCEPT WITH FINDINGS); evidence
`evidence/o2_live_20261015/`.

**Result: O2 UI qualification = NOT VERIFIED. O2 stays unfrozen.** The source review (round 4 ACCEPT WITH
FINDINGS) is a source-code result only; under the new policy it is not phase qualification.

## 1. Why the existing UI runs do not meet the new rule

The UI runs (UI run 2 at `63e0e73f`, UI run 3 at `89134547`) use a separate release entry point,
`uri_ui/lib/office_o2_live_check.dart`. It mounts `OfficeWorkspace` directly with `AppState(MockUriClient())`, and it
presses approvals through `A2uiHub.act` from code. That proves the Office workspace, the Office service, the
engines and the approval binding work together. It does not show:

- that a user can reach Office from the real app (`lib/main.dart` → living UI → `workspace_mode_view.dart`, the one
  place the app mounts `OfficeWorkspace`);
- that the app works with the real URI Core instead of `MockUriClient`;
- real pointer or keyboard use of the controls (approval buttons, chips, composer).

The service runs (`live_service.py`, 36 PASS / 4 NOT VERIFIED) drive HTTP only; they are integration evidence, not UI
evidence.

## 2. O2 items required by the directive

| Item | Existing evidence | Status under the new policy | What is missing |
|---|---|---|---|
| Office navigation through the actual UI | harness opens the workspace directly | NOT VERIFIED | real app launch → find and open Office, first-time and returning user |
| Word preview | harness UI (`02_docx_preview.png`) | NOT VERIFIED (harness) | same in the real app |
| PowerPoint preview | service only (11-slide deck, chart) | NOT VERIFIED | any UI journey |
| PDF preview and search | harness UI (`09_pdf_search.png`) | NOT VERIFIED (harness) | same in the real app |
| Save as PDF | harness UI (DOCX); service (deck, report, bilingual) | NOT VERIFIED (harness) | real app; at least one non-Word source |
| Excel workspace continuity | harness UI (`14_sheet`, `15_sheet_kept`) | NOT VERIFIED (harness) | real app with the existing M1/M2 Excel flow |
| Natural-language tasks | deterministic subset in harness; Brain subset BLOCKED | BLOCKED (Brain) / NOT VERIFIED (deterministic) | GPU window (OD-U6) for the Brain subset; real app for the rest |
| Approval cards | harness, pressed from code | NOT VERIFIED | a real click on the card, plus a refused stale approval seen in the UI |
| Document validation | service findings; output card in harness | NOT VERIFIED | findings shown and understandable in the real app |
| File integrity | service G1 (12 originals byte-identical) | PASS as integration evidence | re-check after the real-app run |
| Error recovery | service only (corrupt, hostile, kill, disk full by injection) | NOT VERIFIED | at least one failure seen in the UI with its recovery option |
| Discoverability | scripted E rows; owner think-aloud BLOCKED | NOT VERIFIED | first-time journey from launch with no prior state |
| First-time onboarding | goal chips, one-hint rule (O1 PASS automated) | NOT VERIFIED | first-time vs returning journeys; hint not repeated |
| Contextual automation suggestions | follow-up chips (R1), "show my PDFs" | NOT VERIFIED (harness) | real app |
| UI responsiveness | H1 latencies (service); region widths in harness | PASS for service latency; UI NOT VERIFIED | real-app timings at 1100/900/700 px |
| Brain integration | — | BLOCKED | owner-approved GPU window (OD-U6: one logged window, no process killed without asking) |

## 3. Printing (O2P) — deferred

O2P printing and hardware discovery is DEFERRED by the directive. The service already starts with printing off
(`uri_office/service.py`: `printing_enabled` only with `--enable-printing`). Keep the O2P code and evidence as they
are. The O2 qualification runs WITHOUT `--enable-printing` (the earlier UI runs used it), and checks that the print
entry points are absent or say plainly that printing is off. That behaviour is NOT VERIFIED today. Physical print rows
PR-6..PR-9 stay NOT VERIFIED and do not block O2.

## 4. Next qualification run (plan)

1. Build the real app (`flutter build windows --release`, default `lib/main.dart`) at the O2 code commit; start the
   real Core and the Office service without `--enable-printing`.
2. Drive the built app as a user (computer use or a UI-automation driver that sends real input), first-time profile,
   then returning profile: launch → Office → open a DOCX, a PPTX and a PDF → preview → describe a task → plan card →
   approve with a click → output card → Save as PDF → open the saved PDF → switch to the Excel sheet and back → one
   induced error (e.g. a corrupt file) and its recovery → check the print entry points with printing off.
3. Record findings A–F (discoverability, visibility, usability, feedback, functional gaps, consistency), classify
   MATERIAL/MINOR, repair material ones in scope, re-review (`URI-OFFICE-O2-u<n>`), re-run.
4. Brain journey in one owner-approved GPU window (OD-U6).
5. Write `UI_QUALIFICATION` JSON from the template bound to the tested commit; final independent review; then the
   freeze conditions of plan §12 still apply (owner check rows E, K2; GPU decision AC-O2-16).

Owner-dependent items unchanged: GPU window and AC-O2-16 decision, owner check (E, K2). The owner is away until about
2026-10-23.
