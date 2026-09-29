# M36 / M37 / M38 Freeze Record

**Status: `CLOSED_FROZEN` at `bd7c45068ed2f75cb68c9ea60f803e61a36dd7f2`** (branch
`claude/project-thread-2vamlf`, https://github.com/sche004-cyber/Uri).
Verdict for all three milestones: `ACCEPT_WITH_DOCUMENTED_LIMITATIONS`.

This file is the closure evidence for M36 (URI-Memory Minimum), M37 (Edge Minimum) and
M38 (Harness Execution Minimum). The commit that adds it contains governance and
documentation changes only; the frozen code is exactly the tree of `bd7c450`.

## 1. Authority

Chetan (User), 2026-09-29 03:24 UTC, verbatim:

> Yes — freeze M36, M37, and M38 at bd7c450. The final independent check is strong:
> 1,309 passed / 0 failed, all gates passed, 132 additional adversarial grant-wording
> probes were blocked, and there are no open findings. Treat 62d564c as superseded and do
> not preserve it as a competing qualification line.
> Accept the documented limitations and freeze now; do not make a live pilot a prerequisite
> for freezing. The remaining items are environmental/coverage limitations rather than
> unresolved defects in the qualified scope. Record them explicitly as retained
> limitations. A live harness pilot should be the next post-freeze validation activity,
> especially for M38, without reopening M36–M38 unless it exposes a defect that actually
> violates a frozen guarantee.

This record was written by the Claude session that owns the candidate line, because the
Codex bridge device was offline. It records the freeze. It does not re-audit the milestones.

## 2. Evidence

| Check | Where run | Result |
|---|---|---|
| Final independent check of `bd7c450` (Codex via the bridge thread, unsandboxed Windows) | Chetan's PC | 1,309 passed / 0 failed; all gates passed; 132 additional adversarial grant-wording probes blocked; no open findings (as relayed by the User and the coordinator; the full Codex transcript lives in the bridge thread and is not a repository artifact) |
| Previous Codex check of `21bcc63` | Chetan's PC | tests/ 1,289 passed / 0 failed / 3 skipped; three quals pass; anchors ok; governance 37; broad suite shows the same 15 legacy failures; M36 and M37 `ACCEPT_WITH_DOCUMENTED_LIMITATIONS` |
| `tests/` at `bd7c450` | Linux (cloud) | 1,303 passed, 0 failed, 9 skipped (Windows-only) |
| M36 / M37 / M38 qualification drivers at `bd7c450` | Linux | all exit 0; gates pass; `wrong_confirmed` 0; M37 routing verdicts unchanged across the final repair rounds (only latency fields move) |
| Frozen M33.3 anchors | Linux | `ok=True`, changed `[]`, RAR SHA-256 `4db775666868e09a9f7232707d67ec3b4070970a30145ad3c5b41bb86b5e1b95` |
| Governance suite | Linux | 37 passed |
| Broad root suite | Linux | 15 failed / 2,639 passed / 66 skipped; the failure set is identical to the pre-batch base `6420f3e` and to `70ecb59` (none in Memory/Edge/Execution) |

Per-SHA outputs are in the project audit folder,
`audits/m38_windows_repair/evidence/*_bd7c450.txt`, alongside
`audits/m38_windows_repair/CANDIDATE_4cd360f_EVIDENCE.md`.

## 3. Lineage

`80b7359` (M36 line) + `6420f3e` (M37/M38 round 3) → `4cd360f` (merge + Antigravity
`a87e158` reconciliation + M38 Windows repair) → `f9ac385` / `c7832b9` / `249660e` /
`ca3cf7b` (strict positive-allowlist grant grammar) → `7f82400` / `51bf5d0` (minimal
ports from the Codex line) → `f8115d5` → `179fe10` / `21bcc63` → **`bd7c450`**.

**`62d564c` (branch `codex/m36-m38-canonical-audit`) is SUPERSEDED.** It is not a
competing qualification line. Its two defects that Codex confirmed were ported minimally
and then extended:

- M36 apostrophe/NFKC/-n't negation, in `7f82400` and `179fe10`.
- M37 `WORKBOOK_ACCESS_UNPROVEN`, in `51bf5d0`.

Its M38 cancel classification was also ported in `51bf5d0`. We deliberately did not
take:

- its post-`Popen` Job Object assignment;
- its `icacls` secret-file path;
- its textual `extra_dir` matching.

The `bd7c450` versions are stronger in each case. `a87e158` (Antigravity) is reconciled
and superseded the same way.

## 4. Retained limitations (accepted by the User; not open defects)

### M36 — URI-Memory Minimum
- **M36-L1:** verifier receipts are bound to verifier id, type and version only (plan
  §17.6). A compromise of trusted verifier code is out of scope.

### M37 — Edge Minimum
- **M37-L1: the `qualification_run` switch.** `CapabilityRegistry(..., qualification_run=True)`
  (`uri_v1/edge/registry.py`) treats deterministic capabilities as QUALIFIED without a
  pinned qualification record. It is never the default and is recorded in every
  decision's findings. Only the qualification driver and the test support set it;
  `default_registry()` loads the SHA-pinned evidence record without it.
- **M37-L2: Windows NTFS alternate data streams are invisible to the workspace diff.** A
  write to `file:stream` in the isolated copy is not reported as a change. It never
  reaches an original: write-back copies each verified file with `shutil.copyfile`, which
  copies the main data stream only (`uri_v1/execution/workspace.py`).

### M38 — Harness Execution Minimum
- **M38-L1: no live harness run is part of the qualification.** Qualification uses the
  offline fake-harness gate. The spend policy allows only subscription-authenticated runs,
  and the earlier live Claude Code pilot is `PILOT_NOT_QUALIFICATION`.
- **M38-L2: descendants that leave containment are not contained.**
  - On POSIX, a `setsid`-detached descendant leaves the killed process group. The
    write-back fingerprint check still refuses its late changes.
  - On Windows, a process launched through a service (for example, via the Task
    Scheduler or a COM server) is outside the kill-on-close Job Object.
- **M38-L3: the owner-only DACL on secret files is untested across accounts.** The
  protected single-SID DACL is verified in-process for the current user. It has not been
  tested from a second Windows account.

### Shared
- **S-L1: no OS sandbox.** The verifier and harness code run with tool-setting
  restrictions, copy isolation, re-diffing and process-tree containment, not in an OS
  sandbox.
- **S-L2: strict grant grammar refuses some natural phrasings.** Examples are "yes, apply
  it", "I approve sheets", "allow network for now", "use the tools", NBSP forms, very long
  inputs and `\\?\` paths. This is intended under the User's strict-allowlist rule of
  2026-09-28 17:53.

## 5. Next step (post-freeze)

**Next validation activity: a live harness pilot, especially for M38.** It must run
through the User's subscription-authenticated Claude Code session on Windows, against
`bd7c450`, and record the exact CLI versions. It should exercise:

- the restrictive default posture;
- real file-tool scoping;
- Job Object cleanup;
- URI verifier recomputation;
- original protection;
- record redaction.

The pilot does not reopen M36–M38 by itself. A milestone reopens only if the pilot shows
a defect that actually violates a frozen guarantee. Environmental or coverage findings of
the kind listed in §4 are recorded as limitations.

No production integration, live-app wiring, INT-* event or next milestone is opened by this
record. M39 (Office demonstrator) proceeds under its own gates.

## 6. Authorized edits after the freeze (additive)

- **2026-09-29, frozen M37 test (User authorization, Chetan, 05:21 UTC).**
  `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` gains the
  minimum M39-specific allowlist entry (`M39_ALLOWED`: `uri_v1/office/`,
  `fixtures/m39_office/`, `tests/test_m39_`, `tests/m39_office_support.py`,
  `scripts/m39_office_benchmark.py`, `scripts/m39_generate_benchmark.py`) and now also
  rejects `..` path segments. No dynamic-planning paths were added (that lane keeps its
  SourceResolver/adapter approach). No M37 code changed, and the freeze verdict above is
  unchanged. The edited file is pinned by content hash in `tests/test_m39_boundaries.py`;
  `tests/test_m39_frozen_guard_allowlist.py` proves the guard still fails for a changed
  frozen file, a new file in frozen or live-app scope, and M39 look-alike paths, and that
  `uri_v1/office` does no direct file I/O.

  Tightened the same day after the recheck of `ba0db5e` (LOW items): the three
  single-file entries (`tests/m39_office_support.py` and the two scripts) are now exact
  matches (`M39_ALLOWED_FILES`), so a longer name such as `scripts/m39_office_benchmark.pyx`
  is rejected, and the guard probes run on a disposable clone instead of editing frozen
  files in the working checkout.

## 7. Retained limitation recorded after the freeze (additive)

- **2026-09-29, M37-L3: the frozen M37 scope guard cannot by itself prove the frozen
  line intact.** Recorded from the independent audit of M39 at `736464a` (finding F2,
  classified there as a frozen-line limitation, not an M39 defect). The pre-freeze
  prefixes `uri_v1/edge/` and `uri_v1/execution/` in
  `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` date from M37,
  when those were M37's working directories, so an edit under them passes that guard. The
  authorized M39 entry (section 6) did not widen them. No code change: the test is
  frozen and the User's authorization covers only the M39 entry. Frozen-line integrity is
  enforced instead by M39's guard
  `tests/test_m39_boundaries.py::test_m36_m37_m38_and_frozen_files_unchanged`, which
  diffs against the freeze commit `5bbf738` with no exemption since the M39 repair after
  that audit (its N1). The classification is the audit's; the User's acceptance of this
  limitation is not yet recorded.
