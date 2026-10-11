# SCHED-TOKEN-ACL-1 — scheduler token and state folder: current user only

- **Date:** 2026-10-11
- **Coordinator:** Claude. The owner asked for this fix, as its own small milestone, while the URI-OFFICE-M1 review runs.
- **Process:** `uri-development-lifecycle` (independent `claude_cli` reviewer, gates, receipt). Integration needs owner authorisation (D1).

## Baseline (verified)

- **Canonical:** `integration/git-sync-20261008` = `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` (`git ls-remote uri-repo`).
- **Candidate:** branch `phase/sched-token-acl`, worktree `C:\Users\cheta\Development\uri-sched-acl`.
- **Frozen paths:** `uri_scheduler/` is not in `scripts/ws_frozen_check.py` `PROTECTED`.

## Problem (evidence)

- `uri_scheduler/service.py` writes the per-launch bearer token with `token_path.write_text(token)` to `<state>/api-token`, and sets no permissions. Its docstring claims the token is "readable by the same Windows user".
- **Observed on the owner's PC (2026-10-11):** `icacls` on a scheduler `api-token` showed inherited entries for several SIDs, plus `ChetanPC\CodexSandboxUsers:(I)(M)`, `NT AUTHORITY\SYSTEM`, `BUILTIN\Administrators` and the user. So other local principals could read the token, or modify the file.
- **Folder rights:** modify rights on the containing folder also allow deleting and replacing the token and the scheduler database.

## Acceptance criteria

| # | Criterion | Verified by |
|---|---|---|
| S1 | On `run`, before the database is opened or the token written, the state folder's ACL is replaced by exactly one inheritable full-control entry for the current Windows user, with inheritance removed (`icacls <state> /inheritance:r /grant:r <user>:(OI)(CI)F`). On POSIX the folder mode is `0700`. | test |
| S2 | Files that already exist in the state folder (e.g. `scheduler.db`, an old `api-token`) end up with only the inherited current-user entry, not the old inherited ones. | test |
| S3 | The token file is created new on every launch, restricted to one current-user entry before the token is written (POSIX `0600`). | test |
| S4 | If restricting the folder or the token file fails, the service refuses to start with exit code 4 and a clear `{"error": "STATE_ACL_FAILED"}` line; no token is left on disk. | test with a failing `icacls` |
| S5 | Existing behaviour is unchanged: the scheduler suite passes (71 tests at baseline), the bearer-token check, `service.json`, and the Living UI's `scheduler_client.dart` reading `api-token` as the same user. | gates |
| S6 | No frozen path changes; `ws_frozen_check` passes. | gate |

## Design

- One helper in `uri_scheduler/service.py`: `restrict_to_user(path, folder=)`, plus `write_token_file(path, token)`.
- It uses the same commands as `uri_office/service.py` on `phase/uri-office` (copied, not imported, so the two milestones stay independent).
- No other module changes.
- **Same-user trust limit:** processes running as the same Windows user can still read the token. That is the documented trust boundary (Phase 1 C1), and this fix does not change it.

## Out of scope

- Moving the state folder.
- Encrypting the token (DPAPI).
- The Task Scheduler logon task (an owner decision recorded in `docs/scheduler`).
- Any Office code.
