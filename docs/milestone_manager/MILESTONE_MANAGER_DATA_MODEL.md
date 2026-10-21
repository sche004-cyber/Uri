# Milestone Manager — data model

Schemas as implemented in `scripts/dev_workflow/milestones/` (`model.py` is the vocabulary source; this document
must match it, and the tests in `tests/dev_workflow/test_milestones.py` check the behaviour).

## 1. Ledger files

| File | Schema id | Authoritative? |
|---|---|---|
| `<home>/mm.json` | `uri-mm-ledger/1`: `{schema, autocommit, created_at, dec_namespace}` (`LDEC` until promotion, then `DEC`) | yes (shared config, tracked) |
| `<home>/local/host.json` | `{host_id, registered_at}` | per machine, untracked |
| `<home>/events/<host_id>.jsonl` | one event per line (§2) | **yes — the only state truth** |
| `<home>/local/anchors.json` | `{<segment>: {count, head}}` high-water marks; never move backwards except by a recorded `ANCHORS_RESET` | per machine, untracked integrity anchor |
| `<home>/quarantine/<host>.<ts>.torn` | raw bytes of a torn tail | evidence only |
| `status --json` output | `uri-mm-status/1` (§6) | export contract for Mission Control |

## 2. Event envelope

```json
{"v": 1, "seg": "owner-pc", "seq": 42, "ts": "2026-10-21T16:22:14.112966Z",
 "actor": "claude:session-7930d870", "session": "7930d870-...", "kind": "MILESTONE_STATUS_SET",
 "data": {...}, "base": {"MILESTONE-MANAGER": 7}, "prev": "<64 hex>", "hash": "<64 hex>"}
```

| Field | Rule |
|---|---|
| `seg` | host id = segment file name; one writer host per segment |
| `seq` | 1, 2, 3 ... with no gaps inside a segment |
| `ts` | UTC, microseconds; global order is `(ts, seg, seq)` |
| `actor` | writer identity (required for every write; never a secret) |
| `base` | entity versions the writer validated against; a mismatch after a merge is recorded as a conflict |
| `prev` | previous event hash in the same segment; genesis `0`×64 |
| `batch` | optional `{id, n, i}` when one command wrote `n` events; the fold applies the batch only when complete |
| `hash` | `sha256` of the canonical JSON (`sort_keys`, `separators=(",", ":")`, UTF-8) of every field except `hash` |

## 3. Event kinds and their `data`

| Kind | Data fields | Notes |
|---|---|---|
| `MILESTONE_CREATED` | `id, title, objective, priority, phase, status, depends_on[], acceptance_ref, worktree, branch, base_commit, next_action, origin` | id `^[A-Z0-9][A-Z0-9._-]{1,63}$`, no priority inside the id |
| `MILESTONE_UPDATED` | `id, fields{title, objective, priority, phase, next_action, worktree, branch, base_commit, candidate_commit, acceptance_ref}` | status, dependencies and assignment have their own kinds |
| `MILESTONE_STATUS_SET` | `id, status, reason, basis` | `basis` = evidence ids that satisfied the guard (§5) |
| `DEPENDENCY_ADDED` / `DEPENDENCY_REMOVED` | `id, on[, reason]` | cycles refused |
| `MILESTONE_ASSIGNED` / `MILESTONE_RELEASED` | `id, agent, session, worktree, expires_at, takeover_of` / `id, reason` | lease ≤ 72 h |
| `IMPLEMENTER_RECORDED` | `id, agent` | adds an implementer identity (used by the independence guard) |
| `BLOCKER_ADDED` / `BLOCKER_RESOLVED` | `id BLK-n, subject, kind, reason, needs` / `id, resolution` | subject = milestone id or `PROJECT` |
| `EVIDENCE_ADDED` | `id EV-<16 hex>, subject, kind, ref, sha256, commit, result_class, summary` | id = hash of content ⇒ automatic deduplication; content never stored |
| `REVIEW_RECORDED` | `id RV-n, subject, commit, reviewer{kind,id}, assurance, verdict, blocking_open, findings_total, result_class, summary, evidence[]` | positive verdict with open blocking findings refused |
| `APPROVAL_REQUESTED` | `id AP-n, subject, kind, question, alias, origin` | `alias` keeps an imported id such as `OPEN-01` |
| `APPROVAL_RESOLVED` | `id, outcome, owner_words, source, reason, assurance` | APPROVED/DENIED need `owner_words` + `source`; assurance `OWNER_RELAYED`; the relaying actor is recorded |
| `DECISION_RECORDED` | `id DEC-NNN, title, decision, date, evidence_class, source, proposal, reasoning, alternatives_rejected, related[], consequences, approval_ref, imported[, source_status, imported_fields]` | never overwritten |
| `DECISION_SUPERSEDED` | `id, by, partial, note[, link_only]` | links both ways; `link_only` (imports) keeps the source's own status |
| `DECISION_CORRECTED` | `id, correction, evidence_class, source` | appended to `corrections[]` |
| `DECISION_SOURCE_REVISED` | `id, source, raw` | the Markdown row changed after import; original kept |
| `RECORD_IMPORTED` / `RECORD_SOURCE_REVISED` | `id REG-<section>-<first cell>, record_type, fields{}, color, source` | capability / roadmap / defect / next_action rows of `developmental.md` |
| `IMPORT_RECORDED` | `importer, source, commit, file_sha256, counts` | provenance of each import run |
| `HANDOFF_RECORDED` | `id HO-n, subject, summary, done, next, files[], commit` | milestone-level session handoff |
| `LIFECYCLE_LINKED` / `LIFECYCLE_SYNCED` | `subject, state_dir, config_path` / `subject, state_dir, snapshot` | snapshot fields in §7 |
| `INTEGRATION_RECORDED` | `subject, target_ref, target_commit, candidate_commit, contains_candidate, verified_by` | ancestry checked with git when a repository is given |
| `CONFLICT_RESOLVED` | `entity, note` | closes merge conflicts on that entity |
| `STORE_RECOVERED` | `segment, bytes, sha256, quarantine` | written by `recover` |

## 4. Vocabularies

| Name | Values |
|---|---|
| Milestone status | PLANNED, IN_PROGRESS, PAUSED, ACCEPTED, INTEGRATED, DONE, CANCELLED, SUPERSEDED |
| Phase | RESEARCH, DISCOVERY, ARCHITECTURE, IMPLEMENTATION, TESTING, REVIEW, REPAIR, ACCEPTANCE, INTEGRATION, CLOSED |
| Verdict | ACCEPT, ACCEPT WITH FINDINGS, REVISE, REJECT, BLOCKED |
| Assurance (review) | DRIVER_VERIFIED, SUBAGENT, SESSION, OWNER_ATTESTED, UNVERIFIED (does not qualify) |
| Reviewer kind | codex_cli, claude_cli, subagent, session, owner, lifecycle_driver, other |
| Result class | COMPLETED_WITH_RESULT (only positive), PENDING, RUNNING, FAILED, KILLED, TIMED_OUT, CANCELLED, NO_OUTPUT, BLOCKED |
| Evidence kind | test_run, gate, review_record, receipt, log, live_run, document, commit, other |
| Approval kind | INTEGRATION, POLICY, SCOPE, DECISION, PROTECTED_ACTION, OTHER |
| Decision evidence class | REPO-RECORD, MEMORY-ONLY, OWNER-PROMPT, ANTIGRAVITY-RECOMMENDATION, AGENT-RECORD, OTHER (same classes as `decisions.md`) |
| Decision status (derived) | ACTIVE, SUPERSEDED, PARTIALLY_SUPERSEDED, UNCLEAR, NOT_OWNER_DECISION |
| Blocker kind | TECHNICAL, REVIEWER_UNAVAILABLE, RESOURCE, DEPENDENCY, OWNER, INTEGRITY, OTHER |
| Indicator (derived) | GREEN COMPLETED, BLUE IN PROGRESS, YELLOW OWNER ACTION, RED BLOCKED, WHITE NOT ACTIVE |

## 5. Guards (positive claims)

See architecture §5. Implemented in `Manager.guard_status`; each refusal has a stable code: `NO_CANDIDATE`,
`NO_INDEPENDENT_ACCEPT`, `LATER_NEGATIVE_REVIEW`, `NO_OWNER_INTEGRATION_APPROVAL`, `NO_INTEGRATION_RECORD`,
`NOT_ACCEPTED`, `OPEN_ITEMS`. Other refusal codes: `CONFLICT`, `ASSIGNED`, `EXPIRED_ASSIGNMENT`, `CYCLE`, `SECRET`,
`EXISTS`, `NOT_FOUND`, `NO_ACTOR`, `TOO_LONG`, `BAD_VALUE`, `BAD_ID`, `BAD_SHA`; store errors `TORN_TAIL`,
`CHAIN_BROKEN`, `LOCK_TIMEOUT`, `CONCURRENT_WRITE`, `NOT_INITIALISED`.

## 6. Status export `uri-mm-status/1`

```json
{"schema": "uri-mm-status/1", "generated_at": "...",
 "ledger": {"events": 0, "conflicts_open": 0, "integrity_errors": []},
 "milestones": [{"id": "", "title": "", "priority": "P0", "phase": "", "status": "",
                 "indicator": {"color": "YELLOW", "word": "OWNER ACTION", "tone": "warning", "issue": "", "next_action": ""},
                 "depends_on": [], "ready": false, "open_approvals": [], "open_blockers": [], "assignment": null,
                 "worktree": null, "branch": null, "candidate_commit": null, "integration": null,
                 "lifecycle": [{"state_dir": "", "stage": "", "blocker_kind": ""}],
                 "tasks": {"available": false, "count": 0}}],
 "approvals_open": [{"id": "", "subject": "", "kind": "", "question": ""}],
 "decisions": {"ACTIVE": 0, "SUPERSEDED": 0}}
```

Consumers must ignore unknown fields; a breaking change bumps the schema id.

## 7. Lifecycle V3 snapshot (read-only)

`{milestone, stage, blocker{kind, reason, needs}, candidate, baseline, config_sha256, events, head, chain_ok,
errors[], latest_review{round, candidate, verdict, independent, outcome, provider, status}, integration{status,
target_ref, target_tip_after, candidate}, receipt_sha256, state_sha256}`. The chain check uses the driver's own
formula (`sha256(json.dumps({seq, ts, kind, data, prev}, sort_keys=True))`, `lifecycle.py:251`) and compares
`state.json` history with the log, as `lifecycle.verify` does; the test builds its fixture with the real
`lifecycle.State`.

## 8. Lifecycle V3.1 task summary (consumed, not owned)

Contract `uri-dev/task-ledger-contract/1` (owned by the V3.1 session, branch
`milestone/lifecycle-v3-1-task-intelligence-20261021`): array of `{task_id, milestone_ref, title, status, version,
updated_at, head_commit, last_verified_commit, accepted_commit, open_blocking_findings, paused, chain_head,
next_action, v3_runs}`. Exit 0 = verified data, 4 = `LEDGER_INTEGRITY_FAILED`, 3 = refused, 2 = error (agreed by
message 2026-10-21). MM passes its milestone id as `milestone_ref`.

## 9. Mapping from the P0 registers

| Source | Target |
|---|---|
| `decisions.md` §1 rows (13 columns) | `DECISION_RECORDED` with every column kept (`imported_fields`), `source{path, commit, line, file_sha256, row_sha256}`, `source_status` from the Applicability column |
| "superseded ... by DEC-x[/y/z]" in corrections or applicability | `DECISION_SUPERSEDED` with `link_only` |
| `decisions.md` §3 OPEN-01..OPEN-10 | `APPROVAL_REQUESTED` kind DECISION, subject PROJECT, `alias` = OPEN id |
| `developmental.md` §B, §C, §J, §K rows | `RECORD_IMPORTED` (capability, roadmap, defect, next_action) with colour word and raw fields |
| owner roadmap (prompt 2026-10-21) | `MILESTONE_CREATED` per milestone (priority field) — done in the migration rehearsal, not by an importer |

## 10. Conflicts (derived, after review R1)

`{type, entity, subject, event, kind, resolved[, expected, actual][, kept, duplicate][, missing]}` with `type`:
VERSION (an event was built on an older entity version, e.g. after a merge), DUPLICATE_ID (two events created the
same id; both records are kept, the later one under `<id>@<seg>.<seq>`; a duplicate MILESTONE_CREATED is kept in
`duplicates[]`), BASIS_INVALID (a positive status names reviews/approvals that do not support it). Additional refusal
codes: `CANDIDATE_LOCKED`, `CONFLICT_OPEN`; CLI errors `IO`, `INPUT` (exit 2); integrity failure exit 3.

## 11. Changes after review R2

- `APPROVAL_REQUESTED.commit` (required binding for kind INTEGRATION: the candidate at request time).
- `APPROVAL_RESOLVED.target`, `BLOCKER_RESOLVED.target`, `DECISION_SUPERSEDED.target/by_target`,
  `DECISION_CORRECTED.target`: creation-event hash of the referenced record (fold binds by it).
- `CONFLICT_RESOLVED.conflicts`: hashes of the conflict events the resolver saw; only those are resolved.
- New kinds: `ANCHORS_RESET {reason, previous, lost, unknown_previous, counts}` (after R3: a non-empty `lost` or `unknown_previous` creates an ANCHOR_LOSS conflict), `BATCH_ABANDONED {batches[], reason}`.
- New conflict type `UNBOUND_REFERENCE` (a resolve whose target record is absent).
- Decision ids: `DEC-NNN` (owner register numbering, import only until promotion) and `LDEC-NNN` (ledger-native).
- Refusal codes: `NEGATIVE_REVIEW` (replaces `LATER_NEGATIVE_REVIEW`), `DEC_NAMESPACE`; store errors `NO_HOST_ID`,
  `HOST_ID_TAKEN`, `ALREADY_REGISTERED`; CLI `import-decisions` exits 1 with `ID_COLLISION` when rows collide.

## 12. Changes after review R3

- Reference targets may be `"BATCH"`: the record with that id created by an earlier event of the same batch.
- `source.register` (file name of the register) identifies an import source independent of the checkout path.
- Conflict type `ANCHOR_LOSS` (entity `LEDGER`); refusal `LOSS_NOT_ACKNOWLEDGED` for `reanchor`.

## 13. Changes after review R4

- `source.register` = the register document's first level-1 heading (or an explicit `--register`).
- `ANCHORS_RESET.anchor_problems[]`: anchor errors/warnings the reset acknowledged (non-empty ⇒ ANCHOR_LOSS).
- Conflict type `ABANDONED_BATCH_COMPLETED` (entity `LEDGER`, field `batch`).
- `local/anchors.json` always holds this machine's own entry (`count` 0 until the first refresh).
- Event `ts` of a write is strictly later than every event the writer had verified (Lamport floor + 1 µs).

## 14. Changes after review R5

- `STORE_RECOVERED.anchor_problems[]` (non-empty ⇒ ANCHOR_LOSS); new kind `ANCHORS_ADOPTED {segment, count, head,
  warning}` (always ⇒ ANCHOR_LOSS).
- Records keep `original {fields, color, source}`; each revision holds `previous` and the new values.
- `import-register` reports `collisions` like `import-decisions`.

## 15. Changes after review R6

- New kind `HOST_REGISTERED {host, adopted{segment: count}}` (written by `init-host`; informational, folded into
  `hosts[]`). Store error `UNCOMMITTED_SEGMENTS`.

## 16. Changes after review R10

- `HOST_REGISTERED.anchor_problems[]` (present only with `init-host --acknowledge-loss`) ⇒ ANCHOR_LOSS.
- Store error `ANCHOR_MISMATCH` (init-host without acknowledgement).

## 17. Changes after review R11

- New kind `LOSS_RECORDED {anchor_problems[], origin}` (⇒ ANCHOR_LOSS), written by the first write after an
  interrupted acknowledged registration.
- Local file `local/pending_loss.json {anchor_problems[], host}` (untracked; exists only between an acknowledged
  registration and the event that records it).
