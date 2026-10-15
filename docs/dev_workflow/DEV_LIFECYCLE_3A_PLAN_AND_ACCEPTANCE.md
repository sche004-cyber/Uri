# DEV-LIFECYCLE-3A: Codex reviewer on Windows (driver adapter repair)

Date: 2026-10-15. Branch `milestone/dev-lifecycle-3a-codex-win-sandbox-20261015`, baseline `1b5423bc` (canonical
`integration/git-sync-20261008`). Development tooling only; not part of the URI runtime.

## Problem (evidence)

DEV-LIFECYCLE-3 round R1 (`codex_cli`, `gpt-6-sol`, session `codex_cli-fa492a8a-4b87-462f-80a4-7d5a04a31756`) could
run no shell command: every command was rejected with `blocked by policy`. The reviewer inspected nothing and the
driver stopped BLOCKED NO_ACTIONABLE_FINDINGS.

## Root cause (probe, codex-cli 0.158.0, Windows 11 Pro 10.0.26200)

The driver gives a `codex` reviewer a fresh `CODEX_HOME` with only `auth.json` (`reviewer_codex_home`, R6-02/R7-01:
the user's `config.toml` must not reach the reviewer). The user's `config.toml` sets `[windows] sandbox =
"unelevated"`; the fresh home has no Windows sandbox mode. Same prompt, same model, same fresh home, `--sandbox
read-only -C <candidate checkout>`:

| Run | `git rev-parse HEAD` | write `probe_write.txt` |
|---|---|---|
| no Windows sandbox setting | rejected: `blocked by policy` | rejected by the read-only sandbox |
| `-c windows.sandbox="unelevated"` | ran; printed the exact HEAD (not present in the prompt) | `Access ... is denied`; no file created |

Not the cause: model availability (`gpt-6-sol` answered in both runs), authentication (`auth.json` worked in both),
filesystem access rights of the user, the driver's prompt.

## Change

`build_argv` adds `-c windows.sandbox="unelevated"` to `codex exec` on Windows only, for both roles. `--sandbox
read-only` (reviewer) and `workspace-write` (implementer) are unchanged, so the sandbox stays enforced; nothing is
disabled and the user's global Codex configuration is not read or changed. The same mode is the one the owner's own
Codex configuration already uses.

## Acceptance criteria

- AC-A1: on Windows, `codex_cli` argv for reviewer and implementer contains `-c windows.sandbox="unelevated"`; on
  other platforms it does not (unit test `test_3a_codex_gets_windows_sandbox_only_on_windows`).
- AC-A2: `--sandbox read-only` / `workspace-write`, `--model`, `-c project_doc_max_bytes=0` and the stdin prompt `-`
  are unchanged (existing R6-02 test plus AC-A1 test).
- AC-A3: `tests/dev_workflow` passes (no regression).
- AC-A4: a driver-run `codex_cli` reviewer round on Windows shows real inspection: non-empty `tests_run` with
  COMPLETED_WITH_RESULT entries for commands it ran itself, and no change to the candidate checkout.
- AC-A5: no change outside `scripts/dev_workflow/lifecycle_providers.py`, `tests/dev_workflow/**` and this file.

## Revision 2 (2026-10-15): two more Windows driver defects found while auditing DEV-LIFECYCLE-3

- DRV-1: a driver repair could not commit a tracked file under the ignored `.claude/` directory (the lifecycle skill):
  `git add -A -- <path>` refuses ignored paths, so every repair of the skill ended BLOCKED REPAIR_FAILED
  (DEV-LIFECYCLE-3-r2 and -r3, three attempts each). Fix: `_commit_and_prove` adds paths already in the index with
  `-f`; any other path keeps plain `git add -A`, so a new file under an ignored directory is still refused.
- DRV-2: worker, gate and git output was decoded with the Windows ANSI code page (cp1252); a UTF-8 character such
  as a curly quote (byte 0x9d) killed the reader thread and lost that stream (DEV-LIFECYCLE-3-r2..r4 logs; in r4 the
  repeated tracebacks also exhausted the PowerShell host that redirected them). The prompt sent on stdin was also
  encoded as cp1252. Fix: every `text=True` subprocess in `lifecycle.py` and `lifecycle_providers.py` uses
  `encoding="utf-8", errors="replace"`.

| ID | Criterion | How it is checked |
|---|---|---|
| AC-A6 | DRV-1 repaired: a repair of a tracked file under an ignored directory commits; a new ignored file is not force-added | `test_3a_repair_of_a_tracked_file_under_an_ignored_directory_is_committed` (fails before, passes after), `test_3a_new_ignored_file_is_still_not_force_added` |
| AC-A7 | DRV-2 repaired: UTF-8 worker stdout and stderr are recorded intact | `test_3a_worker_output_is_decoded_as_utf8` (fails before, passes after) |
| AC-A8 | AC-A5 widened to `scripts/dev_workflow/lifecycle.py`; nothing else outside the AC-A5 list changes; `tests/dev_workflow` passes | diff, driver gate |

## Known limits

- Only the unelevated mode was probed; it is the mode the owner already runs. Codex also offers an elevated Windows
  sandbox (not probed here); switching to it is an owner choice and needs its own probe.
- The patched driver itself launches the reviewer that reviews it. The reviewer is a separate vendor model in a
  separate process with a fresh home. The changes are small (two argv elements, subprocess decoding, one `git add`
  split); the unit tests, their fail-before/pass-after runs and the probe above are the evidence for their effect.
- The 3A tests use `write_bytes`/`-X utf8` in their own helper; other tests' `_script_worker` still writes scripts
  in the platform encoding (test-only, ASCII scripts).
