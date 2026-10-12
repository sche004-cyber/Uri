# A1 — Guided Learning and Smart Fill: design (NOT IMPLEMENTED)

Status: **design only**. The A1 entry gate (plan §5) is not met, so no A1 code exists. This document is for owner
review; the write-capable controls it describes must not be connected until the owner approves this contract.

## 1. Entry gate (all required before any A1 code)

| Gate | State (2026-10-10) |
|---|---|
| A0 independently accepted by Codex | **NOT MET** (Codex not available in this session) |
| A real browser channel (extension → worker) or UIA adapter running on the PC, with the redaction tests passing against live pages/windows | **NOT MET** (snapshot script tested in Chromium; channel and UIA not built) |
| Owner approval of the Insert grant contract (§4) | **NOT MET** |
| Owner approval of workflow storage, retention and deletion (§5) | **NOT MET** |
| A0 vision pathway qualified on the PC, if Smart Fill uses screenshots | **NOT MET** (Smart Fill must work from DOM/UIA alone first) |

## 2. Teach URI (explicit demonstration → reviewable workflow)

1. The user presses **Start teaching** in the Assist view (requires an ACTIVE scope with Observe, plus a new
   `remember` permission scoped to *this teaching session only*).
2. While teaching, the adapter records **structure only**: an ordered list of steps `{action: focus|type|select|
   click, target: {role, name, label, automation_id | css-path-hash}, value_kind}`. Values are never stored; a typed
   value is recorded as its *kind and provenance* (`literal_from_example`, `copied_from_field:<label>`,
   `date`, `number`, `email`), never its text. Sensitive fields (redaction rules) record only "user filled a private
   field". Clicks on submit/pay/send/delete-like controls are recorded as **stop points**, never as steps.
3. Stop → URI shows the inferred workflow: steps, field mappings, repeated blocks, and an explicit uncertainty list
   ("I couldn't tell whether 'Section' always comes from the class list").
4. The user edits, deletes steps, renames, sets the matching rule (origin / window process + title pattern), and
   approves **Save**. Nothing is saved before that click. Saved workflows are listed in Workspace ▸ Workflows with
   Disable and Delete.

Inference (deterministic first): align repeated demonstrations by target identity; infer per-field value sources by
exact match against other visible fields/selection (copy), constant (literal), or simple transforms (date reformat,
case, trim, split on separator) — the same family as Flash Fill's program synthesis over a small DSL
(`concat(substr(field, i, j), const)`), solved by enumeration over examples, accepting a program only when it
reproduces **all** examples and is unique up to equivalence. If ambiguous → surface the alternatives; the Brain is
consulted only to *name* steps or to propose a mapping the user must confirm.

## 3. Smart Fill

1. Requires Observe + Suggest on the scope; produces a **preview table**: field, current value, proposed value,
   source ("from your workflow 'Fee form'", "from the e-mail field above", "pattern from 3 examples"), confidence.
2. Nothing is inserted until the user selects rows and presses **Apply selected**.
3. Batch apply: one approval for N chosen rows creates a single-use Insert grant (§4) for exactly those rows.
4. URI **never submits**. After insertion it re-reads the fields and shows what changed; the submit button stays
   the user's.

## 4. Insert grant contract (needs owner approval)

```
InsertGrant {
  grant_id, scope_grant_id, generation,          # bound to the ACTIVE Assist grant; dies with it
  target_id, origin_or_process,                  # the exact tab/window
  rows: [{field_fingerprint, before_digest, value_digest}],   # what the user saw and approved
  issued_at, expires_at (≤ 60 s), uses: 1
}
```
Execution re-captures the target and refuses unless every field fingerprint matches, every `before_digest` equals the
field's current value digest (no change since the preview), the generation is current, and the value inserted hashes
to `value_digest`. Sensitive fields are never insertable. A stale preview can never authorise an insert (same
generation rule as A0). Insert is implemented by the adapter as a value set on the specific element — never keyboard
or mouse synthesis — and never triggers submit.

## 5. Storage, retention, deletion (needs owner approval)

- Store: per-user directory under the client root (`control/assist/workflows/<uuid>.json`), never in Core memory,
  never synced. Content: structure and rules only (no captured values, no page text, no screenshots).
- Retention: until deleted; a "Delete all workflows" control; disabling keeps the file but stops matching.
- Audit: content-free events (created, edited, matched, applied, deleted).

## 6. Tests the A1 implementation must ship with

Mapping inference fixtures (positive, ambiguous, contradictory), stop-point detection, no value persistence (scan the
store for every value typed in the demo), Insert grant refusal matrix (stale generation, changed field, extra row,
sensitive field, expired, reused), never-submit (spy on form submission in Chromium), revoke-during-teach discards the
session, workflow matching refuses other origins.
