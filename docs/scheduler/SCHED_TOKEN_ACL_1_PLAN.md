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
- **Links in the state folder (R2-05):** child resets pass `/L`, so icacls acts on a link itself and not on its target. After the folder is closed, any symlink or junction anywhere under it fails closed (`STATE_ACL_FAILED`) before any reset. Otherwise a principal with the old inherited `(M)` could plant a junction and make the scheduler reset the ACL of a folder outside the state folder. The owner removes the link and starts again.
- **Owners of existing children (R3-01):** before its reset, each child is taken over with `icacls <child> /setowner <user> /T /Q /L`. Otherwise a principal that created or replaced an object under the old `(M)` would stay its owner, keeping implicit READ_CONTROL/WRITE_DAC and the ability to grant itself access again. A child the user cannot take over fails the step (`STATE_ACL_FAILED`), and the folder is left closed. The link check runs again once every child is reset, so a link planted between the first check and the resets also fails closed.
- **The state folder itself (R4-01):** the `--state` path must not be a symlink, junction or other reparse point, checked with `lstat` before any step. The folder's closing step also passes `/L`. After it, the path must still be the same object (same `st_dev`/`st_ino`, not a link), checked again at the end. The single DACL write on the folder now also sets the owner (`O:<user SID>D:P(A;OICI;FA;;;<user SID>)`), and the owner is read back with `GetFileSecurityW`. If it is not the current user, startup fails (`STATE_ACL_FAILED`) and the folder is left closed. Otherwise a principal that pre-created the folder, or swapped one in at first launch, would keep owner's implicit WRITE_DAC and could grant itself access again. On Windows, `api-token` is created with `CreateFileW(CREATE_NEW)` and a protected user-only security descriptor, so it never inherits an entry added to the folder through a handle opened before the takeover.
- **Same-user trust limit:** processes running as the same Windows user can still read the token. That is the documented trust boundary (Phase 1 C1), and this fix does not change it.

## Amendment 2026-10-11 — redesign: check and refuse, never repair (owner decision)

**Why.** Follow-up milestone SCHED-TOKEN-ACL-1b tried to repair, in place, a state folder that other principals could already write to. Five independent review rounds each confirmed the earlier findings fixed and found a new race (R1-01 reset window, R1-02 partial reset, R2-05 links, R3-01 child owners, R4-01 folder owner, R5-01 children created during the takeover). `service.py` had grown to about 300 lines of untestable-on-Linux Windows ACL code. The owner chose the redesign ("Redesign", 2026-10-11) and the 1b run was stopped in round 5 (its rounds stay in its state dir and receipt). The design notes above for R2-05, R3-01 and R4-01 describe that superseded approach and are kept as history.

**Design now.**

- **New folder:** created with `CreateDirectoryW` and the descriptor `O:<user SID>D:P(A;OICI;FA;;;<user SID>)`, so it is never open, not even for an instant (POSIX: `mkdir` `0700`).
- **Existing folder:** only checked, never changed. Through one handle opened without following links (`FILE_FLAG_OPEN_REPARSE_POINT`), the folder must be a plain folder owned by the user with exactly that DACL. Everything inside must be a non-link owned by the user, with no explicit entry for any other SID. Otherwise `run` exits 4 (`STATE_ACL_FAILED`) and names `secure-state`.
- **`python -m uri_scheduler.service secure-state --state <dir>`:** a one-off move, run by the owner with the scheduler stopped. It refuses if the scheduler is running or if any link is inside. It renames the old folder to `<dir>.pre-acl-<time>` (kept, never deleted), creates a new locked folder and copies the plain files and folders in. The copies are new files owned by the user and inherit the user-only entry.
- **Token:** created empty inside the checked folder, given its own non-inherited user-only entry (`icacls /inheritance:r /grant:r *<SID>:F`; POSIX `0600`), then written.

**Why this closes the class.** Nothing is repaired while someone else may hold access, so there is no window to race. A folder another principal could have touched is refused, and is moved over only by an explicit owner action.

**Acceptance criteria as amended** (supersede S1 and S2 above; S3–S6 unchanged in intent):

| # | Criterion | Verified by |
|---|---|---|
| S1′ | A new state folder is created already restricted: owner = current user, protected DACL with exactly one inheritable full-control entry for the user (POSIX `0700`). An existing folder that is not exactly that, or is a link, is refused with exit 4, and its ACL is not changed. | test |
| S2′ | Before the database is opened or the token written, nothing inside the state folder is a link, owned by another principal, or carries an explicit entry for another SID; otherwise exit 4. `secure-state` moves an old folder into a new locked one, keeps the old one, and changes nothing if a link is inside or the scheduler runs. | test |

**Owner steps this creates (deployment, not code):**

1. **Existing install:** stop the scheduler and run `secure-state` once on the canonical state folder before upgrading. Until then, `run` refuses to start (fail closed).
2. **`scripts/scheduler_task_ctl.ps1 -Action install`** pre-creates `<State>` with `New-Item`, which gives an ordinary inherited ACL. Run `secure-state` once after installing, or the logon task will exit 4 each time. Changing the installer is outside this milestone's permitted paths (and in the exact-path guard lists), so it is recorded as a follow-up.

## Out of scope

- Moving the state folder.
- Encrypting the token (DPAPI).
- The Task Scheduler logon task (an owner decision recorded in `docs/scheduler`).
- Any Office code.
