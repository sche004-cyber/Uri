# O2 implementation: independent review record

Append-only. Each round names the exact commit reviewed, the verdict, and the disposition of every finding. The
reviewer is a separate Claude agent (Codex optional, owner ruling 2026-10-11). Only results the reviewer or the author
actually ran are claimed as verified.

## Round 1: WS-A backend at `6d2d6816` (2026-10-15)

Scope: contract `o2.1`, capability registry, engine integrity and pin, Job Objects, workers, LibreOffice manager,
sanitizer, validation, engine hub, documents, workflows, safe write, approvals generalization, A2UI actions, intent and
Brain classify, recent list, grants, service routes. Flutter and printing were out of scope.

**Verdict: REVISE** (2 major, no blocker).

Reviewer ran: `tests/office_u2 -m "not engine"` 136 passed; `tests/office tests/a2ui` 483 passed, 5 skipped;
`tests/office_u2 -m engine` 13 passed in 248 s; its own sanitizer-bypass and resume probes.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| 1 | major | Resume ran a plan the owner never approved (start-up turned `waiting_approval` into `interrupted`, resume queued it) | **Repaired.** Apply of a plan records `plan_approved`. At start-up only approved runs (`running`, `ready_to_save`, `needs_review`) become `interrupted`; unapproved plans become `discarded` and their cards close. Resume refuses without `plan_approved`. Tests: `test_workflow_resume.py` (unapproved plan discarded and not resumable; approved run interrupted then resumed to `ready_to_save`; changed input stops with `INPUT_CHANGED`). |
| 2 | major | Sanitizer bypasses: split complex-field instruction; main part moved out of `word/`; main part renamed `.dat` | **Repaired.** Parts are chosen for parsing by name and by `[Content_Types].xml`, never by folder; cleaning applies to every parsed part of the kind; complex-field instructions are joined from begin to separate (nested frames kept) before matching; a non-XML-named part that is markup with a DOCTYPE/ENTITY is refused. `DisableActiveContent=true` added to the hardened profile (the key exists in the pinned `main.xcd`). Sanitizer version `s1` -> `s2` (preview cache key). Tests: 4 new sanitizer tests; engine canary `test_split_field_canary_makes_no_connection` for the sanitized copy **and** for the unsanitized file under the hardened profile alone (both 0 HTTP, 0 SMB, 0 engine connections). |
| 3 | minor | Cancel while queued ended `failed`; a cancel during the last steps was overwritten; future timeout recorded as a class name | **Repaired.** `CANCELLED` from the engine queue maps to `cancelled`; the cancel flag is checked before the final state; a future timeout maps to `ENGINE_TIMEOUT`; unexpected exceptions map to `ENGINE_CRASHED`; failed runs remove their work files. Test: `test_cancel_while_queued_ends_cancelled_not_failed`. |
| 4 | minor | Interrupted runs were never removed | **Repaired.** Every non-running record older than 7 days is removed at start-up. Test: `test_old_interrupted_runs_are_removed_after_retention`. |
| 5 | minor | Launch check skipped the bundled Python's code and files added after start-up; signer check not implemented | **Partly repaired.** Launch check now refuses any file in `program/` that is not in the manifest (for example a dropped `sitecustomize.py` or `.pth`) and re-hashes `.py .pth .ini .cfg .pyc` under `program/` as well as executables and libraries. Tests: 4 new `test_engine_pin.py` cases. **Open:** the Authenticode signer check (plan F11) is not implemented; the SHA-256 manifest pin is the integrity control in force. Recorded for the O2 closing review. |
| 6 | minor | All pages rasterized in one 120 s request; a timeout failed the workflow | **Repaired.** Batches of 20 pages, each with its own timeout; a failed batch becomes an error finding (`N page(s) could not be drawn`), not a failed workflow. |
| 7 | minor | A leftover `.part` file broke a cached page permanently | **Repaired.** Each render writes a uniquely named `.part` file. |
| 8 | minor | Run-copy leak on spawn failure; old save-as grants not revoked; `/answer` ignored its workflow; `listing()` without a lock | **Repaired** (all four). `/answer` now requires an existing workflow and routes with its input kind. |
| 9 | minor | No §5.1 concurrency test; `/capabilities` reported engines ready before the hub started | **Repaired.** `test_workbook_save_completes_while_a_conversion_runs` (a workbook save is applied in under 5 s while a conversion is blocked); before the hub starts, engine capabilities report `unverified` / not ready. `/workflow` now returns the engine's reason when it is `unavailable`. |
| notes | note | Contract gaps (DocView fields, C3 wording, uncatalogued codes, `help` result, `/request` fields, resume rules, output write inside apply) | **Contract updated** to match the code (`O2_API_CONTRACT.md`). Font names in finding messages come from the document; they are owner-facing only. Commit message test count corrected here: at `6d2d6816` the suite collected 149 tests (136 + 13 engine). |

After repair (author's runs, 2026-10-15): `tests/office_u2 -m "not engine"` **154 passed**; `tests/office_u2 -m engine`
**15 passed** in 233 s; `tests/office tests/a2ui` **483 passed, 5 skipped**.
