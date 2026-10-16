# UI-V2-POSTINT — UI V2 post-integration repairs (2026-10-16)

Owner task 2026-10-16 "URI UI V2 — post-integration repair, lifecycle driver correction & live qualification".
UI V2 is integrated in canonical (`integration/git-sync-20261008` @ `2eff03d086e3cacbcd2682bf4f75b7e51d4fa919`,
Codex ACCEPT, receipt branch `receipts/ui-v2-20261016` @ `74044f77`). It is **not frozen and not production-ready**.
This milestone repairs the registered findings UIV2-F1..F5 without rebuilding or replacing UI V2.

- Branch `milestone/ui-v2-postint-20261016`, worktree `C:\Users\cheta\Development\uri-ui-v2p`.
- Based on DEV-LIFECYCLE-3B (`milestone/dev-lifecycle-3b-flutter-gates-20261016`, the DRV-3 driver repair, its own
  milestone and review), so this milestone's Flutter gates carry real execution evidence. The two are integrated in
  order: DEV-LIFECYCLE-3B first. Attribution: driver changes only under `scripts/dev_workflow/**`,
  `tests/dev_workflow/**`, `docs/dev_workflow/**` (DEV-LIFECYCLE-3B); UI V2 changes only in the paths below.
- Run folder `C:\Users\cheta\Development\uri-ui-v2p-run` (materialized runtime `runtime2` from the code commit,
  installation `uiv2p-a`, harness copied from the UI V2 completion run, lifecycle state `lifecycle/`).

## Classification

| Capability | Class | Verified through |
|---|---|---|
| F1 draft integrity (Text Intelligence routing + draft retention) | INDIRECT | Workspace and Companion chat journeys J14, J7 |
| F1 draft scope in the UI (Workspace only) | USER_FACING | J14, J7 (Companion note, mode command) |
| F2 testing-only composer controls | USER_FACING | J14 (absent for ordinary users) |
| F3 layout during the shrink into Companion | USER_FACING | J11, J7, flutter-error count over every journey |
| F4 Lunar edge on light themes | USER_FACING | J15 + returning-run pixel check at the renderer bounds |
| F5 visual fidelity | USER_FACING | evaluation only (below) |

## Findings, root causes and repairs

### UIV2-F1 (P1) — Companion chat may silently edit an open draft

Reproduced deterministically on canonical: with a draft open, `text_intent.classify` returned `REVISE` for
"Say hello in three words" (the live l9 case), "Write a haiku about rain", "Call me Ravi", "It's raining today",
"Not now", "Use a calm voice please", "Start a timer", "Update me on the weather", "Put some music on", "Mark this as
done", "Spell necessary", "Change of plans, …", "Make me a plan for the week", "Add milk to my shopping list",
"Summarise the news", "Simplify my life", "Fix my wifi". Root causes:

1. `_REVISE_START` treats any message opening with a revision-like verb as an edit of the open draft, with no check
   that the message refers to the document (`text_intent.py`).
2. The surfaces that do not show the draft (Companion chat, dashboard composer, voice outside the Workspace) send the
   same `auto` turn as the Workspace, so the desk edits a document the user cannot see.
3. A new document (create, dictation, correct-with-text) replaced the open draft with no way back (`DraftDesk._set`).

Not causes (checked): A2UI (`schedule_intent` handoff drops a draft question only), cross-session interference (drafts
are keyed by session id; Companion and Workspace share one conversation by design), concurrent buttons (`draft_op`
is refused while a turn runs), persistence (drafts live in the worker; a restart drops them and says so, TI L-7).

Repairs:

- Classifier: with a draft open, weak chat-like openers count as an edit only when **anchored** to the document: a
  named part with a determiner ("the date", "a line"), a pronoun object ("address it …"), quotes, "instead",
  a correction form ("X, not Y", "I meant …"), the existing revision vocabulary, or the draft's own words (two shared
  content words or a shared number, `draft_text`). Strong edit verbs (remove, replace, rephrase, don't …) are
  unchanged. Rewrite/correct verbs without text ("Summarise the news") edit only when their object is the draft.
  An open draft question is still answered in the draft's context.
- UI: the draft changes only from the Workspace conversation (`UiPresentationController.draftInView`). Elsewhere a
  turn goes as input mode `command` (existing TI L-2 contract: the ordinary path, never a draft). The Companion chat
  says "A draft is open in Workspace. Messages here do not change it." Dictation stays explicit content.
- Explicit target (revision after review rounds R1–R3, 2026-10-16): three Codex rounds each found new
  counterexamples for the classifier in both directions ("Change the date of my appointment to Friday" taken as an
  edit; "Replace the name with Ravi" missed). A deterministic classifier cannot decide intent for every
  conversational sentence, and "make it shorter" is genuinely ambiguous between the last answer and the draft. The
  guarantee is therefore an explicit, visible target: while a draft is open the Workspace composer shows a chip,
  "To: conversation" (default) or "To: <type> draft"; one tap switches; the draft panel also offers "Change this
  draft with URI" (pencil) and "Answer" on its open question. Two new input modes carry the target to the worker:
  `conversation` routes as if no draft were open (no revision can be produced; a draft operation the user types
  exactly, such as "undo" or "close the draft", is carried out deterministically (review C2-02); a new document
  request still starts a new draft and the open one is kept for Undo; an answer to a pending new-document question
  continues that new document (C2-01); an open draft question is dropped), and
  `draft` makes the message an instruction for the open draft unless it is a draft operation, an explicit new
  document ("new", "another", "separate", or a different document type than the open draft, C2-03), an answer to a
  pending new-document question (C2-01; the panel then says "About your new document: ... Answer in the
  conversation." and offers no Answer button) or an action only Core may take; the desk's model can still answer that a
  message is not an edit. After round R4 (BLOCKED RETRY_LIMIT, diagnosis: the default draft target let ordinary
  requests into the inference gate) the default is the conversation, so the classifier is no longer part of the
  safety boundary in either direction; the R4 classifier restructure (`eac2da0b`) was reverted (`git revert`) because
  it broke accepted auto-mode behaviour (TI lq13) and is not needed with explicit targets. Every draft change is
  visible (version, Changes view) and reversible (Undo). A new draft starts with the conversation as target.
  Owner preference recorded below: the default target.
- Retention: a new document keeps the drafts it replaced as a chain of up to five (`DraftDesk.MAX_REPLACED`). Undo
  on a first version brings the previous draft back unchanged; Redo returns; a new edit ends the way forward; Close on
  a draft that replaced another brings that one back. The draft panel says "Replaced your earlier
  <type> · Undo brings it back". No confirmation prompt is added for conversation.

### UIV2-F2 (P2) — testing-only transcript and dictation controls visible to ordinary users

The composer showed the simulated-transcript and typed-dictation toggles whenever it was not minimal. They are now
shown only with `URI_UI_TESTING_TOOLS=1` (read once, like `URI_UI_VISUAL`) and only when the row is wide enough. The
voice settings' dictation and the TI contract are unchanged.

### UIV2-F3 (P2) — brief layout overflow entering Companion Mode

Evidence (l13/l11): `draft_panel.dart:50` Column (69 px), `living_composer.dart:139` Row (54 px),
`oi_widgets.dart:76` Column (34 px). New widget tests over window sizes 1280×860 … 360×300 and pixel ratios 1–2 found
more: the workspace rail Column (90 px), the Brain-bar pickers (96 / 156 px). Root cause: Columns with fixed parts
and one flexible body laid out in a box shorter than the fixed parts (the one-frame shrink, short windows), and
pickers wider than a narrow pane. Repair: `ScrollWhenShort` (`CustomScrollView` + `SliverFillRemaining
(hasScrollBody: false)`; the flexible body reports a small intrinsic height through `ShortIntrinsic`): when the
height is enough the layout is unchanged; otherwise the whole panel scrolls. Pickers are bounded (260 px) and
ellipsize; the composer's optional buttons step aside on narrow rows; the draft version label ellipsizes.

### UIV2-F4 (P3) — faint rectangle around Lunar on light themes

`companion_lunar.frag` writes premultiplied emissive output with `a = max(rgb)` after a sky field and a ±0.5/255
dither that never reach exactly zero at the square's bounds; the low-resolution path's scaling also samples the edge
row. On a light background those near-zero pixels showed as a faint frame (UX-D2: 3/255 lines). Repair at the end of
`main()`: fade the output to exactly zero over the outer 1.5–10 % of the square and drop sub-1.5/255 haze. True alpha,
the borderless window and the renderer's identity are kept; no background, no extra pass. The shader pin in
`companion_settings_test.dart` is updated for Lunar only (owner-requested repair); every other shader is unchanged.

### UIV2-F5 (P3) — visual fidelity relative to the approved reference

Evaluation, not redesign. Reference authority (docs/ui_v2/VISUAL_QUALIFICATION.md): Companion "Detached chat"
(`evidence/reference/companion-approved.jpg`, owner-approved 2026-10-13) and the dashboard reference plus three theme
studies. Last measurement: dashboard 0.879 local-luminance SSIM (above 0.80), Companion 0.634 (below the owner's 80 %
target, which is not established). Listed differences: Solar renderer details vs the generated sun (identity kept by
design), compact sizes keep 80 px controls, chat font/bubble padding/composer spacing, artwork fade, 390 px dashboard
heading clip. This milestone repairs only differences that are defects shown by evidence (layout overflow, F3) and
records the rest for the owner: a closer Companion match would replace the approved working renderer and controls
with an imitation, which the owner rules exclude. F5 stays OPEN as an owner preference decision with the evidence.

## Independent reviews

Driver-counted reviews are Codex rounds inside the lifecycle states (`uri-ui-v2p-run/lifecycle/`). Codex hit its
usage limit three times on 2026-10-16; per the owner ("If codex is unavailable use an independent claude agent"),
independent read-only Claude agents reviewed in between. Their results are imported, not driver-counted (owner
decision D1):

- C1 on `cf97a1a8` (`review_C1_claude_agent_cf97a1a8.txt`): repaired in `0129f3b3`.
- C2 on `486f8ba9` (`review_C2_claude_agent_486f8ba9.txt`): REJECT. C2-01 HIGH (an answer to a pending
  new-document question edited the unrelated open draft through mode draft, and could not be answered in mode
  conversation), C2-02 MEDIUM (typed draft operations under the conversation target went to the Brain), C2-03 LOW
  (a different document type said to the draft revised it), C2-05 LOW (docs said one-level retention) and C2-07 LOW
  (missing tests) are repaired with tests. C2-04 LOW (deep + conversation routes text tasks to the desk while deep +
  auto does not) and C2-06 LOW informational (mode draft relies on the desk model's guard for non-text actions; no
  bypass) stay open as recorded limitations.

## Acceptance criteria

- AC-1 (F1) Deterministic boundary: the open draft changes only after the user explicitly targeted it. No turn from a
  surface that does not show the draft (mode `command`) and no Workspace turn with the default target
  "To: conversation" (mode `conversation`) can change it (Python `tests/ws/test_uiv2_postint_target_modes.py`,
  Flutter `uiv2_postint_test.dart`, live J7-draft-untouched, J14-chat-does-not-edit, J14-target-conversation).
  The auto-mode classifier keeps its regression tables for older clients and the worker contract
  (`test_uiv2_f1_draft_integrity.py`, `test_uiv2_postint_r2_regressions.py`, `test_uiv2_postint_r3_regressions.py`).
  Every draft change is visible and reversible.
- AC-2 (F1) Explicit edits still work (J14-explicit-edit-applies; existing TI suites unchanged except two tests whose
  trigger message was chat-like and is now anchored).
- AC-3 (F1) A new document keeps the replaced draft; Undo restores it unchanged, Redo returns (J14, Python tests).
- AC-4 (F1) Surfaces that do not show the draft send mode `command`; the Companion says a draft is open (Flutter
  `uiv2_postint_test.dart`, J7-draft-note).
- AC-5 (F2) No testing-only composer controls without `URI_UI_TESTING_TOOLS` (Flutter, J14-no-testing-controls).
- AC-6 (F3) No RenderFlex overflow over the size/scale matrix (Flutter) and no new flutter error in any live journey
  (J11, J7, summary `flutter_errors`).
- AC-7 (F4) On a light theme the Lunar renderer's bounds are invisible: max channel difference ≤ 1/255 between
  pixels inside the bounds and the background outside (J15 and the returning run), alpha kept.
- AC-8 Preservation: Workspace, Dashboard, Assist, Companion, companion selections, theme independence, orb animation
  and interaction, voice states, Core/Brain integration, Office integration, onboarding, controls,
  `URI_UI_VISUAL=living`; all earlier journeys J1–J13 and the returning run still PASS; full Flutter and Python suites
  show no new failure; frozen check OK.
- AC-9 Performance: no new persistent timer, saveLayer or shader pass; Lunar adds a few ALU instructions; Brain tok/s
  and UI GPU memory within the earlier record's range.
- AC-10 Independent driver-counted review of the whole diff (Codex) ACCEPT or ACCEPT WITH FINDINGS; live record PASS
  on the exact code commit; final revision reviews the record.

## Owner decisions (not taken here)

- Canonical integration of DEV-LIFECYCLE-3B and of this milestone (not authorized).
- F5: whether any further Companion resemblance work is wanted, given the rule not to replace the working renderer.
- F1: the Workspace composer's default target while a draft is open: the conversation (chosen: strictest, the draft
  changes only on explicit intent; each edit series needs one tap first) or the draft (fewer taps, but ordinary chat
  typed while it is the target is taken as an instruction for the draft).
- `\URIServer` legacy task disable (privileged; evidence in `01_LEGACY_AND_RECEIPTS.md`).
