# URI Text Intelligence — Implementation and Architecture Report

Date: 2026-10-09. Branch `phase/text-intelligence` (worktree `C:\Users\cheta\Development\uri-text-intel`), based on
the accepted Working System tip `68cac3d`. Contract: `TI_BLUEPRINT.md` (frozen; change log §9).
Companion documents: `TI_INPUT_CONTRACT.md`, `TI_TEST_MATRIX.md`, `TI_AUDIT_RECORD.md`, `TI_INTEGRATION_RECEIPT.md`.

## 1. Outcome

URI can now correct, rewrite, draft and revise text through Runtime v1 inside the Living workspace, with versioned
drafts, local edits, deterministic undo/redo, visible fact checks, and a verified text/transcript input contract.
The owner's warden demonstration passed on the real Brain through the real integrated worker, the real Living
widgets and the built Windows app, typed and as a **simulated** transcript.

Nothing here sends, saves, files or executes anything. Speech recognition is **not** operational (no microphone
path); only the transcript interface is implemented and qualified.

Independent audit: Codex round 16 **ACCEPT WITH FINDINGS** (16 rounds). Regression chain: see §8.

## 2. Acceptance criteria status (TI_BLUEPRINT §0)

| ID | Status | Evidence |
|---|---|---|
| TI-AC1 routing | Met (heuristic; residual misses are limitations L-1/L-2) | `test_ti_text_intent.py`, audit regressions, live M18 |
| TI-AC2 versions, original recoverable | Met | `test_ti_store_verify_input.py`, live M1/M12, UI Original view |
| TI-AC3 locality | Met | apply_edits tests, live M1 (`unrelated_blocks_identical`), M11 |
| TI-AC4 factual safeguards visible | Met for the listed checks; reassignment of values is a limitation (L-4) | `test_ti_live_findings.py`, audit rounds 1–16 |
| TI-AC5 clarification | Met | live M10, M14; desk tests |
| TI-AC6 input contract | Met (simulated transcripts only) | `TI_INPUT_CONTRACT.md` §5 |
| TI-AC7 degraded behaviour | Met | live M19, M20; desk tests |
| TI-AC8 no authority change, frozen files untouched | Met | `ws_frozen_check.py` ok; no `core.result`/approval in live journeys; chain §8 |
| TI-AC9 UI | Met | widget tests, live UI test, `screenshots/` |
| TI-AC10 Runtime v1 quality/latency | Met (last live run before Codex r12–15 verifier changes; §6 of the matrix) | `TI_TEST_MATRIX.md` |
| TI-AC11 owner demo on real Brain + real worker | Met | `evidence/ti_worker_live_20261009-073802.json`, `ti_ui_live.json`, screenshots |
| TI-AC12 regression | see §8 | chain summary |
| TI-AC13 independent review | Met: ACCEPT WITH FINDINGS | `TI_AUDIT_RECORD.md` |

## 3. Architecture (what was added; nothing frozen was edited)

```
Living composer (typed | SIMULATED transcript toggle) ─ oi_turn{text, input?} ─▶ integrated worker (unchanged script)
  worker_bridge.IntegratedTurns (WS-owned; additive edits)
    text_input.parse(input)            uri.text_input.v1 validation; raw transcript kept
    DraftDesk.classify(text)           text_intent (deterministic, <2 ms, biased to fall through)
      not a text task ──────────────▶  Orchestrator.handle_turn (unchanged: triage → answer channel / Core)
      UNDO/REDO/ORIGINAL/DISCARD/SHOW  deterministic, no model, works with the Brain stopped
      DRAFT_NEW/EXPAND/CORRECT/REWRITE/REVISE
        one Runtime v1 call (FAST, temp 0, JSON schema over the streaming seam, cancellable)
        model-side guard: actions_requested ≠ [] → hand the turn to the ordinary path (Core decides)
        create: facts-first schema → blocks;   edit: operations on block ids, applied deterministically
        text_verify: checks against the USER's words → flags (error / review / info), never silent rewrites
        draft_store: immutable versions, undo/redo/restore, one block per paragraph
    draft_get / draft_op (button path; no model)       events: draft.updated, draft.clarify, draft.progress
Living UI: OiConversation (draft state) → DraftPanel (version, source label, Current/Changes/Original, flags,
missing items, Undo/Redo/Copy/Close) beside or above the conversation
```

New files: `uri_operational_intelligence/{text_input,text_intent,text_verify,draft_store,draft_desk}.py`,
`uri_ui/lib/living/integration/{oi_draft,draft_panel}.dart`, tests, `scripts/ti_live_matrix.py`, docs.
Edited (additive): `worker_bridge.py` (+commands `draft_get`, `draft_op`, optional `input` on `oi_turn`, fallback
re-routing), `events.py` (+3 event types), `oi_conversation.dart`, `oi_widgets.dart`, `workspace_mode_view.dart`
(mount), `living_composer.dart` (transcript toggle), and the two scope-guard lists (exact paths, WS-D3 pattern).
Not edited: `uri_core/`, `uri_supervisor*/`, orchestrator, triage, answer channel, Runtime v1 config, frozen Dart.

Key design decisions beyond the blueprint (recorded in its change log): the model-side `actions_requested` guard
(audit round 3); "nothing is excused silently" (round 9); partial fact matches are review lines (round 12).

## 4. Implementation status ledger (separated as the owner asked)

| Capability | Status | Evidence / gap |
|---|---|---|
| Text correction (grammar, spelling, punctuation) | **Implemented, live-qualified** | M12; grammar-only meaning checks |
| Rewriting, expansion, drafting (letters, e-mails, notices, circulars, reports, notes) | **Implemented, live-qualified** | M1–M17 |
| Revision of an active draft, versions, undo/redo, compare | **Implemented, live-qualified (worker + widgets + app)** | M1, M11, M13, M15; UI evidence |
| Speech-transcript handling (`uri.text_input.v1`, self-correction resolution, raw kept) | **Implemented and qualified with SIMULATED transcripts only** | M2, M3, M5, M6, M7, M9; worker + UI journeys |
| Actual speech recognition (microphone → transcript) | **Not implemented here. Not operational.** | Contract for a future recogniser: `TI_INPUT_CONTRACT.md` §4 |
| Voice-driven editing (spoken instructions end to end) | **Not operational** (depends on recognition); the same text path would serve it | — |

## 5. Limitations (owner acceptance needed where not already in the blueprint)

| ID | Limitation | Classification |
|---|---|---|
| L-1 | Text-intent routing is a heuristic. Misses either fall through to the unchanged ordinary path (safe) or, for actions, are caught by the model-side guard; a request phrased outside both can still be drafted without the action being carried out (the draft says nothing was sent). | Blueprint D2 (biased to fall through); residual needs acceptance |
| L-2 | Dictated content with sentence-initial action verbs and no colon ("Write a notice. Send the form by Friday.") goes to Core instead of the desk (safe misroute). | Safe-path misroute; needs acceptance |
| L-3 | Verifier precision: review lines appear on some correct drafts (e.g. CORRECTION_UNCONFIRMED, FACT_REWORDED after tone changes). | Noise; needs acceptance |
| L-4 | Value **reassignment** ("Monday: 7; Tuesday: 8" → swapped) is not detected deterministically; the Changes view shows it. | Accepted by audit round 11 as outside TI-AC4; needs owner acceptance |
| L-5 | Replacement matcher abbreviation list ("Capt." can cut a replacement) and other residual verifier heuristics. | Audit round 16 limitation; needs acceptance |
| L-6 | Runtime v1 quality: occasional escalation wording or placeholder lists in letters (flagged, reduced by prompt), one paragraph miscount in 4 tone revisions. | Model quality; shown to user |
| L-7 | Drafts live in the worker's memory per session: lost when the worker restarts; one active draft per session. | Blueprint D3 |
| L-8 | Physical app: Runtime v1 decode 33–40 tok/s while the Living app holds ~450 MiB GPU (accepted WS finding PERF-W1); the stacked Draft panel is small while the context panel is open. | Existing WS finding; UX follow-up |
| L-9 | No live run after the final verifier commits (Codex rounds 12–15); unit-tested only. | Evidence gap, stated in the matrix §6 |
| L-10 | Missing-information list can repeat a placeholder in other words ("[Your Name]" and "Sender's name"). | Cosmetic |

## 6. Correction history (auditable; nothing rewritten)

1. **GPU collision (07:05–07:08).** After the machine rebooted, this session started Runtime v1 with the accepted host
   *without* the new machine-wide GPU lease while the WS hardening session's `restart_experiment` held it. Two
   llama-servers loaded for ~2 minutes; that experiment ended with zero runs. This session stopped its host at 07:08
   and from then on ran only under the lease (07:10–07:56). The hardening session's experiment may need rerunning.
2. **Disproved:** "classifier smoke tests are enough" — Codex rounds 1–4 found real Core-routing gaps.
3. **Disproved:** "heuristic correction stripping reduces noise safely" (rounds 5–8); replaced by verified
   supersession and visible info lines (round 9).
4. **Disproved:** "the first live run's error flags indicate model errors" — most were verifier false positives
   (LQ-1..LQ-23); and several precision fixes then hid real changes (round 12), repaired in rounds 12–15.
5. Commit `170b180` was made with two failing regressions (tests ran but the commit was chained after `tail`);
   fixed in `6a141ad`. A `sed` edit converted two CRLF guard files to LF in `2147a2c`; restored in `92e01d1`.
6. First regression-chain attempt was invalid (evidence directory inside the tree; tree not in the accepted
   `<dir>\uri-agent` + `evidence\` layout): 5 harness failures, rerun in the accepted layout (§8).
7. The physical app first showed WORKER_EXITED: the frozen C1 gate pins the `git` binary found on PATH at
   provisioning (Git Bash vs PowerShell). Launching from the provisioning environment fixed it; recorded as an
   environment property, not a defect of this feature.

## 7. Coordination

- `integration/ws-hardening-20261009` (another session) edits `worker_bridge.py` and the worker script (uncommitted at
  inspection; their diff also showed line-ending churn). This phase's bridge edits are additive and small; a merge of
  both will conflict textually in `COMMANDS`/imports and in the two scope-guard lists, not semantically.
- `phase/companion-voice` (voice presentation, simulated) and `feature/uri-dictation` (standalone faster-whisper
  helper) are the candidate transcript sources; neither was modified.
- GPU: all live runs after 07:10 under the machine-wide lease; the lease was released at 07:56.

## 8. Regression

| Gate | Result |
|---|---|
| `tests/ws` (incl. accepted WS tests) | 207 passed, 10 skipped |
| `tests/oi` | 161 passed, 8 skipped at 18f79ba. An earlier run had 1 failure, `test_total_deadline`, a timing flake that also fails on the untouched baseline `68cac3d` (3 of 4 runs there) |
| Flutter full suite | 301 passed, 4 skipped |
| `ws_frozen_check.py` | ok: 121/121 Phase 1 files identical; no protected path changed |
| Accepted chain (gate tree materialized at 9402c94, accepted layout) | phase2 486 passed / 0 failed / 2 skipped (= accepted baseline); remaining gates: see `TI_INTEGRATION_RECEIPT.md` |

## 9. Evidence index

`docs/text_intelligence/evidence/`: five live matrix runs (`ti_live_matrix_fast_*.json`), real-worker journey
(`ti_worker_live_20261009-073802.json`), live UI receipt (`ti_ui_live.json`). `docs/text_intelligence/screenshots/`:
real-app captures with provenance JSON (`capture_run_*.json`).
