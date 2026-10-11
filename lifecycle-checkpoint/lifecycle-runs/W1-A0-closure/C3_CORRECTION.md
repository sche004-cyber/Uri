# Correction to coordinator finding C3 (2026-10-11)

Original statement (in the OWNER_UNBLOCK note, events.jsonl 05:56:17): "R5-01 tests write the real user config:
test-isolation defect, follow-up DEV-LIFECYCLE-2".

Corrected after inspection:
- The committed lifecycle suite (canonical ce1a90c / candidate 1f4aedd) is isolated: every test that writes git
  config uses the `user_home` fixture (throwaway HOME, also set in L.GIT_ENV and L.NOBYTECODE for gate commands).
- Evidence: full `tests/dev_workflow/test_lifecycle.py` run with HOME = a sandbox copy of ~/.gitconfig, no failures;
  sandbox copy and real ~/.gitconfig both unchanged (sha256 4d5a9c7e..., mtime 1791689156 before and after).
- The three url.insteadOf entries were written at 03:25:56, during the R5-01 repair (commit dff1ea7 at 03:29).
  One entry names `test_merge_combined_gates_redi*`, a test that never existed in a commit: it came from the repair
  worker's draft tests before the R5-01 fixture change. Workers share the driver's HOME by design; the driver's
  GIT_CONTROL digest detected the change and blocked (TAMPER) - the containment worked.
- So C3 is not a defect in the committed suite. Residual (LOW, non-blocking): a repair worker's draft code can still
  write the user's global git config; it is detected, not prevented. Possible hardening for a later milestone: give
  workers GIT_CONFIG_GLOBAL pointing to a per-run file. Not started.
- Cleanup of the three entries: deferred by the owner until after W1/A0 integration (auto mode refused the edit).
