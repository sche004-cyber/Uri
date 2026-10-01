# Dynamic Planning Slice 1 Freeze Record

**Status: `CLOSED_FROZEN` at `565eae8be2e3896e1d8615ccf4e610e014b87a90`** (branch
`claude/dynamic-planning-slice1-2eemmh`, https://github.com/sche004-cyber/Uri).
Verdict: `ACCEPT_WITH_DOCUMENTED_LIMITATIONS`. Effect guard: **not approved; not implemented**.

This file is the closure evidence for dynamic planning slice 1: the two-workbook structure
comparison with four read-only actions plus a report writer, under `uri_v1/planning/`.
The commit that adds it contains governance and documentation changes only. The frozen code is
exactly the tree of `565eae8`: the audited `b6b2cb0` plus the package move to `uri_v1/planning/` that Chetan ordered before the freeze (report §12).

## 1. Authority

- **Freeze authorization, verbatim excerpt** (Chetan, 2026-10-01 12:22 UTC; his closing paragraph, which asks for the post-freeze next steps, is omitted here):

  > I confirm my acceptance of the audited Dynamic Planning slice at commit `b6b2cb0` for freezing, subject to the documented limitations.
  > Please proceed as follows:
  >
  > 1. Complete the pending Authority section of the freeze record using this explicit authorization.
  > 2. Preserve the recorded qualification results, regression results, and Python compatibility evidence.
  > 3. Document the accepted frozen-guard failure and the fact that Windows validation has not been performed.
  > 4. Apply the verified freeze patch without modifying the previously frozen components.
  > 5. Run the governance and frozen-anchor checks.
  > 6. Commit and push the freeze record and associated state updates.
  > 7. Report the final commit SHA, branch, governance result, and freeze status.
  >
  > Do not interpret this authorization as approval of the separate effect-guard card or any additional Dynamic Planning slices.
  > Do not introduce unrelated implementation changes.

- **Move before freezing, verbatim** (Chetan, 2026-10-01 12:23 UTC): "Move, then freeze:". It answers the coordinator's question whether to move the dynamic planning code out of the frozen M37 folders before freezing. The frozen commit is therefore `565eae8`, the audited `b6b2cb0` moved to `uri_v1/planning/` with no logic change (report §12).
- **Effect guard:** not approved; not implemented. Chetan's authorization above says it does not approve the separate effect-guard card.
- **Earlier decisions this freeze relies on:**
  - 2026-09-29 01:10: base on the frozen line, reuse the existing verifier, do not edit `verify.py`, no live wiring before the working-product baseline.
  - 2026-09-29 05:21: no dynamic-planning allowlist entry in the frozen M37 test; keep the SourceResolver adapter.
  - 2026-09-29 05:31: accept the frozen M37 guard failure on slice paths.
  - 2026-09-29 13:49: do not accept F2; bind qualification to adapter identity and an implementation SHA-256, and fail closed.
  - 2026-09-30 15:43: bounded R3-1 repair, then a focused re-check; no freeze until it accepts.
- **Who wrote this record:** the Claude session that implemented the slice. It records the
  freeze. It does not re-audit the slice.

## 2. Audit chain

| Round | Subject | Verdict | Report |
|---|---|---|---|
| Audit | `c5d47a0` (code `3bbf8f7`) | REPAIRS_REQUIRED | `b4eae6b` |
| Re-audit | `458cbda` | ACCEPT, except F2 (adapter swap), which went to Chetan | `1cab035` |
| Re-audit | `74474a2` (F2 attestation) | REPAIRS_REQUIRED (F2R-1..5) | `5eb0149` |
| Re-audit | `06a920b` | REPAIRS_REQUIRED (R3-1) | `d3d26de` |
| Focused re-check | `0c56215` / `28fcbf9`, extended to `b6b2cb0` | **ACCEPT** | `67681af` on `claude/project-thread-wjykgi` (`DYNAMIC_PLANNING_SLICE1_RECHECK_0c56215.md` and evidence) |
| Focused re-check of the move | `565eae8` | **ACCEPT** | `43101f8` on `claude/project-thread-wjykgi` |

All of these audits are independent Claude audits. Codex was paused for quota.

## 3. Evidence at `565eae8` (frozen head, after the move)

| Check | Where run | Result |
|---|---|---|
| `tests/` full suite | Linux, Python 3.11.15 | 1449 passed, 1 failed, 9 skipped. The only failure is the accepted `test_m36_and_frozen_files_unchanged` |
| Guard offenders (current guard, and the M37-L3 fixed guard `9395677` logic) | Linux | 27 under each, all slice paths (`uri_v1/planning/`, `tests/test_dynamic_planning_*`, `scripts/dynamic_planning_*`, `fixtures/dynamic_planning/`); none in `uri_v1/execution/` |
| Slice tests | Linux, Python 3.11 and Python 3.13 | 147 passed on each |
| Slice qualification | Linux, Python 3.11 | exit 0: 34/34; all six safety counters 0; C33 semantic miss 1/1; gate passed |
| Qualification record digest (re-pinned for the new module names) | Linux | `9998e2b238c2837d206e0505c77191d56391c7646ae37534f1da087c74fd2a26` |
| Review regression set / anchors / governance | Linux | 113 passed / `ok=True`, changed `[]` / 37 passed, validator VALID |
| M36, M37, M38 qualification | Linux | exit 0 each |
| Previously frozen files | Linux | `git diff --name-status --no-renames 5bbf738 565eae8` lists 38 additions and no modification or deletion; nothing under `uri_v1/execution/`, `uri_v1/edge/`, `uri_v1/memory/`, `uri_core/` or `uri_ui/` differs from the M36-M38 freeze |
| Windows | not run | **Windows validation has not been performed at this head.** |

## 3a. Evidence at `b6b2cb0` (audited head, before the move; kept as recorded)

| Check | Where run | Result |
|---|---|---|
| `tests/` full suite | Linux, Python 3.11.15 (implementation thread, and again in the re-check) | 1449 passed, 1 failed, 9 skipped. The only failure is the accepted `test_m36_and_frozen_files_unchanged`; all 18 offending paths are slice test, script or fixture paths |
| Slice tests (`tests/test_dynamic_planning_*.py`) | Linux, Python 3.11 and Python 3.13 | 147 passed on each |
| Slice qualification (`scripts/dynamic_planning_qualification.py`) | Linux, Python 3.13 at `b6b2cb0`; Python 3.11 at `28fcbf9` (same code) and in the re-check | exit 0: 34/34 expected outcomes; all six safety counters 0 (false VERIFIED 0/34, unauthorized effect 0/34, wrong source binding 0/16, undeclared execution 0/16, undetected original modification 0/34, unresolved reported complete 0/34); C33 semantic miss 1/1 (expected); gate passed |
| Battery / gate digests | Linux | `2c36641926db04e679fb937ce10d0fff141c7989e049618caf9759002fd0f419` / `f2dfc9371871eb994ff22f4e5a6d0802864980d9dab03e521a8dac04938c50ff`, unchanged since `44fa36e` |
| Qualification record digest (pinned in `actions.py`, superseded by the move) | Linux | `9975a268c1301e01ec87430d1c2d632088460f71c29bb8465ff166b0d5dd553b` |
| Review regression set | Linux | 113 passed |
| M33.3 anchors / governance | Linux | `ok=True`, changed `[]` / governance 37 passed, validator VALID |
| M36, M37, M38 qualification | Linux | exit 0 each |
| Frozen boundary | Linux | `git diff --name-status 5bbf738 b6b2cb0` is additions only; `verify.py` and every reused file match their base digests |
| Windows, Python 3.13.15 | Chetan's PC (readiness-audit session, temp worktree at `b6b2cb0`) | slice 147/147; qualification 34/34 with all six counters 0; C33 scored separately as the expected semantic miss (as relayed by the coordinator 2026-10-01 07:49; evidence `evidence\dp_qual_b6b2cb0_win_py313.json` in the readiness audit folder on Chetan's PC, not a repository artifact). Full suite not run on Windows. |

## 4. Retained limitations

- **DP-L1. Frozen M37 guard failure (accepted 2026-09-29 05:31).** `test_m36_and_frozen_files_unchanged` fails on the slice's own paths: 27 at `565eae8` (the 9 code files in `uri_v1/planning/` plus the test, script and fixture paths), none in frozen M36-M38 code. The M37-L3 guard fix does not change that count. No allowlist entry was added.
- **DP-L2. Attestation is not a containment or complete security boundary** (report §6.16). Attestation proves the adapter that runs is the qualified implementation. It does not stop:
  - the qualified adapter's own writes outside the workspace;
  - process-wide patching of builtins, standard-library modules or `sys.modules` (probes P5 and Q6);
  - C-level code;
  - editing a source file together with the record and re-pinning it (visible in git);
  - replacing `attestation.py`, the runner or the pinned constants in the process;
  - effects of tampered module state on non-adapter code during planning (P3);
  - any other in-process modification of URI's running code or state.

  All of these need an attacker who already controls the process, the same class as the frozen shared S-L1 "no OS sandbox".
- **DP-L3. Effect guard not approved; not implemented.** The in-process audit-hook guard prototyped in `docs/reviews/DYNAMIC_PLANNING_F2_TRUST_REVIEW.md` is not implemented. Containment of outside writes is left to a future decision, made once for the live app (guard or OS sandbox).
- **DP-L4. Self-qualification.** Capabilities are qualified by the implementer (`capability_qualification.json`), with independent audits as above.
- **DP-L5. No live provider.** FixtureProvider only, with no spend, so semantic ability is unmeasured.
- **DP-L6. Interpreter-specific attestation.** Code-object and dataclass comparisons depend on the CPython version. A mismatch fails closed (no run) and is never a false VERIFIED.
- **DP-L7. Recorded deviations.** Report §6.1-§6.15 records them, among them:
  - compiler check order;
  - oracle keyed by verifier coverage;
  - the reader shared by the oracle and the actions;
  - `snapshot=` required by `PlanRunner.run`.
  - the package move to `uri_v1/planning/` (report §12).
- **DP-L8. Windows not validated at the frozen head.** Windows validation has not been performed at `565eae8`. Windows Python 3.13.15 ran only at `b6b2cb0`, before the move (§3a).

## 5. Not authorized by this freeze

- Live or production wiring. None happens before the working-product baseline.
- Further slices or Needle integration.
- Any edit to frozen M33.x, RAR, ARN or M36-M38 files.

The slice is reopened only for a defect that violates a guarantee frozen here.
