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

## Round 2: WS-A backend at `c974a655` (2026-10-15)

**Verdict: ACCEPT WITH FINDINGS.** Both round-1 majors and minors 3, 4, 6 to 9 are repaired; finding 5 is partly
repaired with the signer check disclosed as open.

Reviewer ran: `tests/office_u2 -m "not engine"` 154 passed; `tests/office tests/a2ui` 483 passed, 5 skipped (two
`test_page.py` tests skip asking for `npm ci`, three are POSIX-only); `tests/office_u2 -m engine` 15 passed in 267 s;
the resume probe (an unapproved plan becomes `discarded`, resume refused, nothing queued); the three sanitizer bypass
probes (each now cleaned, `removed={'field': 1}`); and one further case through the real engine (below).

| # | Severity | Finding | Disposition |
|---|---|---|---|
| N1 | note | A part with a non-XML name **and** a non-XML or missing content type is still not parsed. Reviewer ran it through the pinned LibreOffice: the engine refuses to load such a part (`PREVIEW_UNAVAILABLE`), the HTTP canary got 0 hits. | Accepted as mitigated on the pinned engine. Hardening option (parse any part on the main-document relationship path that starts with `<`) recorded for the closing review. |
| N2 | note | Contract lists `BAD_REQUEST` as uncatalogued, but `contracts.ERRORS` has it | To fix in the contract wording. |
| F5-open | minor | Authenticode signer check (plan F11) not implemented; the SHA-256 manifest pin is the integrity control in force | Carried to the O2 closing review. |

**Status:** WS-A backend accepted at exact commit `c974a655` (ACCEPT WITH FINDINGS, no open blocker or major). The
contract `o2.1` is the interface O2P builds on (A5 freeze condition: contract tests pass and independent review
accepts).

## Round 3: Flutter B1 workspace, O2P printing and live-run repairs at `63e0e73f` (2026-10-15)

**Verdict: REVISE (narrow)**, 2 major in the opt-in print path, no blocker. Reviewer ran: `tests/office_u2 tests/devices`
not engine 179 passed (incl. the real Microsoft Print to PDF job); `tests/office tests/a2ui` 483 passed, 5 skipped;
`flutter test` 587 passed, 5 skipped; engine subset (canaries, chart, hardened profile) 8 passed; `Get-PrintJob` 0 jobs;
tallied the live JSON (run 7: 36 PASS, 4 NOT VERIFIED, 0 FAIL; UI run 2: 17 steps) against the README. It diffed the
extracted sheet companion against the removed code: textually identical.

| # | Severity | Finding | Disposition |
|---|---|---|---|
| M1 | major | OneNote (`nul:`) and fax queues offered; printing to them opens another program's window | **Repaired.** Devices carry `supported` / `unsupported_reason`; `nul:`, `NEnn:`, `XPSPORT:`, fax ports or drivers, and `PORTPROMPT:` queues that are not PDF writers are listed as "not used by URI" and refused with `PRINTER_NOT_SUPPORTED`; they do not count as physical printers. Test `test_queue_that_opens_another_program_is_refused`. |
| M2 | major | "Fit to page" fitted inside default 1-inch margins (pages at about 76 %), and the card did not say so | **Repaired.** Fit uses the printable area (rotated for landscape). Measured on the same page: leftmost ink 0.21 of the width with the old worker, 0.118 with the new (expected 0.118) — `o2p_s11_20261015/s11_rerun_result.json`; PR-5 test now asserts it. |
| m1 | minor | Cancel races; a cancel during printing did not stop the worker | **Repaired.** The runner takes the job lock at start; a cancel while printing sets the flag and closes the worker's Job Object; the runner finishes as `cancelled` and deletes any spooled job by its token. |
| m2 | minor | Print error codes missing from the catalogue; `status` could return 500 | **Repaired.** 10 print codes with messages and recovery (`check_printers`, `choose_printer`) in `contracts.ERRORS` and the Dart table; `find_job` errors become "status unavailable". |
| m3 | minor | Invalid page range silently became "all"; totals and thumbnails from the wrong PDF for a task output | **Repaired.** Totals come from the PDF being printed; an invalid range is never sent (buttons disabled); task-output thumbnails come from the output PDF. |
| m4 | minor | `uri office <view>` from a document/task/sheet view did not move the centre | **Repaired**, test added (from a document view). |
| m5 | minor | Absolute blank rule missed "page number only" pages | **Repaired.** Ink in the top 5 % and bottom 8 % bands is ignored; tests for both cases. |
| m6 | minor | Used-fonts logic missed bullets and East Asian / complex-script theme references | **Partly repaired** (`numbering.xml`, `eastAsia`, `eastAsiaTheme`, `cstheme`). Theme script fonts (e.g. Deva) still not resolved; false negatives only. |
| m7 | minor | Device descriptors described as used by the routes; two copies could drift | **Repaired** (docstring corrected; test keeps effects, approval and inputs in agreement). |
| m8 | minor | Evidence statements not backed by recorded data | **Repaired** with corrections: `Get-PrintJob` is now recorded by `s11_rerun.py` (0 jobs); the chart comparison is recorded (`chart_disableactivecontent_check.json`); "no dialog" is labelled inferred; S11's first-run claims corrected. A1's GPU statement gets a correction note on the planning branch. |
| m9 | minor | Print worker GPU use not measured | **Measured:** 53 MB at 300 dpi, 146 MB at 600 dpi dedicated GPU memory while printing, engine ≤ 2 %; released when the job's process exits. Added to the owner GPU decision. |
| n1 | note | Hardened profile alone covered DOCX only | **Added** unsanitized PPTX and XLSX canaries under the profile alone: 0 connections. |
| n4 | note | Workspace polls every 700 ms for the session | Accepted for O2 (cheap); recorded. |

**Found while repairing (author):**
- The first attempt to re-check the chart cause appended `DisableActiveContent` at the end of the profile; LibreOffice
  dropped it silently, so that attempt showed nothing. With the exact profile of `c974a655` the setting is applied
  and charts break (single-slide and deck); without it both render (`chart_disableactivecontent_check.json`).
- That led to checking every hardened setting: **4 of 20 were not in effect.** The FTP proxy keys and
  `CollectUsageInformation` do not exist in LibreOffice 26.8 (removed), and the update-check switch needed
  `oor:type` (LibreOffice had reset it to `true`; headless never runs that job, and the proxy blocks it, but the
  claim "update checks disabled" was not true before this repair). Now 17 of 17 are in effect
  (`hardened_profile_effective.json`) and engine test `test_every_hardened_setting_is_in_effect` guards it.

After repair (author's runs): `tests/office_u2 tests/devices` not engine **182 passed**; `tests/office_u2 -m engine`
(render engine file) **15 passed**; `tests/office tests/a2ui` **483 passed, 5 skipped**; `flutter test` **587 passed,
5 skipped**.

## Round 4: re-review at `89134547` (2026-10-15)

**Verdict: ACCEPT WITH FINDINGS.** Round-3 majors and minors repaired (m6 partial, disclosed). Reviewer ran:
`tests/office_u2 tests/devices` not engine 182 passed (incl. the virtual-printer job with the fit assertion);
`tests/office tests/a2ui` 483 passed, 5 skipped; `flutter test` 587 passed, 5 skipped; engine subset (profile in
effect, unsanitized PPTX/XLSX canaries, chart, canaries, positive control) 10 passed; `Get-PrintJob` 0 jobs. It
checked the M2 arithmetic and evidence, the M1 refusal, and the 17/17 profile result.

Open minors (not fixed at this commit; carried to the next O2P round; printing stays off unless `--enable-printing`):
1. `_support` also trusts the printer **name** for "PDF" on a `PORTPROMPT:` queue; check the driver only.
2. Unknown custom ports (third-party virtual printers such as `CPW2:`) count as supported and physical; label or
   refuse until qualified.
3. A short cancel window between "printing" and the worker's Job Object existing; re-check the cancel flag before
   spawning, and report `output_written` on a cancelled job.
4. Note: "All" pages for a task output without a page count is rejected (edge case; outputs always record pages).
5. m6 partial: theme script fonts (e.g. Deva) not resolved (missed warnings only).
Still open from earlier rounds: no tests for U1 (sizes persist after restart), U7 (every error state), U11 (keyboard,
Tab order, labels).

**Live re-run at this exact commit** (`evidence/o2_live_20261015/at_89134547/`): service run 8 **36 PASS, 0 FAIL,
4 NOT VERIFIED** (physical printing); UI run 3 **COMPLETED_WITH_RESULT**, 17 steps.
