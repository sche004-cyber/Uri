# Phase 2 operational qualification: UI, voice parity and acceptance plan

Date 2026-10-08. Author: Claude (implementer and self-auditor; not an independent review). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent` (detached at `e8e3b65`, uncommitted). Supersedes nothing; it
extends `PHASE2CLOSE_UI_READINESS.md` with the state after the operational-qualification slice.

Rule kept throughout: a design document, a mockup, a widget test or a scripted endpoint never proves real-device
behaviour. Statuses use the ledger vocabulary (PLANNED, IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED, PHYSICALLY
QUALIFIED, FROZEN, DEPLOYED); PARTIAL and BLOCKED are stated with the missing part.

## 1. Acceptance criteria for this plan (set before drafting)

1. Every area the owner listed has a status backed by a file, a test or a named absence.
2. Each status distinguishes the Phase 2 tree from the `_V1` line; nothing on `_V1` is counted as present here.
3. Each missing part names its blocker (code, owner decision, line reconciliation, hardware).
4. Each area has an acceptance step that a real device (the owner) performs, mapped to a PA gate where one exists.
5. No new feature scope: everything outside Phase 2 is listed as a later item, not planned here in detail.

## 2. Status by area

| Area | Phase 2 tree | `_V1` line | Status (Phase 2 tree) | Blocker for the rest | Real-device acceptance |
|---|---|---|---|---|---|
| Companion / Workspace continuity | Workspace, Compact, Mobile presentation per the frozen blueprint; the supervised screen is a pushed route over any of them | `platform_window_controller.dart` "Companion Compact window", `compact_overlay.dart` | PARTIAL: presentation switch IMPLEMENTED (blueprint, legacy line); continuity of a pending supervised card across a switch NOT TESTED | widget test for the supervised route under a Compact/Workspace switch (next UI slice) | PA-6 extended: switch presentation while an approval card is pending; the card, digests and session stay; nothing resubmits |
| URI-controlled presentation-state transitions (Orb) | state contract only (`PHASE2CLOSE_UI_READINESS.md` section 3) | voice wake restores Chat | DESIGN ONLY | visual design (owner), line reconciliation | none yet (no implementation) |
| Chat -> supervised handoff (C6 Option B) | `widgets/supervised_handoff_action.dart`, `services/task_handoff.dart`, `SupervisedExecutionEntry.open(draft:)`, Chat pane mount | absent | IMPLEMENTED, TESTED (widget: `supervised_execution_screen_test.dart`, `chat_supervised_handoff_test.dart`) | independent review; owner session | **PA-13** (new): from a settled Chat message, open the draft, confirm nothing was sent, choose executor, Send, Decline; Back returns to the conversation unchanged |
| Approval / denial / cancellation / recovery | supervised screen + execution lifecycle; OQ-1 (unusable executor: Approve disabled, `execution_begin` refused before the server) | absent | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (ops round 7, closure round 6); OQ-1 IMPLEMENTED, TESTED | owner session | PA-2..PA-7 |
| Client/server connection and authentication | worker spawned from `URI_CLIENT_MANIFEST` + opt-in file; signed identity; preflight line | legacy `/ask` + login screen | IMPLEMENTED, TESTED, INDEPENDENTLY ACCEPTED (paired runtime Phase 1; supervised profile ops) | owner session | PA-1, PA-6, PA-7 |
| Harness and provider selection | executor picker: no preselection, unusable rows disabled with the exact required action; native rows only from a client-profile qualification | desktop harness UI (provisional) | IMPLEMENTED, TESTED; native rows need the client-profile login | owner logins (PA-8/PA-9), sandbox backend decision (EXE-1b) | PA-8, PA-9, PA-10 |
| Qualification and readiness indicators | preflight line; harness lines (installed / auth state / qualification / required action); proposal shows qualification and LIVE usability (OQ-1); `scripts/phase2close_acceptance.py status` reports INSTALLED, AUTHENTICATED, QUALIFIED, OPERATIONAL separately | readiness text in harness UI | IMPLEMENTED, TESTED (CLI + widgets); the four-state view exists only in the CLI | a UI panel over the same four states (later UI slice) | PA-1 (preflight), PA-8/9 (`status` after login) |
| Voice-command parity | none | `widgets/desktop_voice.dart`, `services/voice_event.dart`, `scripts/uri_voice_listener.ps1`, `scripts/uri_voice_transcribe.py` (uncommitted, "IMPLEMENTED - AWAITING USER TEST" per `_V1` `CAMERA_VOICE_GEMMA_IMPLEMENTATION_REPORT.md`); a transcript is sent to legacy `/ask` through `AppState.ask()` | BLOCKED (infrastructure absent from this tree) | line reconciliation (P2-6) and the voice parity rules below | none until ported |

## 3. Voice parity rules (proposed; the parts marked OWNER are not assumed)

The handoff seam already carries `source: 'voice'`, so voice needs no new authority path:

1. A spoken request becomes a `TaskHandoff(source: 'voice')`: an UNSENT draft on the supervised screen. It is never
   sent, confirmed or approved by voice. (`_V1` today sends a transcript straight to legacy `/ask`; for supervised
   execution that would turn speech into a protected-action request without the draft step, so it is not ported as is.)
2. Voice never approves, confirms an intent or selects an executor: an utterance is typed text (C6 contract), and the
   approval card needs the on-screen digests.
3. OWNER: whether voice may say "cancel" for a running execution. Cancelling only withdraws authority, but a
   misrecognised word would end a run; recommended: voice may OPEN the cancel button's confirmation, not press it.
4. OWNER: wake word and audible reply behaviour are already the owner's `_V1` decisions; they are not changed here.
5. Presentation: a voice wake may restore the window and show the draft; it never resubmits a pending card (blueprint R2).

Acceptance once ported (new gates, numbered when the slice exists): spoken request -> draft banner says "Draft from
voice", nothing sent; spoken "approve" -> nothing happens; spoken request while a run is in flight -> draft kept, run
shown (`sx-draft-busy`).

## 4. Order of work (no redesign, smallest steps)

1. Owner: shipping line (`PHASE2OQ_SHIPPING_LINE_RECOMMENDATION.md`), Codex sandbox backend (EXE-1b), voice rules 3-4.
2. Owner session on this tree: PA-1..PA-7 and PA-13 (no login needed), then PA-8/PA-9 logins, PA-10.
3. Integration slice onto the chosen line: Phase 2 packages, the supervised screen, the handoff action (additive files
   plus two mounts: `app.dart`, Chat pane).
4. Voice port as a separate slice on that line: `_V1` voice infrastructure + rules 1-5 + its acceptance steps.
5. UI slice: shared approval/execution widgets (`PHASE2CLOSE_UI_READINESS.md` section 5), presentation-switch
   continuity test, four-state readiness panel. Orb and Brain visualisation stay in the design phase.
