# Text and Speech Input Contract — `uri.text_input.v1`

Status: implemented and tested for typed text and SIMULATED transcripts. No speech recogniser is connected to the
Working System; nothing in this contract claims that microphone capture or recognition works.

Implementation: `uri_operational_intelligence/text_input.py` (validation, cleanup, correction cues),
`uri_operational_intelligence/worker_bridge.py` (`oi_turn` accepts the envelope), Dart
`OiConversation.sendTranscript` (`uri_ui/lib/living/integration/oi_conversation.dart`).

## 1. Where it travels

The integrated worker's existing `oi_turn` command takes one optional key, `input`:

```json
{"command": "oi_turn", "session_id": "<uuid>", "text": "<exact transcript>", "depth": "auto",
 "input": {"schema": "uri.text_input.v1", "source": "transcript",
           "transcript": {"raw": "<exact transcript>", "engine": "simulated", "simulated": true,
                          "language": "en-IN", "uncertain": ["Priya near"]}}}
```

Without `input` the turn is typed text, exactly as before (backward compatible). `{"schema": ..., "source": "typed"}`
is also accepted and means the same.

## 2. Fields and rules (fail closed)

| Field | Rule |
|---|---|
| `schema` | must be `uri.text_input.v1` |
| `source` | `typed` or `transcript`; no other keys allowed for `typed` |
| `transcript.raw` | required, non-empty, at most 20 000 characters, and **byte-identical to the turn's `text`**. URI produces the interpretation; the caller never sends a pre-cleaned version, so the original can always be compared with the result |
| `transcript.engine` | required; `"simulated"` **if and only if** `simulated` is true. A real recogniser must name itself (e.g. `faster-whisper-large-v3-turbo`) |
| `transcript.simulated` | required boolean. The UI labels such input "Simulated transcript" everywhere it appears |
| `transcript.language` | optional BCP-47 hint (`en-IN`, `hi-IN`) |
| `transcript.uncertain` | optional list (if present it must be a list) of spans that occur in `raw` and that the recogniser marked low-confidence. URI never "fixes" such a span; when it appears in a draft the user sees a POSSIBLE_MISHEARING review line |
| `mode` | optional, both sources (added 2026-10-09, L-2): `auto` (default, routing unchanged), `dictation` (the words are draft content and never reach Core, even sentences that start with an action verb; sentences that read as instructions get a `DICTATED_INSTRUCTION` info line), `command` (the ordinary path: intent discovery, Core, approvals; never a draft) |
| `scope` | optional, only with `mode: dictation`: `grammar` (default, grammar/spelling/punctuation only) or `rewrite` (professional rewrite keeping every fact) |
| anything else | refused (`INPUT_KEYS`, `TRANSCRIPT_KEYS`) |

Refusal codes: `INPUT_NOT_OBJECT`, `INPUT_SCHEMA`, `INPUT_SOURCE`, `INPUT_KEYS`, `TRANSCRIPT_KEYS`, `TRANSCRIPT_RAW`,
`TRANSCRIPT_TEXT_MISMATCH`, `TRANSCRIPT_SIMULATED`, `TRANSCRIPT_ENGINE`, `TRANSCRIPT_LANGUAGE`, `TRANSCRIPT_UNCERTAIN`, `INPUT_MODE`, `INPUT_SCOPE`.

## 3. What URI does with a transcript

1. Validates the envelope (above).
2. Deterministic cleanup for interpretation only: hesitation fillers (`um`, `uh`, `erm`, `hmm`) and immediate word
   repeats (`the the`) are removed; valid doubles (`had had`, `that that`) are kept. Self-corrections are **not**
   resolved here: "five, sorry, seven" reaches the Brain intact.
3. Routing is identical to typed text (text intent -> draft desk, otherwise the ordinary Operational Intelligence path
   with the cleaned text).
4. The draft keeps `source` (the whole envelope) and `original_text` (the raw transcript, verbatim). The Draft panel's
   Original view shows the raw transcript, labelled "SIMULATED input (no microphone)" when simulated, separately from
   URI's first version ("URI's interpretation").
5. The Brain is told the input was dictated speech and which correction cues were heard; verification then checks the
   draft against the user's own words (see the architecture report §5).

## 4. Integration contract for a future voice pipeline

A recogniser (for example the standalone `feature/uri-dictation` faster-whisper helper, or the voice presentation in
`phase/companion-voice`) integrates by calling, once per finished utterance:

```dart
conversation.sendTranscript(rawText, engine: '<recogniser id>', simulated: false,
                            language: 'en-IN', uncertain: lowConfidenceSpans);
```

Requirements on that pipeline before `simulated: false` may be used:
- the microphone-to-transcript path has been tested with real audio (not synthesised or scripted text);
- `raw` is the recogniser's final text for the utterance, unmodified (no polishing model in between);
- low-confidence spans, if the recogniser reports them, are passed in `uncertain`.

Partial (streaming) transcripts are presentation only and are never sent as turns. Voice-driven editing ("make the
second paragraph shorter", "undo that") needs no new command: the same text intent and draft operations apply.

## 5. Verified

| Check | Evidence |
|---|---|
| Valid envelopes accepted, 11 malformed shapes refused with their codes | `tests/ws/test_ti_store_verify_input.py` |
| Falsey `uncertain` not coerced | `tests/ws/test_ti_audit_r1_regressions.py` (F8) |
| Raw transcript preserved byte for byte from the UI | `uri_ui/test/ws/ti_draft_test.dart` |
| Simulated label on message and draft; real recogniser named | `ti_draft_test.dart` |
| Transcript through the real bridge; raw kept as `original_text`; engine must say "simulated" | `tests/ws/test_ti_desk_bridge.py` |
| Live: simulated transcripts through Runtime v1 | `docs/text_intelligence/evidence/ti_live_matrix_*.json` |
