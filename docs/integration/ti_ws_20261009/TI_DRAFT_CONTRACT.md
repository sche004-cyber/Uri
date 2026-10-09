# Text Intelligence draft contract: `uri.ti.draft.v1`

Status: IMPLEMENTED on `integration/ti-on-ws-hardening-20261009` (the snapshot schema tag and execution state were
added in this phase; every other field existed and is tested). This is the contract the Living Draft panel uses today,
and the one a future A2UI draft surface must consume. A2UI renders it and does not re-implement drafting: the draft
desk stays the only producer.

## 1. Where it travels

| Channel | Shape |
|---|---|
| `draft.updated` event (`uri.oi.event.v1`) | `{"op": "created" \| "revised" \| "corrected" \| "rewritten" \| "restored" \| "undo" | "redo" | "show" | "original" | "discard" | "unchanged"\| "redo" \| "original" \| "discard" \| "unchanged", "draft": <snapshot> \| null}` |
| `draft.clarify` event | `{"question": str \| null, "draft": <snapshot> \| null}`. The question is open for one user turn |
| `draft.progress` event | `{"chars": int}` (structured output generated so far) |
| `draft_get` command | `{"command": "draft_get", "session_id"}` returns `{"draft": <snapshot> \| null}`. Allowed while a turn runs |
| `draft_op` command | `{"command": "draft_op", "session_id", "op": "undo" | "redo" | "show" | "original" | "discard" | "unchanged"\| "redo" \| "discard" \| "restore", "version"?: int}` (`version` only with `restore`) returns `{"draft", "op"}`. Deterministic, no model, no authority. Refused while a turn runs |

## 2. Snapshot (`Draft.to_dict`, `uri_operational_intelligence/draft_store.py`)

| Field | Meaning | Requirement covered |
|---|---|---|
| `schema` | `"uri.ti.draft.v1"` | versioned contract |
| `execution` | `{"state": "NOT_EXECUTED", "sent": false, "saved": false, "note"}`. Always this value: a draft never acts. Approval and execution of actions belong to Core's own events (`approval.required`, `core.result`) | approval and execution state |
| `original_text`, `source` | the user's words as received (the raw transcript for speech), and the input envelope: `typed` / `transcript`, engine, `simulated`, `mode` (`dictation`), `scope` | original text |
| `first` | version 1 (URI's first interpretation) | original vs interpretation |
| `current` | the current version: `blocks[{id, role, text}]`, `text`, `op`, `summary`, `instruction`, `changed[block ids]`, `removed[block ids]`, `flags[{code, severity, detail}]`, `facts`, `exclusions`, `missing` | revised draft; detected concerns |
| `previous` | the version before `current` (the basis of the Changes view) | changes / diff |
| `history[{n, op, summary, instruction}]`, `version`, `position`, `count`, `can_undo`, `can_redo` | version history and the undo/redo cursor | history, undo/redo |
| `pending_question` | the open clarification, if any | clarification |
| `draft_id`, `doc_type`, `tone` | identity and kind | — |

Diff: `changed` / `removed` are authoritative at block level. Word level is computed by the renderer from `previous`
and `current` (Dart `wordDiff`); a renderer must not compute block changes itself.

Concerns: `flags[].severity` is `error`, `review` or `info`. All three are always shown; nothing is hidden. Codes are
listed in `text_verify.py`. They include the L-4 reassignment flags `VALUE_REASSIGNED` (review) and
`VALUE_REASSIGNED_AS_ASKED` (info), and the L-2 `DICTATED_INSTRUCTION` (info).

## 3. Rules a consumer must keep

1. Never send, save or execute from a draft surface. A "send" button would be a request through the ordinary turn
   path, where Core decides and asks for approval. It is not a draft operation.
2. Map buttons only to `draft_op` (`undo`, `redo`, `restore{version}`, `discard`) or to a new user turn. For A2UI, the
   action registry entries would be `draft.undo`, `draft.redo`, `draft.restore` and `draft.discard`, each bound to
   the `version`/`position` shown (stale-version refusal, as A2UI's digest rule requires).
3. Show `original_text`, `first`, `previous` and `current` as the Original / Changes / Current views. Label simulated
   transcripts as SIMULATED and dictation as Dictation (`source.mode`).
4. After the worker restarts or exits, the snapshot is gone (drafts live in worker memory, TI L-7). Clear or disable
   the surface as the Draft panel does (INT-1, INT-2).

## 4. Compatibility status with `phase/a2ui`

`phase/a2ui` (`602fe4d`, active, uncommitted work) is not modified or used here. Its v0.9.1 subset and catalog can
express this contract: `Card`/`Text` for blocks, `Badge(tone)` for flags, `List` for history, and `Button` actions
through its registry. The existing Draft panel stays the drafting UI until an A2UI draft surface is implemented,
tested and independently accepted.
