# Milestone Manager — architecture

Date: 2026-10-21. Inputs: `MILESTONE_MANAGER_DISCOVERY.md`, `ACCEPTANCE_CRITERIA.md`.

## 1. Role in one paragraph

Milestone Manager (MM) is URI's development-time project registry. It owns **project-level** state: the roadmap,
milestones, milestone dependencies and blockers, decisions, milestone acceptance/integration evidence references,
review verdict records on milestones, owner approval records, milestone assignment and milestone handoff notes. It
does **not** run work and does **not** own task state.

Coordination correction (2026-10-21, after a message from the parallel Lifecycle V3.1 session `v1-2e`, branch
`milestone/lifecycle-v3-1-task-intelligence-20261021`): the first draft of this design also kept tasks, task claim
leases, task checkpoints and task evidence. Lifecycle V3.1 owns exactly those (task ids `TASK-...`, task context and
evidence, execution transitions, review/acceptance gates, checkpoints, leases, recovery). Keeping both would create
two sources of truth, so MM now reads tasks only through the V3.1 read contract `uri-dev/task-ledger-contract/1`
(`python -m scripts.dev_workflow.task_ledger summary --milestone <ref> --json`) and never writes task state. V3.1
stores the MM milestone id as an opaque `milestone_ref`. Lifecycle V3 keeps owning execution of one milestone run (stages,
reviewer launch, gates, integration push). MM links to lifecycle runs and records read-only, hash-verified snapshots
of them. Mission Control (future) reads MM; Skill Command Center (future) owns skill qualification and only links
its records to MM tasks.

## 2. Persistence alternatives compared

| Criterion | **A. Hash-chained JSONL event log in a git-trackable folder** (recommended) | B. SQLite (WAL, `synchronous=FULL`) with append-only event table (scheduler pattern) | C. Keep Markdown registers only | D. Write into scheduler / OI TaskLedger |
|---|---|---|---|---|
| Durability after power loss | fsync per append; torn tail detected and quarantined | very good (SQLite journal) | depends on editor; no detection | good |
| History / never overwrite | inherent (append-only file, chain) | needs triggers (as scheduler does) | manual discipline | partial |
| Tamper evidence | per-segment chain + git history when committed | chain in table; binary file not diffable | none | scheduler yes, OI no |
| Concurrency on one PC | OS file lock (msvcrt/fcntl) released on process death; optimistic version checks | `BEGIN IMMEDIATE` | none | engine lock = one process |
| Multi-machine / cloud sessions | one segment per host; segments never conflict textually in a git merge (host id and anchors are untracked, per machine); semantic conflicts detected by versions and duplicate ids | binary DB cannot be merged; needs export/import | text merges conflict | no |
| Review by humans and agents | readable JSON lines, diffable in git | needs a tool | readable | needs a tool |
| Query speed at 10k events | full verified fold 0.3 s measured (no cache) | fastest | n/a | fast |
| Dependencies | stdlib | stdlib | none | runtime package import |
| Code size | ~1 small store module | similar | none | coupling cost |
| Domain fit | development records | development records | yes | **no**: runtime product state (MM-F9) |

Decision: **A**. In plain words: an append-only diary of small JSON lines is easy to keep in git, easy to read, and
cannot silently lose old entries; the folder lock and fsync give the safety SQLite would give, at our tiny volume.
SQLite (B) stays a fallback: if event volume ever makes the fold slow, a projection index can be added, but it must
be bound to verified segment heads and must never be trusted by a guard (review R1-02). C fails continuity and integrity needs. D crosses the runtime /
development boundary.

## 3. Components

```
scripts/dev_workflow/milestones/
  store.py      EventStore: segments, OS lock, fsync append, torn-tail detection, chain verify, recover, git autocommit
  model.py      constants, validation, secret refusal, reducer (event -> projection), guards
  service.py    Manager: one method per command; validates against the projection *inside* the lock, then appends
  views.py      indicators, status board, ready list, resume brief, JSON export (schema uri-mm-status/1)
  importers.py  decisions.md, developmental.md, Lifecycle V3 state dirs (read-only)
  cli.py        `python -m scripts.dev_workflow.milestones <command>`
```

Ledger home (data, not code): a directory chosen by `--home` or `URI_MM_HOME`:

```
<home>/mm.json                 config: schema, host id, autocommit flag
<home>/events/<host>.jsonl     authoritative, append-only, hash-chained segment (one per host)
<home>/local/host.json         this machine's host id (untracked; a clone runs `init-host --host-id <new>`)
<home>/local/anchors.json      this machine's per-segment high-water marks; detects deletion of the newest events
<home>/.gitignore              ignores local/ and .lock
<home>/quarantine/             torn tails moved here by `recover`
<home>/.lock                   OS lock file (contents irrelevant)
```

Recommended deployment: `<home>` is a dedicated git worktree (for example orphan branch `ledger/milestones`), so every
append can be committed locally (`autocommit: true`) and pushed for off-machine durability only with owner approval.
Promotion of a ledger to authoritative is an owner decision (see implementation plan, phase 5).

## 4. State model

- **Events** are the only truth. Each event: `{v, seg, seq, ts, actor, session, kind, data, base, prev, hash}`;
  `hash = sha256(canonical JSON of all other fields)`; `prev` = previous hash in the same segment (genesis 64 zeros).
- **Projection** = deterministic fold of all events ordered by `(ts, seg, seq)`. Entities carry a `version` that
  increments on every event touching them.
- **Status indicators are derived**, never stored: RED (open blocker, unresolved conflict, lifecycle BLOCKED/WAITING)
  > YELLOW (open owner approval request, lifecycle BLOCKED OWNER_AUTHORIZATION) > GREEN (INTEGRATED, DONE) > WHITE
  (PLANNED, PAUSED, CANCELLED, SUPERSEDED) > BLUE (IN_PROGRESS, ACCEPTED). Same legend as `developmental.md`.

## 5. Integrity rules enforced in code (positive-claim guards)

| Claim | Required evidence (checked when the status is set) |
|---|---|
| milestone `ACCEPTED` | a review on that milestone, verdict ACCEPT or ACCEPT WITH FINDINGS, `blocking_open = 0`, commit equal to the milestone's `candidate_commit`, reviewer identity different from every implementer actor recorded on the milestone, result class `COMPLETED_WITH_RESULT`, and **no** completed negative review on that commit (a repair is a new commit) |
| milestone `INTEGRATED` | the ACCEPTED evidence again, an APPROVED owner approval of kind INTEGRATION **bound to the current candidate commit**, and an integration record for that candidate whose target contains it |
| milestone `DONE` | no approval request open, no blocker open, and status already ACCEPTED or INTEGRATED |
| approval `APPROVED`/`DENIED` | the owner's own words and a source reference; assurance `OWNER_RELAYED` (the recording agent is named) |
| decision text | never edited; `supersede` and `correct` add events and links both ways |

PENDING, RUNNING, FAILED, KILLED, TIMED_OUT, CANCELLED, NO_OUTPUT and BLOCKED result classes are stored but never
satisfy a guard (CLAUDE.md Evidence Integrity Rules).

## 6. Concurrency and multi-agent coordination

| Concern | Mechanism |
|---|---|
| Two processes write at once | exclusive OS lock on `<home>/.lock` around read-projection + validate + append; the OS releases it if the process dies (no stale lock files) |
| Lost update | `--expect-version N`: refused with CONFLICT when the entity moved |
| Milestone ownership (prevents duplicate milestone work, DEC-073) | `assign` writes a lease (agent, session, worktree, expiry); another actor is refused until release or expiry; takeover after expiry is recorded with `takeover_of`. Task-level leases belong to Lifecycle V3.1 |
| Two machines edit the same entity offline | each writes its own segment; after a git merge the fold sees two events built on the same base version and records a **conflict** (RED) until `resolve` |
| Review independence | review records name reviewer kind and id; the ACCEPTED guard refuses a reviewer that is also an implementer actor of the subject. Lifecycle V3 remains the place where independence is *verified* for driver reviews; MM records the class (`DRIVER_VERIFIED`, `SUBAGENT`, `SESSION`, `OWNER_ATTESTED`, `UNVERIFIED`) |
| Parallel worktrees | milestone records carry worktree and branch; `ready` lists milestones whose dependencies are met and that have no open blocker, approval request or live assignment by another actor |
| Handoff | `handoff` records done / next / files / commit at milestone level; `resume` prints the brief for the next agent and includes the V3.1 task summaries when that tool is present |

## 7. Session continuity

A new session runs `python -m scripts.dev_workflow.milestones resume <MILESTONE> --home <home>` and gets a bounded
brief (default 6,000 characters) answering:

1. What was requested? (objective, acceptance criteria reference)
2. What has been completed? (milestone status, V3.1 tasks ACCEPTED/INTEGRATED, evidence ids)
3. What evidence exists? (id, kind, result class, path, SHA-256)
4. What was rejected and why? (REJECT/REVISE reviews, superseded decisions, rejected alternatives)
5. What remains unfinished? (open V3.1 tasks, open blockers, unmet dependencies)
6. What is safe to do next? (next action, ready milestones, V3.1 task next actions)
7. What requires owner approval? (open approval requests)

plus the last handoff note and the linked lifecycle run stage. Recovery scenarios:

| Event | What happens |
|---|---|
| Context or quota exhaustion | nothing is lost: every recorded step is already fsynced; the next session runs `resume` |
| Session killed mid-command | lock released by OS; either the event was fully written (fsynced line) or not at all, or a torn tail exists. If it died after the append but before the anchor refresh on a host's very first write (including the HOST_REGISTERED write of `init-host`), the next write anchors the segment and records ANCHORS_ADOPTED (one ANCHOR_LOSS conflict to review and resolve) |
| Power loss mid-append | torn tail ignored by reads, reported by `verify`, quarantined by `recover`; earlier events intact; complete lines of the interrupted batch stay unapplied and are abandoned by the same `recover`. When the own segment has no anchor yet (a host's first command, or a failed first anchor refresh), `recover` always proceeds and records one ANCHOR_LOSS conflict for review: the bytes on disk cannot distinguish a power loss in progress from a cut of applied events (see §20) |
| Newest events deleted, a segment rewritten, or the anchors file lost | `local/anchors.json` (and git history) disagree or the file is missing; `verify` fails, writes are refused, status shows an integrity banner and exits 3 |
| Crash in the middle of a multi-event command | the command's events are one batch (one write + fsync); an incomplete batch is ignored by the fold and reported as a warning; the retry succeeds |
| Harness or agent replaced | identity is a recorded string; claims expire; the new agent claims after expiry or release |
| Worktree deleted | MM stores commits and paths; `verify-evidence` reports missing files and SHA mismatches |
| Partial implementation | the last checkpoint names files and commit; lifecycle link shows the run stage |

## 8. Integration boundaries (one owner per kind of state)

| Kind of state | Owner | MM role |
|---|---|---|
| Roadmap, milestones, milestone dependencies, next actions, blockers, assignment | **MM** | authoritative (after promotion) |
| Tasks, task context/evidence, task checkpoints and leases | **Lifecycle V3.1 task ledger** | reads `summary --json` (contract `uri-dev/task-ledger-contract/1`); never writes |
| Decisions (DEC-NNN) | **MM** (after promotion; `decisions.md` until then) | import, supersede, correct |
| Owner approvals | **MM** record of the owner's words; lifecycle `authorized` flag for the push itself | MM records; lifecycle enforces |
| Lifecycle run stage, rounds, gates, findings, integration push | **Lifecycle V3** | link + read-only snapshot (`sync-lifecycle`) |
| Review verdict on a run | Lifecycle V3 (driver) or imported review file | MM stores a reference + class |
| Lifecycle V3.1 (in development in parallel) | task execution | MM consumes its summary contract; V3.1 never writes MM state |
| Mission Control (P6) | visualises and coordinates | consumes `status --json` (schema `uri-mm-status/1`); writes only through MM commands |
| Skill Command Center (P7) | skill qualification records | links a qualification to an MM task by id; no duplicate task list |
| Session Launcher | starts sessions | passes milestone id; new session calls `resume` |
| Capability Registry (runtime Core) | product capabilities | untouched; MM may reference capability ids as text |
| Harnesses (Claude, Codex, subagents) | do the work | write through CLI with `--actor`; never edit segments by hand |
| URI runtime stores (scheduler, OI, supervisor, Core) | product | untouched |

## 9. User experience

- `status` prints one line per milestone/task: indicator emoji **and** a text word (accessible without colour),
  phase, issue, next action. Example: `🟡 OWNER ACTION | P0-MILESTONE-MANAGER | phase INTEGRATION | issue: approval
  AP-3 integration authorisation | next: owner decides AP-3`.
- Owner decisions come first in the output; routine reviews appear only as counts unless `--verbose`.
- `status --a2ui` maps indicators to `uri_a2ui` Badge tones (GREEN=success, BLUE=accent, YELLOW=warning,
  RED=danger, WHITE=neutral), so a later Mission Control can reuse the lifecycle surface pattern. No Flutter screen
  is required for MM to be useful (owner requirement H). Stage 8 UI qualification: MM is classified INTERNAL
  (development tooling, no user-facing URI capability).

## 10. Security and privacy

- Free text is refused if it matches secret patterns (API keys, tokens, private keys, `password=`-style pairs).
- Evidence is stored as path + SHA-256 + summary, never file contents.
- No network access, no model calls. Git push is never done by MM.

## 11. Resource expectations

Stdlib Python only; one process per command; no daemon. Measured: ~440-690 bytes per event; 10,000 events ≈ 4.4-6.9 MB (6.89 MB measured by reviewer R2/R3);
full fold ≈ sub-second; memory < 50 MB. Measured values are recorded in the implementation evidence (criterion N3).

## 12. Self-review (criteria R2, R3, R5)

- R2 met: four options compared on durability, history, tamper evidence, concurrency, multi-machine, readability,
  speed, dependencies, size, domain fit.
- R3 met: recommendation and plain-language reason in §2.
- R5 met: §8 gives one owner per kind of state.
- Gap found and repaired while drafting: the first draft let MM set a milestone INTEGRATED from a lifecycle snapshot
  alone. That would make MM re-decide a lifecycle outcome and bypass the owner record; §5 now requires the owner
  approval record as well.
- Remaining limitation (stated): tamper-evident, not tamper-proof; someone able to rewrite a whole segment can rebuild
  a consistent chain. Git commits of the ledger and the head hashes printed by `verify` are the anchor.

## 13. Changes after independent review R1 (2026-10-21, REJECT on `2ae7a79f`)

Recorded, not silently overwritten (details: `reviews/R1_2ae7a79f.md`, `reviews/R1_REPAIR.md`):

| Change | Reason |
|---|---|
| Projection cache removed; every read and write folds the verified log | R1-02 (forged cache satisfied a guard), R1-06 (tamper in another segment unseen), R1-08 (stale offsets) |
| Events after a segment's first chain error are not folded; status/show/resume/ready print an integrity banner and exit 3 | R1-04 |
| `anchors.json` high-water marks | R1-07 (deleting the newest events left a valid shorter chain) |
| Fold never replaces a record with the same id from another event; duplicates kept under `<id>@<seg>.<seq>` and flagged as DUPLICATE_ID conflicts; positive status refused while a conflict on the milestone is open | R1-05 |
| Fold flags a positive status whose basis names no real review/approval (BASIS_INVALID) | R1-02 defence in depth |
| ACCEPTED/INTEGRATED/DONE all re-run the independent-accept check on the current candidate (after R2: any negative review on that commit blocks); candidate locked while ACCEPTED/INTEGRATED/DONE; integration record must match the candidate; RED when any negative review on the candidate contradicts a positive status | R1-01, R1-03 |
| Multi-event commands are atomic batches | R1-15 |
| Identity comparison case/whitespace-insensitive | R1-14 |

## 14. Changes after independent review R2 (2026-10-21, REJECT on `4a54ebe1`)

| Change | Reason |
|---|---|
| Resolve, supersede and correct events carry the creation-event hash of their target; the fold binds by hash, so a duplicated id never redirects an answer to another milestone's record; DUPLICATE_ID conflicts name both subjects | R2-01 |
| Anchor refresh failure after a successful append is a warning; replace retries while a reader holds the file | R2-02 |
| Missing/unreadable anchors while events exist = integrity error; `reanchor --reason` records an explicit reset | R2-03 |
| Host id and anchors are local, untracked files (`local/`); a clone must `init-host` with a new id (refused if that segment exists) | R2-04 |
| `resolve-conflict` names the exact conflicts it saw | R2-05 |
| Timestamps never go backwards within a segment; the merge preserves each segment's order; acceptance no longer depends on cross-host clock order (any negative review on the candidate blocks) | R2-06 |
| Ledger-native decisions use `LDEC-NNN` until promotion; an imported row whose id belongs to a non-imported decision is reported as a collision, never as a revision | R2-07 |
| INTEGRATION approvals are bound to the candidate commit | R2-08 |
| A row whose own status is partial/unclear never records a full supersession | R2-09 |
| `log` reports integrity (exit 3); numbers and state words are not secrets; `recover` acknowledges incomplete batches (BATCH_ABANDONED) | R2-12..R2-14 |

Second-host procedure: clone the ledger repository, then `python -m scripts.dev_workflow.milestones --home <clone>
init-host --host-id <unique-id>`; never copy another machine's `local/` folder.

## 15. Changes after independent review R3 (2026-10-21, REJECT on `5bce5bdf`)

| Change | Reason |
|---|---|
| `reanchor` refuses to hide a detected loss (shorter/different segment, or unknown history) unless `--acknowledge-loss`; the recorded loss becomes an open ANCHOR_LOSS conflict: RED on every milestone and blocks positive statuses until `resolve-conflict LEDGER`; an anchors file without this machine's own non-empty segment is an integrity error | R3-01 |
| Decision supersession links bind by creation hash, or to the record created in the same batch (`"BATCH"`); both link lists store the actual (possibly duplicate) keys; UNBOUND_REFERENCE for decision links/corrections; importer links carry targets | R3-02 |
| Import source identity is the register name (`decisions.md`), not the checkout path | R3-03 |
| Lamport floor: a write is stamped no earlier than the newest event the writer has seen; a clock found behind is reported as a warning | R3-04 |
| Anchors are read before segments; transient Windows sharing violations are retried, not reported as missing | R3-05 |
| BATCH_ABANDONED applies by batch id whatever the order; `recover` reports only effective abandonments | R3-06 |
| Numeric exemption limited to small numbers for `token`/`secret`; numeric passwords/keys refused | R3-07 |
| Doc figures corrected; dead helper removed | R3-08 |

Residual (stated, not hidden): a removed anchors entry for *another* host's segment is not detectable from this
machine's anchors alone (that segment may simply not be anchored here yet); git history of the ledger is the anchor
for other hosts' segments.

## 16. Changes after independent review R4 (2026-10-21, REJECT on `c992b5ae`)

| Change | Reason |
|---|---|
| `reanchor` treats anything the anchors cannot vouch for (missing file, missing own entry, own count 0 with events, lost/rewritten events) as unknown history: refused without `--acknowledge-loss`, recorded as ANCHOR_LOSS when acknowledged | R4-01 |
| Lamport floor is strictly after the newest seen event (+1 µs), so an answer never ties with or sorts before what it answers, whatever the host names; segments stamped > 5 min ahead of this clock are named in warnings; the "clock behind" warning names the segment and both possibilities | R4-02 |
| `recover` abandons only this machine's own incomplete batches; an abandoned batch that later turns out complete is applied and flagged (ABANDONED_BATCH_COMPLETED, RED, `resolve-conflict LEDGER`) instead of being dropped | R4-03 |
| Import register identity = the document's first level-1 heading (or `--register`), not the file name or path | R4-04 |
| This machine's own anchor entry always exists (count 0 until first refresh); count 0 with events is a visible warning, not an error, so a failed first refresh does not block the next write | R4-05 |
| Open conflicts indexed once per projection (status no longer milestones × conflicts); `evidence/perf_n3.py` committed with its output | R4-06 |
| Docstring and handoff table corrected | R4-07 |

Residual (stated): a host whose own clock is ahead cannot detect that from its own clock; other hosts name its segment
in warnings. An own anchor entry at count 0 is shown as a warning and makes `reanchor` require acknowledgement; after
review R5 the next write records ANCHORS_ADOPTED, which opens ANCHOR_LOSS (see §17). The ledger is tamper-evident,
not tamper-proof.

## 17. Changes after independent review R5 (2026-10-21, REJECT on `7c8e0a29`)

| Change | Reason |
|---|---|
| `recover` computes anchor problems against the previous anchors and refuses (`LOSS_NOT_ACKNOWLEDGED`) unless `--acknowledge-loss`; acknowledged problems are recorded on STORE_RECOVERED and open ANCHOR_LOSS | R5-01 |
| `import-register` applies the register-identity collision rule (exit 1 `ID_COLLISION`) | R5-02 |
| record revisions keep `original` and each revision's `previous` values | R5-03 |
| a write that anchors an own segment with no anchor (count 0) first appends ANCHORS_ADOPTED in the same batch; the fold opens ANCHOR_LOSS (RED, blocks positive statuses until `resolve-conflict LEDGER`). Consequence, accepted: after a failed first anchor refresh the owner or an agent must review and resolve that conflict once | R5-04 |
| ANCHORS_RESET and STORE_RECOVERED use the Lamport floor | R5-05 |
| future-stamp warning names only the segment with the earliest future-stamped event and explains pinning | R5-06 |
| conflict index invalidated on every applied event | R5-07 |
| malformed anchor entries (non-integer/negative count, bad head) = unreadable anchors = integrity error (exit 3) | R5-08 |
| registers read as `utf-8-sig` (BOM tolerated) | R5-09 |

## 18. Changes after independent review R6 (2026-10-21, REJECT on `3ba9af68`)

| Change | Reason |
|---|---|
| `recover` does not count an own count-0 anchor as a problem when every own event beyond it belongs to this segment's incomplete batches (power loss in a host's first multi-event command) | R6-01 |
| `init-host` refuses when the ledger is a git work tree whose event segments differ from HEAD (`UNCOMMITTED_SEGMENTS`) and records HOST_REGISTERED with the adopted counts | R6-02 |
| acknowledged `recover` re-bases anchors explicitly (like `reanchor --acknowledge-loss`); the CLI prints the recovery result even when the follow-up batch abandonment fails | R6-03 |
| the count-0 warning and the adopting write both say that ANCHORS_ADOPTED / ANCHOR_LOSS follows | R6-04 |
| handoff references the rehearsal evidence file instead of quoting a count | R6-05 |

Residual (stated): outside git, a machine whose `local/` folder was deleted can register a new host id and adopt the
segments as they are; the HOST_REGISTERED event records the adopted counts, but a truncation that happened before
that is only detectable from the ledger's git history or another machine's anchors.

## 19. Changes after independent review R7 (2026-10-21, REJECT on `5b2a1427`)

| Change | Reason |
|---|---|
| `recover` on an unanchored own segment decides on the torn bytes: their canonical prefix must name the incomplete batch and its next index (`_torn_continues_batch`); too short ⇒ proceed but record ANCHOR_LOSS; contradicting ⇒ `LOSS_NOT_ACKNOWLEDGED` | R7-01 (the R6-01 repair let a truncated, already applied batch disappear without review) |
| warning text fixed | R7-02 |
| `init-host` removes its host file and anchors if the locked registration fails; a retry may continue a segment that holds only its own HOST_REGISTERED events | R7-03 |

## 20. Changes after independent review R8 (2026-10-22, REJECT on `ddc4e63b`)

The R6/R7 attempts to *prove* from the torn bytes that a tail was a harmless power loss were wrong in principle: a
genuine power-loss file and a byte-truncation of applied events are byte-identical (R8-02), and the prefix parsing
also refused legitimate cuts (R8-01). The rule is now uniform and simple:

| Situation in `recover` | Behaviour |
|---|---|
| anchors vouch for the segment (normal case) | quarantine the torn tail, abandon this host's incomplete batches, nothing to review |
| own segment has no anchor (count 0) | same, and record one ANCHOR_LOSS conflict (review, then `resolve-conflict LEDGER`); never refused |
| anchors show a loss or are missing/invalid | refused (`LOSS_NOT_ACKNOWLEDGED`) unless `--acknowledge-loss`, which records ANCHOR_LOSS |

`init-host` (R8-03..R8-05): any existing segment with the requested id is refused (`HOST_ID_TAKEN`, no retry
exception); if registration fails, the call removes exactly what it created (its new segment file, host file,
`.gitignore`/`local/` if new) and restores the previous anchors bytes, so a retry works inside and outside git and
cannot take over another machine's segment.

## 21. Changes after independent review R9 (2026-10-22, REJECT on `2fe3615f`)

| Change | Reason |
|---|---|
| `recover` treats "own anchor count 0" as unanchored whenever it runs (it only runs with a torn tail, so the segment always has bytes), also when the cut falls inside the first line and no complete event remains ⇒ always one ANCHOR_LOSS | R9-01 |
| `init-host` holds the ledger lock for its checks, writes and undo, so a concurrent registration of the same id on the same home is seen (`HOST_ID_TAKEN`) and never undone by the other call; earlier anchors that disagree with the segments are refused (`ANCHOR_MISMATCH`) | R9-02 |
| `init-host` writes the adopted anchors (with its own entry at count 0) before appending HOST_REGISTERED, so a kill between the append and the refresh leaves the documented count-0 state (warning, next write records ANCHORS_ADOPTED) instead of a missing anchors file | R9-03 |

## 22. Changes after independent review R10 (2026-10-22, REJECT on `1838e2df`)

| Change | Reason |
|---|---|
| `init-host` order: verify segments → compare earlier anchors → git check → write adopted anchors (own entry count 0) → write the host file (only now is the machine registered) → append HOST_REGISTERED → refresh. A kill before the host file leaves an unregistered home (`NO_HOST_ID`, not an integrity failure) that a retry registers; readers never see a registered host without anchors | R10-01 |
| `init-host --acknowledge-loss`: when this machine's earlier anchors disagree with the segments (or are unreadable), registration is refused with `ANCHOR_MISMATCH` naming this option; with it, HOST_REGISTERED records `anchor_problems` and the fold opens ANCHOR_LOSS | R10-02 (the earlier message pointed to `reanchor`, which cannot run without a host id) |

## 23. Changes after independent review R11 (2026-10-22, REJECT on `5bb005f6`)

| Change | Reason |
|---|---|
| `init-host --acknowledge-loss` first writes `local/pending_loss.json` (the problems) before replacing the earlier anchors; the marker is removed only after HOST_REGISTERED records them. An interrupted registration therefore keeps the loss: a retry sees the marker (needs the flag again and records it); a registered host's next write prepends LOSS_RECORDED (ANCHOR_LOSS); status warns while it is pending | R11-01 |
| `init-host` treats a missing `git` executable as "not a git work tree" | R11-02 |
| every locked writer re-reads `local/host.json` under the lock and refuses (`NO_HOST_ID`) when the registration changed or vanished while it waited | R11-03 |
| ANCHOR_LOSS status text names the recording event and its first recorded problem | R11-04 |
| an unreadable `local/host.json` counts as unregistered: `init-host` replaces it (anchors are still compared) | R11-05 |

## 24. Changes after independent review R12 (2026-10-22, REJECT on `61b01ac4`)

| Change | Reason |
|---|---|
| ledger-loss events a write has to record (LOSS_RECORDED for a pending acknowledged loss, ANCHORS_ADOPTED for an unanchored own segment) are appended as their own batch and folded *before* the command is validated, so the ANCHOR_LOSS they open blocks a positive status requested by that same command; they are recorded even when the command itself is then refused | R12-01 |
| the pending-loss marker carries an id; HOST_REGISTERED / LOSS_RECORDED record it (`pending_id`); a marker whose id is already recorded is removed and never recorded twice | R12-03 |
| marker removal retries Windows sharing violations and never fails a write that is already fsynced (warning instead) | R12-02 |

## 25. Changes after independent review R13 (2026-10-22, REJECT on `3da86259`)

The R12 design (record ledger-loss events and then run the command against the updated state) let one
`resolve-conflict` close a loss it had just recorded (R13-01), broke `recover`'s output (R13-02) and wrote events for
refused commands (R13-03). Replaced by one rule:

| Situation in any write | Behaviour |
|---|---|
| a pending acknowledged loss whose id is not yet recorded, or an own segment without anchor | record LOSS_RECORDED / ANCHORS_ADOPTED as their own batch (ANCHOR_LOSS), refresh anchors, remove the marker, then **refuse the command** with `LEDGER_LOSS_RECORDED` — it is not executed. The user reviews, resolves (`resolve-conflict LEDGER`) and runs it again |
| otherwise | the command runs as before |

So no command acts on a loss in the same call that records it. (Correction after review R14: this alone did not guarantee that a loss is *seen* before it is resolved — a write interrupted between recording and refusing told nobody; §26 adds the explicit proof.) The CLI prints the
warnings with the refusal. `recover` prints its own result and the refusal of its follow-up step; running `recover`
again completes it.

## 26. Changes after independent review R14 (2026-10-22, REJECT on `b59c1f2a`)

| Change | Reason |
|---|---|
| `resolve-conflict <entity> --id <conflict id> [--id ...] --note ...`: a conflict is resolved only when named by its id (first 12 hex digits of the event hash that raised it). Ids are shown by `status` (in each issue line) and by the new `conflicts` command. Without ids the command is refused (`NO_CONFLICT_ID`, listing the open ids); unknown ids are refused (`UNKNOWN_CONFLICT_ID`). Naming the id is the proof that the conflict was displayed, so a loss recorded by an interrupted write (Ctrl-C, kill during autocommit) cannot be closed by entity name alone | R14-01 |
| a refusal that follows a recorded loss also reports a git autocommit error | R14-02 |

Verified by reviewer R14 for the first time since R12: concurrency stress (5 rounds × 4 writer + 4 reader processes,
2,847 reads, 0 false integrity alarms) and N3 (rebuild 0.18 s, CLI status 0.43 s, 4.43 MB).

## 27. Changes after independent review R15 (2026-10-22, REJECT on `255b9079`)

| Change | Reason |
|---|---|
| a conflict id names the event that raised it; naming it resolves every open conflict that event raised on the entity (they are displayed under that one id). An id is refused only when it matches no event or more than one | R15-01 (HIGH regression of the R14 repair: a duplicate creation raises VERSION and DUPLICATE_ID with one id and became unresolvable) |
| refusal and warning texts give the exact `resolve-conflict LEDGER --id <id>` to run | R15-02 |
