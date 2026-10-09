# URI Text Intelligence — Frozen Implementation Blueprint

Date: 2026-10-09. Author: Claude. Branch `phase/text-intelligence`, worktree
`C:\Users\cheta\Development\uri-text-intel`, created from the accepted Working System tip `68cac3d`
(`integration/working-system-20261008`, Codex WS round 8 ACCEPT WITH FINDINGS).
Status: FROZEN for implementation. Changes after freeze are recorded in §9.

## 0. Acceptance criteria (defined before implementation)

| ID | Criterion | Evidence |
|---|---|---|
| TI-AC1 | Routing: drafting, correction, rewriting, expansion, revision and undo requests go to the draft desk; greetings, questions and analysis keep the existing fast paths unchanged; send/save/file/email-it requests still go to Core | `tests/ws/test_ti_text_intent.py` (deterministic, incl. Hinglish) |
| TI-AC2 | A draft has versions. Each revision makes a new version; undo/redo move between versions; version 1 and the original input (typed text or raw transcript) stay recoverable | `test_ti_draft_store.py` |
| TI-AC3 | Revisions are local: blocks the edit does not target are byte-identical; when the instruction names a specific paragraph and no whole-document scope, edits outside it are dropped and reported | `test_ti_draft_store.py`, `test_ti_desk.py` |
| TI-AC4 | Factual safeguards: facts the Brain reports must come from the user's words; superseded values must not remain; user exclusions ("don't mention X") must not appear; grammar-only corrections must keep numbers, dates and names. A violation is shown to the user as a flag, never hidden | `test_ti_verify.py` + live matrix |
| TI-AC5 | Clarification: an ambiguous correction produces a short question and no new version | unit + live |
| TI-AC6 | Speech input contract `uri.text_input.v1`: transcript input carries raw text, engine, `simulated`; the raw transcript is preserved and shown apart from the interpretation; malformed envelopes are refused | `test_ti_bridge.py`, Dart tests |
| TI-AC7 | Degraded behaviour: with the Brain not READY, Brain-needing text tasks fail with BRAIN_UNAVAILABLE and no version change; undo/redo/original/discard still work; cancellation leaves the draft unchanged | unit + live |
| TI-AC8 | No authority change: drafting never sends, saves, overwrites or executes; approval/refusal behaviour of the Working System is unchanged; no frozen file edited | frozen check, existing WS/OI suites |
| TI-AC9 | UI: the Living workspace shows the current draft, version, change preview (changed blocks marked), compare with original/previous, Undo/Redo, flags and missing items, and labels transcript input as SIMULATED when it is | widget tests + real-app screenshot |
| TI-AC10 | Runtime v1 quality and latency measured on a representative matrix (self-correction, misheard names, dates/numbers, Hinglish, Indian English, long dictation, multiple corrections, contradictions, paragraph revision, grammar-only, cancellation, Brain unavailable) with per-case pass/fail and timings | `docs/text_intelligence/evidence/*.json` |
| TI-AC11 | The owner's four-step warden demonstration runs end to end on the real Brain through the real integrated worker, input labelled typed or simulated transcript | live JSON receipt |
| TI-AC12 | Regression: OI + WS suites, Flutter full suite, frozen check and the accepted chain pass with the known baseline failures only | logs |
| TI-AC13 | Independent Codex review; valid findings repaired and affected tests rerun | verdict file |

## 1. What exists (inspected 2026-10-09)

| Area | State |
|---|---|
| Core (`uri_core/`) | Frozen. Has drafting tools (`draft_institutional_note/order`, `generate_document`) but the Working System qualifies only `remember_fact` and `external_harness_task`. Core is the authority for actions, not a text editor. |
| OI triage | `URI draft a letter ..., sorry seven ..., Make it formal.` is classed ACTION (two imperative clauses) and sent to Core, which has no drafting capability: today the success demo fails. |
| OI answer channel | Language-only replies, "drafts ... in the reply itself". No draft state, no versions, no revision locality, no fact checks. |
| Living UI | Conversation pane renders `uri.oi.event.v1`; no draft surface. |
| Speech | No microphone-to-transcript path in the Working System. `feature/uri-dictation` (standalone faster-whisper helper, 2026-10-02, not integrated) and `phase/living-companions` voice presentation (uncommitted, another session) exist outside this baseline. Speech recognition is NOT operational here. |
| Parallel work | `integration/ws-hardening-20261009` edits `worker_bridge.py` and the worker script (uncommitted). This phase keeps its edits to those files small and additive. GPU is shared: live runs wait for a free GPU. |

## 2. Decisions

- D1. The capability lives in Operational Intelligence as language work (no authority), in new modules. Core,
  the answer channel, the orchestrator and the triage module are not edited. Actions in the same request (send,
  save, file) still go to Core through the existing path.
- D2. A deterministic text-intent classifier runs before the orchestrator in the worker bridge. It is biased to
  fall through: when it is not sure, the turn goes to the existing path.
- D3. Draft model: ordered blocks with roles (recipient, subject, salutation, body, closing, signature, line). Body
  blocks are the "paragraphs" users refer to. Versions are immutable snapshots; undo/redo move a cursor; a new
  revision after undo drops the redo tail. In memory per session in the worker (bounded); lost with the worker.
- D4. Brain calls use Runtime v1 FAST tier (thinking off), temperature 0, JSON schema output over the streaming
  seam (`complete_json`). One call per create, revise or correct. Progress is reported as character counts.
- D5. Revisions are edit operations on block ids, applied deterministically. The model never returns the whole
  document for a local edit.
- D6. Verification is deterministic and runs after every Brain call. Violations become flags shown with the draft.
  One automatic repair is not attempted: the user sees the flag and decides (no silent rewrite).
- D7. Deterministic cleanup (fillers, repeated words, spacing) is applied to transcripts before interpretation; the
  raw transcript is kept. Grammar needs the Brain.
- D8. Undo, redo, show original, discard and draft read are deterministic and work with the Brain stopped. Buttons
  use a structured `draft_op` command; typed or spoken "undo the last change" uses the same operation.
- D9. A stronger harness is considered only if the live matrix shows Runtime v1 failing an important task.

## 3. Data flow

```
UI (typed | simulated transcript) --oi_turn{text, input?}--> worker bridge
   bridge: validate input contract -> text_intent.classify(text, active draft?)
      not a text task  -> Orchestrator.handle_turn (unchanged)
      text task        -> DraftDesk.handle(turn): undo/redo/... (no model) | Brain JSON call -> verify -> new version
   events: turn.started, turn.routed{route:"draft"}, companion.state, draft.progress, draft.updated | draft.clarify,
           answer.delta (one-line summary), answer.done, error, turn.finished
UI: OiConversation keeps the latest draft; DraftPanel shows it with versions, compare, undo/redo, flags.
```

## 4. Work items

| # | Item | Files |
|---|---|---|
| T1 | Text intent classifier | `uri_operational_intelligence/text_intent.py` (new) |
| T2 | Draft store, blocks, versions, diff, locality | `uri_operational_intelligence/draft_store.py` (new) |
| T3 | Transcript contract + deterministic cleanup + correction markers + verification | `uri_operational_intelligence/text_input.py`, `text_verify.py` (new) |
| T4 | Brain prompts, schemas, DraftDesk | `uri_operational_intelligence/draft_desk.py` (new) |
| T5 | Bridge hook: `oi_turn` optional `input`, `draft_op`, `draft_get`; event types | `worker_bridge.py`, `events.py` (small additive edits) |
| T6 | Dart: draft state in `OiConversation`, transcript send, `draft_op` | `uri_ui/lib/living/integration/oi_conversation.dart` |
| T7 | Dart: `DraftPanel`, simulated-transcript composer toggle, mount in workspace | `uri_ui/lib/living/integration/draft_panel.dart` (new), `workspace_mode_view.dart` (mount only) |
| T8 | Tests (Python unit, Dart unit/widget, live matrix runner, live worker demo) | `tests/ws/test_ti_*.py`, `uri_ui/test/ws/ti_*`, `scripts/ti_live_matrix.py`, `scripts/ti_live_demo.py` |
| T9 | Scope guards: exact new paths (WS-D3 pattern) | `tests/phase2a/test_frozen_core.py`, `scripts/phase2close_chain.py` |
| T10 | Reports: architecture, input contract, test matrix, quality/latency, audit verdict, receipt, limitations, status ledger | `docs/text_intelligence/**` |

## 5. Stop conditions

Stop and report if: a frozen file would need editing; a path lets drafting send, save or execute; a Brain output
changes the Brain selection or approves anything; the classifier would route an action request away from Core;
a second resident model would be started.

## 6. Out of scope

Microphone capture and speech recognition (contract only), text-to-speech, saving drafts to files, sending email,
cross-restart draft persistence, production cutover, launcher changes.

## 9. Change log

- 2026-10-09: initial freeze.
- Audit round 3: added a model-side action guard (`actions_requested` in both JSON schemas; non-empty hands the turn
  to the ordinary path, the same pattern as the answer channel's ACTION marker). Refines D2; no architecture change.
- Audit round 7/9: D6 refined — the verifier never excuses an absent detail silently; it only chooses severity
  (error / review / info), and an excused value is shown as an info line.
- Audit round 12: partial fact matches are FACT_REWORDED review lines, never "present".
- Live run: D3 refined — one block per paragraph is enforced deterministically (`split_paragraphs`), including edits.
- Live run: deterministic clarification for "change the date" when several dates exist (TI-AC5), no model call.
- Live run: work item T8 used the accepted machine-wide GPU lease (WS hardening) for every Runtime v1 start after
  07:10; see the report's correction history for the 07:05 collision.
