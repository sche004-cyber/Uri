# DEV-LIFECYCLE-3B — gates fail closed without real test execution (DRV-3)

Milestone of the lifecycle driver (`scripts/dev_workflow/lifecycle.py`), separate from the UI V2 post-integration
repairs that build on it. Classification: **INTERNAL** (driver infrastructure; no user interface). It is verified by
driver tests that reproduce the defect, by the driver's own gates, and by its use as the qualification engine of the
next milestone (UI-V2-POSTINT), whose Flutter gates must now carry real execution evidence.

Baseline: canonical `integration/git-sync-20261008` @ `2eff03d086e3cacbcd2682bf4f75b7e51d4fa919` (verified with
`git ls-remote uri-repo` on 2026-10-16), then `eaeb10c126132b014751674a1fed7d734122e653` after canonical moved (URI Office
O2 integration, which also added `test_setup` steps to the driver; merged in `1dbbfbe6`, revision config c3).
Branch `milestone/dev-lifecycle-3b-flutter-gates-20261016`.

## Defect (DRV-3)

Found after the UI V2 integration (2026-10-16, receipt `docs/ui_v2/completion/integration/` on
`receipts/ui-v2-20261016`). The UI-V2-COMPLETION r1/r2 Flutter gates ran `flutter test --no-pub` and
`flutter analyze --no-pub` in fresh detached qualify and baseline worktrees that have no
`uri_ui/.dart_tool/package_config.json`. Both sides failed (`cannot run without a dependency on either
"package:flutter_test" or "package:test"`; analyze: 21007 unresolved-package issues). `run_gate` recorded the no-report
run as failure `flutter::__run__`; `compare()` found the same failure on the baseline, classed it historical and the
gate reported ok. The driver showed "no new failures" with zero tests executed.

## Change

1. **Dependency preparation.** A gate whose cwd holds `pubspec.yaml` and whose tool is `flutter`/`dart` first runs
   `<tool> pub get --enforce-lockfile --offline` in that cwd (gate option `"pub_offline": false` drops `--offline`,
   `"prepare": false` turns preparation off). The shared pub cache is reused (no download when it is complete); the
   committed `pubspec.lock` is used as-is and a lock that would change fails. Failure is `BLOCKED` with detail
   `INFRA dependency preparation failed ...`, never a test result. The prepare log is kept as
   `gates/<sha>/<gate>.prepare.log`, the lock hash in the result.
2. **Execution evidence.** pytest/flutter results record `executed` (passed + failed), `passed`, `skipped`,
   `exit_code` and an evidence class: `EXECUTED`, `NO_TEST_REPORT` or `ZERO_TESTS`. Zero executed tests is a failure
   unless the gate sets `allow_zero_tests` to a written justification (a bare `true` is not one).
3. **No excuse from the baseline.** Candidate and baseline both without execution: the qualification is BLOCKED
   (`RESOURCE`, `INFRA no test execution on candidate (...) or baseline (...)`), never ok. A baseline without execution
   is no comparison base: every candidate failure counts as new. A candidate without execution against a baseline
   that executed stays a new failure (`<gate>::__run__`), routed to repair as before.
4. **Cache validity.** The baseline cache key binds `GATE_SCHEMA` (5 after the review repairs; it was 2 in the first
   commit) and, for Flutter/Dart gates, the toolchain fingerprint (`flutter --version --machine`: framework, engine,
   Dart revisions; `dart --version` for Dart), plus the preparation settings (`prepare`, `pub_offline`,
   `prepare_timeout_s`) and `allow_zero_tests`. A failed fingerprint probe makes the result uncacheable. Results
   cached under the old rules are never reused; a toolchain change re-runs the baseline. Dependency changes are bound
   by the baseline SHA (its lock file) and by `--enforce-lockfile`; preparation that changes `pubspec.lock` or any
   tracked file blocks.
5. **Recorded counts.** Per-gate counts for candidate and baseline go into the hash-chained `QUALIFICATION` event
   (`counts`) and into `receipt.json` gates.

No new dependency, no second lifecycle authority, no change to reviewer, implementer, integration or containment code.
Compatible with the planned V3.1 persistent task/cache architecture: the cache stays keyed by baseline SHA, command
and toolchain, and the result rows already carry what a persistent store needs.

## Acceptance criteria

- AC-1 A test reproduces DRV-3 exactly (dependency preparation off, both sides cannot run) and fails on the
  canonical driver (it reached VERIFIED), passes on the repaired driver (BLOCKED RESOURCE, no evidence_ok).
- AC-2 With preparation (default) a Flutter gate's tests really execute on both sides; counts (executed 2, passed 2)
  and the prepare record (`--enforce-lockfile --offline`, lock hash) are in state, receipt and the event chain.
- AC-3 Offline dependency failure blocks transparently (`INFRA dependency preparation failed`, tool output kept).
- AC-4 Baseline without execution never excuses the candidate; candidate without execution is never ok.
- AC-5 Zero executed tests is never a pass unless justified in writing; pytest gates too.
- AC-6 Baseline cache follows the toolchain fingerprint and `GATE_SCHEMA`.
- AC-7 Python and command gates keep their behaviour; the whole `tests/dev_workflow` suite shows no new failure.
- AC-8 Independent driver-counted review (Codex) of the whole diff, ACCEPT or ACCEPT WITH FINDINGS with no open
  blocking finding.

## Evidence (coordinator, before the driver run)

- `tests/dev_workflow/test_lifecycle_drv3_flutter_gates.py`: 10 passed on the repaired driver. Against the canonical
  driver (scratch worktree at `2eff03d0`, same test files): 9 failed, 1 passed; the DRV-3 reproduction reached
  `VERIFIED` there.
- Full `tests/dev_workflow` on `8923590c`: 252 passed, 5 skipped, 1 failed. The failure,
  `test_lifecycle_platform.py::test_win_breakaway_is_refused` (`STARTED` instead of `REFUSED`), fails identically on
  canonical `2eff03d0` and is not caused by this change: on this host a child process can break away from a Windows
  job (environment-dependent containment check). Recorded as finding DRV-ENV-2, owner: lifecycle driver; not repaired
  here.

## Review history (driver run DEV-LIFECYCLE-3B, state `uri-dl3b-run/r1`, canonical driver at `2eff03d0`)

| Round | Reviewer | Candidate | Verdict | Findings → repair (driver implementer) |
|---|---|---|---|---|
| R1 | codex_cli | `bea47154` | REJECT | R1-01 zero-test results could pass via `allowed_flaky`/`required: false`; R1-02 toolchain key collision on a failed probe, memoized by name; R1-03 lock/tracked files not proven unchanged → `146d3e42` |
| R2 | codex_cli | `146d3e42` | REJECT | R2-01 hidden Flutter failure could make a zero-test gate pass; R2-02 baseline cache survived a preparation change → `dcbaf4ca` |
| R3 | codex_cli | `dcbaf4ca` | REJECT | R3-01 falsy `pub_offline` allowed network; R3-02 `allow_zero_tests` change did not invalidate the cache → `b231231c` |
| R4 | codex_cli | `b231231c` | REJECT | R4-01 receipt lacked the preparation command and lock hash (AC-2) → `7ed88cc6` |
| R5 | codex_cli | `7ed88cc6` | ACCEPT WITH FINDINGS | R5-01 LOW: this plan named `GATE_SCHEMA` 2 (repaired in the final revision) |

Gates on `7ed88cc6`: `tests/dev_workflow` candidate 268 passed, 5 skipped, 1 historical failure (DRV-ENV-2);
baseline 242 passed, 5 skipped, the same failure; no new failure. Stage VERIFIED, BLOCKED OWNER_AUTHORIZATION,
`evidence_ok_for_candidate: true`, `verify` OK.

## After canonical moved to eaeb10c1

- Merge `1dbbfbe6` (one conflict: the baseline cache key keeps the DRV-3 inputs and adds `test_setup`). Revision c2
  (`fd2b0713`) parked WAITING_FOR_MODEL (Codex usage limit).
- Imported review C1 (independent read-only Claude agent, owner instruction while Codex was unavailable; NOT
  driver-counted): ACCEPT WITH FINDINGS on `fd2b0713`, confirming the DRV-3 reproduction reaches VERIFIED on canonical
  `eaeb10c1` and is blocked on the candidate. Repaired: C1-01 a Dart gate with `"prepare": false` and no
  `.dart_tool/package_config.json` (e.g. `flutter analyze --no-pub`) is BLOCKED INFRA instead of comparing two
  identical failures; C1-02 regression proofs prepare Dart runners and report a preparation failure as INFRA; C1-03
  only tracked files changed by `pub get` itself are attributed to it; C1-04 a justified zero-test run is labelled
  `ZERO_TESTS_JUSTIFIED` and pytest's "no tests collected" exit 5 is accepted only then (`GATE_SCHEMA` 5); C1-05 this
  section; C1-06 tests `tests/dev_workflow/test_lifecycle_drv3_review_c1.py`. Revision c3 is the driver-counted review.

## Owner decisions

- Canonical integration of this milestone needs owner authorisation (not granted; config `authorized: false`).
