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
  unchanged. The edited file is pinned by git blob id in `tests/test_m39_boundaries.py`;
  `tests/test_m39_frozen_guard_allowlist.py` proves the guard still fails for a changed
  frozen file, a new file in frozen or live-app scope, and M39 look-alike paths, and that
  `uri_v1/office` does no direct file I/O.

  Tightened the same day after the recheck of `ba0db5e` (LOW items): the three
  single-file entries (`tests/m39_office_support.py` and the two scripts) are now exact
  matches (`M39_ALLOWED_FILES`), so a longer name such as `scripts/m39_office_benchmark.pyx`
  is rejected, and the guard probes run on a disposable clone instead of editing frozen
  files in the working checkout.

## 7. M37-L3: frozen guard gap, reopened and fixed (additive)

- **Raised.** The independent audit of M39 at `736464a` (finding F2) found that the
  pre-freeze prefixes `uri_v1/edge/` and `uri_v1/execution/` in
  `tests/test_m37_edge_resolution.py::test_m36_and_frozen_files_unchanged` date from M37,
  when those were M37's working directories. The guard diffs against the M36 baseline
  `179fe10`, so any edit, addition or deletion under them passed it, and the guard alone
  could not prove the frozen line intact. The same held for the other M37/M38 entries
  (`tests/test_m37_*`, `tests/test_m38_*`, the two support modules, `scripts/m37_*`,
  `scripts/m38_*`, `fixtures/m37_edge/`, `fixtures/m38_harness/`). The M39 line recorded
  it as retained limitation M37-L3 with the User's acceptance pending.
- **Decision.** Chetan (User), 2026-09-29 13:57 UTC, chose **"Fix in M37"** over accepting
  the limitation: M37 is reopened for a narrow authorized edit to its frozen check, followed
  by a re-audit.
- **Fix (test-only; no code under `uri_v1/` changed; frozen code is still the tree of
  `bd7c450`).** The guard keeps its M36-baseline check unchanged and now also diffs every
  path under those M37/M38 entries against the freeze commit `5bbf738` (`--no-renames`,
  so a rename reports both names), plus untracked files. Any difference fails. The only
  exemptions are the guard file itself and its new pin,
  `tests/test_m37_frozen_guard_pin.py`, which holds the guard file to its authorized
  content by SHA-256 (line endings normalized, so a Windows CRLF checkout hashes the
  same). The guard's offender list is now built by `frozen_scope_offenders()`, and the
  pin's tamper probes run it on a disposable clone, checking exactly what each tampering
  adds: a changed file under each kind of entry, new files (including
  `uri_v1/execution/planning/`), a deletion and a committed rename are all reported, and
  the guard test itself raises. With the pre-fix guard, all 17 of these tamperings passed
  it silently. No allowlist entry was added for any lane.
- **Effect on other lines.** Any branch that adds or changes files under these frozen paths
  now fails this guard. The dynamic-planning slice puts its code under
  `uri_v1/execution/planning/`, which the pre-fix guard let through; with the fix those
  files join its already-accepted guard failure (still one failing test, nine more
  offender paths). The M39 line must update its hash pin of this file when it merges the fix.
- **Status.** M37 is `REOPENED_FOR_AUTHORIZED_EDIT`, pending an independent re-audit of the
  fix, and returns to `CLOSED_FROZEN` only after it; this record does not re-freeze it.
  M37-L3 is closed by the fix, subject to that re-audit.
- **Re-freeze (2026-10-01).** Independent re-audit of `9395677`: **ACCEPT**, no CRITICAL,
  HIGH or MEDIUM findings (`docs/reviews/M37_L3_REAUDIT_9395677.md`, commit `98d8b1b`).
  Chetan (User), 2026-10-01 12:36 UTC, verbatim: "Re-freeze M37 at 9395677." Before this commit the
  conditions were re-checked on `98d8b1b`: no change under `uri_v1/`, `uri_core/`,
  `uri_ui/`, `scripts/` or `fixtures/` since `5bbf738` (only the guard test and its pin
  differ under `tests/`); `tests/` 1,325 passed / 0 failed; M36, M37 and M38 qualification
  drivers exit 0 with gates passing; governance 37 passed, `URI_STATE.yaml` VALID; anchors
  ok, changed `[]`. **M37 is `CLOSED_FROZEN` at `9395677d8fce63ffb5d45722ac871bb5a21b6135`**, frozen code still the
  tree of `bd7c450`. M37-L3 is closed.
- **Retained limitation M37-L4 (re-audit F-1 to F-3, LOW).** The guard is git-based, so
  deliberate local action can blind it: `--skip-worktree`/`--assume-unchanged` flags,
  `git replace` of the baseline commits, `.git/info/exclude`; ignored paths (`cache/`,
  `__pycache__`) and stale bytecode; and editing the guard, its pin, `.gitignore` or root
  pytest config (`pytest.ini`, `pyproject.toml`, `conftest.py`) together with frozen
  files. None of these travels on a branch unseen. Review rule: the guard proves the frozen
  paths only while those files are unchanged from `9395677`, so reviewers check
  `git diff 9395677 -- tests/test_m37_edge_resolution.py tests/test_m37_frozen_guard_pin.py
  .gitignore pytest.ini pyproject.toml conftest.py`. Accepted by the User, 2026-10-01
  12:39 UTC, verbatim: "I accept the independent re-audit verdict and authorize retaining findings F-1, F-2 and F-3 as documented limitations."
- **Windows validation: pending, not a freeze precondition.** No repository governance
  rule requires a Windows run before a freeze (checked: `docs/governance/`,
  `URI_STATE.yaml`, `AGENTS.md`, `CLAUDE.md`), so this is a normal re-freeze. This
  re-freeze is test-only and was validated on Linux, including an `autocrlf=true`
  checkout in the re-audit. The Windows / Python 3.13 run of `tests/` at this line stays a
  required follow-up and is carried into the combined M37/M39 Windows run on the User's
  PC. A failure there that is not already known (re-audit F-6: the M33.3 raw-byte anchors
  fail in an `autocrlf=true` checkout, identically on `5bbf738`) reopens M37.

