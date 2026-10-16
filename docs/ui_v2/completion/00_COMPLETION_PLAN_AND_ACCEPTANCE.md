# URI UI V2 completion — plan and acceptance criteria

Milestone: `UI-V2-COMPLETION` (owner task "URI UI V2 — cosmetic refinement, existing system preservation, and
integration blocker resolution", 2026-10-15).

UI V2 is a refinement of the URI already built. It is not a redesign. This plan keeps every accepted feature and
changes only what evidence shows is broken, unfinished or visibly rough.

## Pins

| Item | Value |
|---|---|
| Canonical | `https://github.com/sche004-cyber/Uri`, branch `integration/git-sync-20261008`, remote `uri-repo`, verified `7d3d0f632ea3af7de17915351f089e5af4dcbb75` on 2026-10-15 |
| Earlier UI V2 candidate | `316e6475` on `qualification/companion-v2-repair-20261013` (base `1b5423bc`); kept unchanged |
| This candidate | branch `milestone/ui-v2-completion-20261015`, worktree `C:\Users\cheta\Development\uri-ui-v2c` |
| Rebase | the four V2 commits were rebased onto `7d3d0f63` without conflict. `uri_ui/` and `docs/ui_v2/` trees are byte-identical to `316e6475` before any new work (`git diff 316e6475 18a91f0a -- uri_ui docs/ui_v2` is empty) |
| Run folder (evidence, harness, runtime) | `C:\Users\cheta\Development\uri-ui-v2c-run` (outside the candidate) |

Canonical moved from `1b5423bc` to `7d3d0f63` only by DEV-LIFECYCLE-3/3A (policy text and lifecycle driver). No
`uri_ui` file changed there.

## Scope

In scope (UI V2-owned):
- Make the V2 presentation reachable from the real production app entry (today it only runs from qualification
  entries `main_v2*.dart`).
- Repair UI defects found by live use of the real app.
- Small cosmetic refinements with evidence: spacing, contrast, labels, composer borders, wording, discoverability
  hints. No screen replacement. No new dependency. No new shader or renderer.
- Live Windows qualification through the real app with the real Core and Brain, under the GPU lease.

Out of scope (owned elsewhere; recorded, not changed here):
- Core and Brain routing defects (for example the generic `prepare_output` gap reply) — Core milestones.
- Runtime security of the materialized test runtime (FCV-11 / FCV-R thread).
- URI Office (Excel, O2, Word, PDF, PowerPoint) — Office thread. Not in canonical; UI V2 must not add it.
- Ember V2.1 into UI V2 — next milestone after UI V2 (owner sequence 2026-10-15).
- Companion fidelity work, Mission Control, Skill Command Center, Lifecycle V3.1 task state.
- Frozen paths (`ws_frozen_check` list). No change.

## Capability classes (lifecycle Stage 1)

| Capability | Class | How verified |
|---|---|---|
| V2 Dashboard, Workspace, Companion, Assist presentation | USER_FACING | live journeys through the real app |
| Companion transparent window, hit regions, drag, clamp | USER_FACING | native run on Windows: window facts from the native channel, region checks |
| Conversation through UI to Core to Brain | USER_FACING | live journeys with the real Runtime v1 Brain |
| Clarification and confirmation cards, approval cards | USER_FACING | live journeys |
| Companion gallery, theme and preference persistence | USER_FACING | live journey + restart (returning user) |
| Production entry wiring (`main.dart`) | INDIRECT | qualified through the live journeys that start from production `main()` |

## Acceptance criteria

AC-1 Preservation. No accepted feature, route, shortcut, setting, data contract or integration is removed or
disabled. The V1 living composition and the classic interface stay reachable. Evidence: whole-diff review against
`7d3d0f63`, full Flutter suite, an inventory row for every screen in `SCREEN_AND_FUNCTION_INVENTORY.md`.

AC-2 Production reachability. Starting the real app (`main.dart`) on a paired installation shows the V2
presentation, with the existing worker, Core, Brain, voice and window wiring. The old composition stays available
by one documented switch. Unpaired installations are unchanged (classic `UriApp`).

AC-3 Real assistant work. From the V2 UI a user sends a request and gets a real Brain reply through Core. Busy,
reply and error states are visible. No simulated reply is shown as real.

AC-4 Clarification and approval. A request that needs clarification shows the clarification/confirmation UI;
answering it continues the turn; declining is honoured. Approval cards stay explicit (no auto-approve).

AC-5 Navigation. Dashboard, Workspace (Conversation, Tasks, Documents, Scheduler, Connections, Settings), Companion
and Assist are reachable by click and by Ctrl+1..4; Escape behaviour is unchanged; state (draft, conversation,
pending decisions) survives mode changes.

AC-6 Companion. Single click acknowledges and shows floating actions without asking the Brain; double click opens
Dashboard; Chat toggles the detached chat; the companion window is frameless with a shaped region and transparent
background; leaving Companion restores the normal window; the window stays on screen (clamp).

AC-7 Settings persistence. Companion choice, interface theme and window position persist across restart and
survive returning-user start.

AC-8 Honest status. Connection, Brain readiness and unavailable features are named in plain words. No raw internal
codes on screen (`[A-Z]+_[A-Z_]+` pattern) in the journeys.

AC-9 Cosmetic quality. Each cosmetic change is listed with before/after screenshots or the reason screenshots are
not available. Changes are small and local to existing widgets and theme tokens.

AC-10 Performance. No material regression: UI process CPU and RAM, GPU dedicated memory of `uri_ui.exe`, and Brain
tokens per second with the UI open are measured before and after under the same conditions and recorded. The UI
must not take the GPU over the lease budget.

AC-11 Security and governance. Candidate changes no protected path (`protected_paths: ws_frozen_check` diff
against the baseline is empty). Security regressions (Python security suite) pass as on canonical. No approval or
permission bypass.

AC-12 Blockers. Every earlier UI V2 blocker has an entry in `01_BLOCKER_REGISTER.json` with cause, owner, repair
and status. UI V2-owned blockers are resolved or the candidate is not called complete.

AC-13 Independent review. Driver-counted Codex review (fallback per lifecycle skill) on the exact final SHA with
`evidence_ok_for_candidate: true`. No self-acceptance.

AC-14 Live record. `UI_QUALIFICATION_UI_V2.json` from the lifecycle template, bound to the tested code commit. PASS
only when every mandatory journey passed live; otherwise NOT VERIFIED or BLOCKED with the missing item.

## Live journeys (Stage 8)

J1 start (first-time and returning) · J2 navigation all modes · J3 conversation with real Brain · J4 ambiguity and
clarification · J5 tool use through UI (existing supported capability) · J6 Office/documents entry points
(existing only) · J7 companion interactions and window · J8 settings and theme persistence · J9 approval visibility
and decline path · J10 responsiveness during Brain execution · J11 window resize and narrow layouts · J12 failure
and recovery (worker stop, Brain unavailable) · J13 regression of accepted workflows.

Input is Flutter `TestTextInput` and widget actions inside the real production `main()` (integration_test on the
built Windows app). Physical mouse and keyboard, microphone and speaker, second monitor and other DPI are recorded as
NOT VERIFIED unless observed.

## Owner-only items (not started without the owner)

- Canonical integration (D1): request only after all integration preconditions hold.
- Frozen-check governance reconciliation (`FROZEN_RECONCILIATION.md` from 2026-10-13): inherited canonical
  condition, not caused by UI V2; stays an open owner item.
- Visual-reference similarity checkpoint (0.80 against Concept C) — owner judgement; recorded, not a code gate.
- Production deployment and cutover: never part of this milestone.

## Auditor

Codex (`codex_cli`, model `gpt-6-sol`, unelevated Windows sandbox), probed before the first run. Fallback per the
lifecycle skill; reason recorded if used.
