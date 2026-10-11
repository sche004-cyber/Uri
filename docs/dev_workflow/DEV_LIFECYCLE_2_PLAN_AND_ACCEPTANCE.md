# DEV-LIFECYCLE-2 — Windows support and remote repair for `uri-development-lifecycle`

Owner direction, 2026-10-11. Baseline: canonical `integration/git-sync-20261008` @ `ce1a90c` (repository
`github.com/sche004-cyber/Uri`). Candidate: `milestone/dev-lifecycle-2-20261011`. Run through the skill itself:
plan, separate candidate worktree, independent `claude_cli` reviewer in a fresh process, repair, re-audit, receipt.

## Findings (from an independent review on the owner's Windows 11 PC)

| Id | Severity | Finding |
|---|---|---|
| F1 | HIGH | `_killpg` calls `os.killpg(pid, signal.SIGKILL)`; neither exists on win32 and only `OSError` is caught, so every gate, test and worker crashes with `AttributeError` after it ends (`lifecycle.py:667/672`, `lifecycle_providers.py:55/134/464`). |
| F2 | HIGH | Containment is Linux-only (`PR_SET_CHILD_SUBREAPER`); on win32 `sweep_orphans()` returns `contained=False`, so `is_independent()` rejects every real review and ACCEPT is impossible on the owner's PC. |
| F3 | MEDIUM | SKILL.md Stage 1 and `TEMPLATE.json` use `origin`; in local clones `origin` is `uri-agent`, which lacks the canonical branch, so the baseline lookup returns nothing. |
| L1 | LOW | SKILL.md says "Do NOT use for ... office tasks": URI Office development milestones must be clearly in scope. |
| L2 | LOW | The older `uri-development` skill overlaps; add one line saying `uri-development-lifecycle` wins for milestones (do not delete it). |
| L3 | LOW | `CAPABILITY_LEDGER.md` is stale (the skill is in canonical `ce1a90c`); platform status must be honest. |

## Design

**One process-containment module** (`scripts/dev_workflow/containment.py`) used by every worker and gate:
`spawn()`, `finish()` (end the tree, then verify), `precheck()` (before each worker), `kill_tree()`.

- **Linux:** unchanged behaviour (process group + child subreaper sweep).
- **Windows:** a Job Object per worker/command through stdlib `ctypes` only (no pywin32). The child is created
  `CREATE_SUSPENDED`, assigned to the job, and only then resumed, so it cannot start a child outside the job. The job
  has `JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE` and no breakaway flags. After the worker or command:
  `TerminateJobObject`, then `QueryInformationJobObject(JobObjectBasicAccountingInformation)` must show
  `ActiveProcesses == 0`; only then `contained=True`. Before each worker, every earlier job must still show 0.
- **Other platforms, or any containment API failure:** `contained=False` (fail closed); a real milestone review does
  not count. Process termination never calls `os.killpg` where it does not exist.

**Canonical remote by URL, not by name.** The config names `canonical_url`. The driver lists the repository's remotes
(`git remote get-url`, which applies `insteadOf`), normalises the URLs (scheme, `.git`, trailing `/`, case) and uses
the one remote that points at it; zero or several matches is BLOCKED. A baseline given as a branch of that remote is
read with `ls-remote`; an empty answer is BLOCKED, never "no baseline". Integration uses the resolved remote, and a
configured `integration.remote` that differs is BLOCKED. An empty target-tip lookup at integration is BLOCKED.

## Acceptance criteria

| # | Criterion | Evidence |
|---|---|---|
| DL2-AC1 | No code path on the worker or gate route calls a POSIX-only API where it does not exist (`os.killpg`, `os.getsid`, `signal.SIGKILL`, `start_new_session`, `/proc`); with `os.killpg` absent, `_killpg`/tree kill on an exited PID returns without raising. | Linux test simulating win32; Windows test on the PC |
| DL2-AC2 | Windows: every worker and gate runs in its own Job Object from its first instruction (suspended → assigned → resumed); a failure to create or assign gives `contained=False`. | Linux logic tests with a fake kernel32 (call order and flags); Windows tests |
| DL2-AC3 | The job sets `KILL_ON_JOB_CLOSE` and never `BREAKAWAY_OK` / `SILENT_BREAKAWAY_OK`; a child's breakaway attempt is refused or recorded as not contained. | fake-kernel32 flag test; Windows breakaway test |
| DL2-AC4 | `contained=True` only when the job reports `ActiveProcesses == 0` after termination, and every earlier job still does before the next worker starts; a grandchild started by a worker is gone after the sweep. | fake-kernel32 tests; Windows grandchild test |
| DL2-AC5 | A job-creation failure gives `contained=False` and `is_independent()` False for a real milestone. | Linux test |
| DL2-AC6 | `canonical_url` resolves to exactly one remote; none or several → BLOCKED; `insteadOf`-rewritten URLs are compared after rewriting. | Linux tests with temporary repositories |
| DL2-AC7 | An empty baseline `ls-remote` → BLOCKED; an empty integration target tip → BLOCKED; a configured `integration.remote` that is not the resolved remote → BLOCKED. | Linux tests |
| DL2-AC8 | SKILL.md, `URI_DEVELOPMENT_LIFECYCLE.md` and `TEMPLATE.json` describe the URL-resolved remote; SKILL.md scopes out "URI runtime office or document tasks" only (L1). | review |
| DL2-AC9 | `CAPABILITY_LEDGER.md` records the skill as integrated at `ce1a90c`; Linux TESTED, Windows NOT VERIFIED until the PC qualification run; the Windows limitations are listed (L3). | review |
| DL2-AC10 | Windows-only tests are marked platform-gated and reported by name on other platforms, never silently skipped; all existing `tests/dev_workflow` tests still pass on Linux. | Linux run output |
| DL2-AC11 | Each new test fails on the baseline `ce1a90c` and passes on the candidate (Windows-only tests: on the PC). | driver regression proof; manual pre-repair run |
| DL2-AC12 | No frozen path, `.gitignore` or new third-party dependency touched. | driver scope/protected-path checks |

## Disclosed limitations (not covered by containment)

- **Windows:** processes started outside the job by other routes are not in it: Task Scheduler tasks, WMI
  `Win32_Process.Create`, services, COM out-of-process servers, and anything a separate already-running process
  starts on a worker's request. A job also does not stop a worker from changing files the user can write; the driver's
  integrity checks cover the repository, not the whole machine.
- **Linux, for comparison:** the subreaper catches every descendant that is re-parented (including `setsid()`
  children) but not processes started by other routes either (`systemd-run`, cron/at, a D-Bus-activated service, a
  process started by an already-running daemon).
- **Bootstrap:** the reviewer cannot yet be qualified on Windows, so the review runs on Linux at the exact candidate
  SHA. Windows results are NOT VERIFIED until the owner's PC runs `tests/dev_workflow` and one real DEVTEST round.
- **L2:** the older `uri-development` skill is not in any branch of `sche004-cyber/Uri` or `sche004-cyber/uri-agent`
  visible to the cloud session (it is presumably local to the owner's PC), so its one-line note is applied on the PC.

## Integration

Under D1: independent ACCEPT on the exact commit, blocking findings resolved, provenance and frozen-file checks,
combined gates, receipt; fast-forward only into `integration/git-sync-20261008`. W1/A0 is also pending (merge mode,
expected tip `ce1a90c`): whichever integrates second must be brought onto the new tip and re-reviewed (fast-forward
only here), and that is recorded rather than worked around.
