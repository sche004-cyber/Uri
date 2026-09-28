# Independent audit — provisional M36 / M37 / M38 batch

Date: 2026-09-28  
Status: **AUDITED WITH REPAIRS; PROVISIONAL / NOT FROZEN**

## 1. Audit identity and lineage reconciliation

- Repository/worktree: `C:\Users\cheta\.codex\worktrees\batch-audit-canonical\_V1`
- Branch: `codex/m36-m38-canonical-audit`
- Reconciled candidate audited before fresh repairs: `833d6ed8b47b797369f775a0bfc01c1c61a09833`
- Repair commit: `379769f` (`fix: harden provisional M36-M38 batch on Windows`)
- Platform: Windows 11, Python 3.13.15.

The audit package's advertised terminal lineage (`405db1f` → `5460d64` →
`3501f85` → `610c8f8`) was no longer canonical. Later work had diverged into:

- M36: `410d1b8` → `c179e42` → `d76dd83` → `80b7359`, plus the distinct
  contraction/verifier repair `a87e158`;
- M37: `763d8e7` → `7e0589b`;
- M38: `b013dba` → `1eec25e`;
- combined M37/M38: `3cd3557`.

No existing branch contained every later repair. I therefore made an additive,
non-destructive reconciliation: `3cd3557` + `a87e158` → `c01957f`, then merged
`80b7359`, resolving only the two overlapping M36 memory files by preserving the
semantic union. That produced `833d6ed`. The original package remains useful as
the audit-scope definition, but its SHA table and dependency statements do not
match the implementation lineage audited here. M37 and M38 are now tested against
the current reconciled M36 semantics rather than `405db1f` alone.

## 2. Verdicts

| Milestone | Audit verdict after repairs | Ready for freeze decision? |
|---|---|---|
| M36 | **ACCEPT_WITH_DOCUMENTED_LIMITATIONS** | **Yes**, as a provisional candidate; no freeze performed. |
| M37 | **ACCEPT_WITH_DOCUMENTED_LIMITATIONS** | **Yes**, as a provisional candidate; no freeze performed. |
| M38 | **ACCEPT_WITH_DOCUMENTED_LIMITATIONS** for offline/Windows qualification | **No**. A fresh subscription-backed live harness qualification on the repaired SHA is still required. |

## 3. Material findings and repairs

### M36

The merged implementation passed the authored coverage for negation/exclusion,
informal negatives, contractions, task-status negation, `complete`/`done`, FAILED
verifier evidence preservation across forget operations, registry mismatch
fail-closed behavior, hidden-task ordering, and frozen import boundaries.

Fresh probing found that several apostrophe-like Unicode glyphs (`ʻ`, `‛`, `′`,
`‵`, `❛`, `❜`) were not normalized. A phrase such as `donʻt allow network` could
therefore miss the shared negation detector used by M38 elevation approval. The
normalizer was extended at `uri_v1/memory/contracts.py:234`; six permanent probes
were added at `tests/test_m36_m38_independent_adversarial.py:18`.

### M37

Authored tests confirmed fail-closed routing, false-success prevention, escalation,
capability/registry boundaries, approval negation, file/task scoping, claim-first
recording, and verifier recomputation.

Fresh probes found that scripts using an unrecognized workbook reader (`read_csv`),
fabricating output without reading input, or passing `Path(...)` to an otherwise
recognized reader could be diagnosed as compatible and enter local execution.
Weak output-only acceptance criteria could then certify fabricated data. Static
inspection now emits `WORKBOOK_ACCESS_UNPROVEN` and escalates before any local
attempt (`uri_v1/edge/scriptinfo.py:305`). Three regression probes are at
`tests/test_m36_m38_independent_adversarial.py:30`.

### M38

Authored tests confirmed workspace containment, original-file protection,
false-output rejection, post-verification mutation checks, timeout/inactivity
cleanup, capability discovery/redaction, per-run grants, approval/elevation
negation, Windows path handling, restrictive argv construction, and the absence
of direct Python/shell execution in the default external-harness posture.

Fresh Windows execution found four issues:

1. Process-tree cleanup and liveness qualification relied on POSIX process-group
   and `/proc` semantics. Windows now uses a kill-on-close Job Object
   (`uri_v1/execution/verify.py:37`) for both verifier and harness processes, with
   fail-closed attachment and a cross-platform liveness probe.
2. Per-run `mcp.json` privacy was asserted with POSIX `0600` mode bits, which do
   not test Windows access control. Windows creation now removes inherited ACLs
   and grants only the current principal read/write (`uri_v1/execution/harness/adapters.py:34`);
   the Windows test checks `icacls` rather than POSIX metadata.
3. Extra-directory grants mishandled Windows path normalization and root forms.
   Matching now accepts the user's literal or resolved path while rejecting both
   slash roots and filesystem roots (`uri_v1/execution/harness/contracts.py:81`).
4. Explicit cancellation was classified as `stopped`; the frozen requirement is
   `outcome_unknown`. Both adapters now use `outcome_unknown`, cancellation is
   recorded in metrics (`uri_v1/execution/harness/runner.py:93`), and the fresh
   probe proves the child tree dies (`tests/test_m36_m38_independent_adversarial.py:40`).

The older detached-child regression was made platform-semantic: on Windows it now
asserts that Job Object containment prevents the mutation; on POSIX it retains the
documented session-escape/write-back-refusal assertion. This tests the intended
security property instead of treating POSIX session metadata as portable.

## 4. Reproduced evidence

- M36 qualification: 189 reference cases per run × 2; zero wrong confirmations,
  zero invented IDs, deterministic; verifier outcome `VERIFIED`; real `.docx`,
  `.md`, `.pdf`, `.py`, `.xlsx` flow exercised.
- M37 qualification: gate passed; decision accuracy 1.0; zero false local success,
  zero unsafe local execution on ambiguous/dynamic cases, zero original changes,
  zero claim-order violations, zero determinism mismatches.
- M38 qualification: gate passed; scenario accuracy 1.0; zero false verification,
  zero undetected original changes, zero surviving processes, zero bypass flags,
  zero secrets in records, zero session IDs in memory, zero determinism mismatches.
- Combined focused M36/M37/M38 suite: **391 passed, 2 stale scope guards failed**.
  The failures compare the combined successor tree to `291c9da` (M36-only allowlist)
  and `405db1f` (M37-only allowlist). They identify expected successor milestone and
  later M36 repair paths, not functional regressions.
- Full `tests/` suite: **1,017 passed, 2 stale scope guards failed, 130 subtests
  passed**.
- Broad root suite: **2,645 passed, 66 skipped, 9 failed, 88 subtests passed**.
  The exact nine failing node IDs were rerun in a clean `405db1f` worktree and all
  nine failed there as well. They are a strict subset of the package's recorded
  15-failure baseline; there are zero new broad-suite failures.
- Frozen M33.3 anchors: `ok=True`, changed `[]`, 8 S4 anchors, 24 frozen LF
  anchors, RAR SHA-256 `4db775666868e09a9f7232707d67ec3b4070970a30145ad3c5b41bb86b5e1b95`.
  Direct diff inspection found no change under the frozen turn/reference/
  evaluation/results anchors, `uri_core`, or `uri_ui`.

## 5. Remaining limitations and next action

- The available session was not running the requested GPT-6 Sol / Medium model;
  the audit proceeded without silently claiming that configuration.
- Claude Code 2.1.281 and Codex CLI 0.158.0 are installed and discoverable, but the
  prior live pilot was not treated as final qualification and was not rerun. A
  real, subscription-backed Windows run has external model behavior and spend and
  is the remaining M38 acceptance evidence. It must exercise the repaired SHA,
  restrictive default posture, real file-tool scoping, Job Object cleanup, URI
  verifier recomputation, original protection, and record redaction. The existing
  two-arm pilot remains explicitly `PILOT_NOT_QUALIFICATION` and is insufficient
  by itself.
- The verifier executes task scripts without a general OS sandbox; containment,
  copy isolation, Job Objects, re-diffing, and write-back fingerprint checks reduce
  risk but do not turn arbitrary Python into a sandbox. This is a documented
  architectural limitation, not silently reclassified as solved.

Recommended next action: independently run a fresh Windows/subscription-backed M38
qualification against the pushed repair branch, record the exact CLI versions and
candidate SHA, then present M36/M37/M38 to the release authority for a freeze
decision. Do not freeze any milestone from this report alone.
