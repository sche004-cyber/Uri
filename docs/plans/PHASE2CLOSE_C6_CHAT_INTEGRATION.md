# C6 owner decision 2: Chat and supervised execution, recommendation and status

Date 2026-10-08. Author: Claude (implementer and self-auditor; this is NOT an independent review). Worktree
`C:\Users\cheta\.codex\worktrees\uri-phase2a\uri-agent`, detached at `e8e3b65`, uncommitted. Status: **RECOMMENDATION
FOR THE OWNER + the no-decision part IMPLEMENTED/TESTED. The decision itself is NOT taken.**

## 1. The decision as the governing contract states it

`docs/plans/C6_UI_INTEGRATION_CONTRACT.md`, "Owner decisions needed", item 2: *Decide whether Chat may move to the
paired runtime before C7, as an opt-in per installation.* The same document says the legacy `/ask` stays the default
until C7, and `C7_CUTOVER_REQUIREMENTS.md` gate 5 needs "Chat connected to the paired runtime". So the decision is
reserved for the owner, and Phase 2 must not take it silently.

## 2. Acceptance criteria used for the recommendation (set before drafting)

1. Ordinary typed text never authorizes a protected action (C6 contract; Phase 2 approval semantics).
2. Intent discovery, proposed execution, human approval, harness execution and verification/reporting stay separate
   steps with separate, visible boundaries.
3. No conversation context, permission or approval boundary is lost or widened when work moves from Chat to a task.
4. Nothing reverses an accepted Phase 2 property (digest-bound approval, one execution per client, cancellation
   semantics, corroborated receipts, no fallback).
5. The legacy `/ask` default is preserved until C7 unless the owner decides otherwise.
6. Each option is reversible by removing one opt-in, and its implementation risk is stated from evidence.

## 3. What exists today (evidence, not assumption)

| Surface | Path | Status |
|---|---|---|
| Chat (legacy) | `uri_ui/lib/screens/ask/ask_uri_screen.dart` -> legacy server `/ask` | IMPLEMENTED (Phase 1 line), not paired |
| Paired runtime screen (frozen) | `uri_ui/lib/screens/settings/paired_runtime_screen.dart` + `services/paired_runtime.dart` | FROZEN (Phase 1 checkpoint) |
| Supervised execution (Tasks) | `uri_ui/lib/screens/tasks/supervised_execution_screen.dart` + `services/supervised_runtime.dart` | INDEPENDENTLY ACCEPTED (UI/operations slice, Codex round 7), opt-in per installation |
| Intent discovery/confirmation | frozen server (`INTENT_CLARIFICATION`, `INTENT_CONFIRMATION_REQUIRED`) through `turn_start`/`turn_intent` | FROZEN (Phase 1) |
| Conversation-to-task handoff value | `uri_ui/lib/services/task_handoff.dart`; `SupervisedExecutionScreen(draft:)`; `SupervisedExecutionEntry.open(context, draft:)` | **IMPLEMENTED + TESTED this closure**; not mounted in Chat |

## 4. Options

| | A. Keep separate (status quo) | B. Chat hands off a DRAFT to supervised execution (recommended) | C. Chat moves to the paired runtime (opt-in per installation) | D. Unified conversation surface on the paired runtime (target experience) |
|---|---|---|---|---|
| What the user sees | Chat for conversation; Tasks -> Supervised execution for work | On the user's OWN message in Chat: "Make this a supervised task". It opens the supervised screen with the words pre-filled and a "Draft from the conversation. Nothing has been sent" banner | The same Chat composer, but each turn goes `turn_start` -> clarification/confirmation -> approval card -> `execution_begin` in-line | One thread where conversation turns, confirmation cards, approval cards and execution receipts interleave; Tasks shows the same executions |
| Authority | unchanged | unchanged: the draft carries text only; executor choice, Send, confirmation and approval stay explicit on the supervised screen | Chat's turns become paired turns (server-side intent discovery and approval for every turn) | as C, plus a shared conversation/task model |
| Typed text as authorization | impossible | impossible (the draft is not sent; the approval card is still required) | impossible if the C6 contract is kept (frozen server holds the session while an approval is pending) | as C |
| Context continuity | none (user retypes) | words carried; conversation id recorded for provenance only, never reused as the supervised session | full (same session) | full |
| Legacy `/ask` default | kept | kept | replaced for opted-in installations | replaced (C7) |
| Reversibility | n/a | remove the action (one widget) | remove the opt-in | cutover-level |
| Implementation risk | none | low: one action on the message bubble + the already-tested handoff seam | high: the legacy Chat carries attachments (`_AttachmentStrip`) and a per-turn model selector (`_ModelSelectorChip`), which the paired worker protocol does not serve; Brain rows are not composed (`lazy-not-selected`) | very high; needs the Context Capsule / Task Compiler (design only) and the C7 cutover |
| Governing status | allowed | **needs the owner's yes** (it changes Chat's visible behaviour) | reserved owner decision 2 | C7 + later phase |

## 5. Recommendation

**Option B now, Option D as the target, Option C not before the paired runtime serves Chat's existing features.**

Reasons, from the evidence in section 3: B gives the desired conversation-to-task experience without moving Chat's
traffic, so none of the legacy features break and no authority path changes; every protected step still happens on
the accepted supervised screen. C would regress attachments and per-turn model selection for opted-in users, because
the paired runtime does not serve them (C6 "Not yet done" list), and Brain rows are not composed, so Chat would offer
only the deterministic row and harness rows. D is the right end state but depends on the Context Capsule / Task
Compiler, which the governing documents keep as design-only for a later phase.

Alternatives the owner may prefer: A (no Chat change at all until C7), or C limited to installations that never use
attachments or the model selector.

## 6. What was implemented without the owner's decision (and why it needs none)

* `TaskHandoff` (`uri_ui/lib/services/task_handoff.dart`): an inert value with the user's words (trimmed, bounded to
  the `/ask` 64 KiB ceiling), source and provenance ids. It has no executor, approval, digest, ticket or token field.
* `SupervisedExecutionScreen(draft:)`: pre-fills the composer and shows the provenance banner. It sends no frame,
  chooses no executor, confirms nothing and approves nothing. The supervised session id is the screen's own, never the
  conversation's.
* `SupervisedExecutionEntry.open(context, draft:)`: the single navigation seam a Chat action would call. The Tasks entry
  now uses it (no draft), so its behaviour is unchanged.
* Tests (`uri_ui/test/supervised_execution_screen_test.dart`): "a conversation handoff pre-fills the composer only: no
  frame, no executor, no approval" (asserts zero `turn_start`, zero `execution_begin`, zero decisions, Send disabled
  until the user chooses, session `s1` not the chat id), "a handoff is bounded, trimmed and carries no authority
  fields", "an empty handoff shows no banner and leaves the composer empty".

None of this changes what Chat shows or does; the action that would expose it in Chat is NOT wired.

## 7. What the owner's "yes" to B would add (prepared, not done)

1. In `ask_uri_screen.dart`, on a USER message bubble only (never on URI's reply), an overflow action "Make this a
   supervised task", visible only when `SupervisedWorkerRuntime.optInConfigured(...)` is true.
2. It calls `SupervisedExecutionEntry.open(context, draft: TaskHandoff(text: message.text, conversationSessionId: ...,
   messageId: ...))`.
3. Widget tests: action absent without opt-in; absent on assistant messages; present on user messages; tapping sends
   nothing to `/ask` and nothing to the worker.
4. The C6 contract gains one row: "Chat -> supervised task handoff: draft only".

Estimated size: one widget action and four tests. Voice (`source: 'voice'`) uses the same seam once voice parity is
decided.

## 8. Status

| Item | Status | Evidence |
|---|---|---|
| Recommendation (this document) | RESEARCHED / PLANNED | sections 3-5 |
| Handoff value + screen draft + navigation seam | IMPLEMENTED, TESTED (widget) | Flutter suite in `evidence\phase2close\run*\flutter_all.log` |
| Chat action | DESIGN ONLY, BLOCKED on owner decision 2 | section 7 |
| Option C / D | DEFERRED (C7 / later phase) | section 4 |
