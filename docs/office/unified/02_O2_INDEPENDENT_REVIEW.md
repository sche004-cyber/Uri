# O2 plan: independent review record

Reviewer: a separate Claude agent, read-only, with no part in writing the plan. Codex is optional under the lifecycle;
the Codex MCP server failed to connect in this session. Brief: verify every claim against primary source and evidence,
then classify findings as BLOCKER, MAJOR, MINOR or NOTE.

## Round 1, at `d2706bff` (plan rev 1)

**Verdict: REVISE.** 2 blockers, 13 major, 8 minor, 2 notes.

The author spot-checked these findings in source before repairing:
- F2: `living_shell_test.dart:235` A4 flow on Documents.
- F3: `presentation_controller.dart:118,157-178` mode-only history.
- F12: committed JSON shows 60 ms and 84 ms, and starts with a PyMuPDF stdout line.
- F22: `uri_core/services/pdf_reader.py`.
- F24: `webview_bridge.cc:197-200` `TextureRegistrar`.

All five were confirmed.

| Id | Severity | Finding (short) | Disposition in rev 2 |
|---|---|---|---|
| F1 | BLOCKER | The approval path is workbook-shaped. "Reuse without a new path" was unproven. | Repaired. New section 5.1 adds `subject_kind`, `propose_outputs` and `propose_plan`, a per-action hash key, dispatch before the session lookup, one region-level Dart hub, and migration and regression tests. Section 1.2 row rewritten. |
| F2 | BLOCKER | Removing `DocumentsRegion` breaks accepted tests, which contradicts "unchanged". | Repaired. The retired and rewritten tests are listed, with reasons, in the section 1.2 rail row. |
| F3 | MAJOR | History and Back do not cover Office views. The cooldown can drop a navigate. | Repaired. History entries become `(mode, focus, officeView)`. A refused navigate becomes a chip. |
| F4 | MAJOR | Grants are in memory, so resume and open cards break after a restart. | Repaired. Inputs are re-confirmed through the picker with a hash match. Open output cards are closed and audited at start-up. A new destination is picked. |
| F5 | MAJOR | The destination order was undefined, and the grants signature broke the positional `flavor`. | Repaired. Destination order fixed (section 5.1). `check_shape(raw, flavor=None, *, suffixes=...)`. Multi-output deferred to O7. |
| F6 | MAJOR | An SMB canary on 127.0.0.1 is infeasible without elevation. | Repaired. System-wide diff of port 445 and 139 connections, plus a WebDAV high-port canary. NOT VERIFIED if WebClient is not running. |
| F7 | MAJOR | A disk quota needs admin rights. | Repaired. ENOSPC fault injection, labelled as simulation. Real disk-full is NOT VERIFIED. |
| F8 | MAJOR | LibreOffice exits not covered: crash reporting, update checks, `%TEMP%`. | Repaired. Profile disables them. Engine `TMP` goes to `<state>/lo-tmp`. Job process census. AC-O2-14 and AC-O2-18, G1 `%TEMP%` scan. |
| F9 | MAJOR | MuPDF parses untrusted PDFs inside the service process. | Repaired. `raster_worker.py` subprocess in a Job Object with memory and time limits. AC-O2-20, R13. |
| F10 | MAJOR | Sanitizer gaps: XXE/DTD, SVG href, attachedTemplate/subDocument, ppaction, OLE. | Repaired. Rules and a hardened parser are named in section 5. |
| F11 | MAJOR | Only `soffice.bin` was pinned, and checked only at service start. | Repaired. Full-tree manifest plus signer check. Executables, DLLs and python are checked at each launch. Spike S6, AC-O2-19, R14. |
| F12 | MAJOR | Cited 42 ms and 104 ms are not in the committed evidence. The 20-page targets were unmeasured. | Repaired. Committed values are cited. A correction is recorded in the programme plan section 2.1, with history kept. U12 and AC-O2-3 are marked provisional. Spike S7. |
| F13 | MAJOR | `OfficeKeep` conversation, per-controller hubs, WebView2 lifecycle and voice routing were not reconciled. | Repaired. One conversation store absorbs `OfficeKeep`. The sheet stays mounted offstage (AC-O2-17). Voice file and hub added. |
| F14 | MAJOR | Intent criterion was not measurable. No Brain-unavailable path. Free-form `missing`. | Repaired. 24 deterministic and 16 Brain requests with thresholds. Brain-unavailable row added. Closed enum. Document-specific system rule. |
| F15 | MAJOR | Conversion of the sanitized copy was undecided. | Repaired. Hyperlinks stay live. Each removed item is a warning on the approval card. This is the O2 default; the owner can change it at G0. |
| F16 | MINOR | `work/` collides with workbook copies. | Repaired. `<state>/workflows/<id>/`. |
| F17 | MINOR | The DOCX page count check is circular. B1 was mislabelled as fidelity. | Repaired. Labelled as consistency and engine regression. Fidelity against Word is NOT VERIFIED. |
| F18 | MINOR | Ctrl+B conflict. Focus inside WebView2. | Repaired. Ctrl+Shift+B and Ctrl+Shift+J. WebView focus behaviour stated. |
| F19 | MINOR | One branch cannot be checked out in two worktrees. Dart mirror ownership contradicted itself. | Repaired. Sub-branches per workstream. Mirror assigned to WS-A. |
| F20 | MINOR | Partial render claim. Queue priority and cancel. Idle definition. Cache key. "Clear previews" location. | Repaired in section 4.7 and section 5. |
| F21 | MINOR | Refinement 10 had no test. Chips dismissal untested. Colour lint too narrow. | Repaired. U16, U17 and the wider U10 lint. |
| F22 | MINOR | Wrong `pdf_reader.py` path. | Repaired. |
| F23 | MINOR | TOCTOU at write time. | Repaired for O2 (real-path re-check and exclusive create). The M1/M2 gap is reported to the owner (R16). |
| F24 | NOTE | S2 is answerable from source (texture host). | Applied. S2 narrowed to live confirmation. R5 lowered. |
| F25 | NOTE | `pymupdf>=1.24` against the measured 1.28.2. Start-up figure derived. 30 s ceiling loose. | Applied. Version pin noted. Derivation cited. ≤ 15 s warm-profile ceiling. |

Items the reviewer could not verify are carried into plan section 17:
- the original wording of the owner's 17 items;
- Brain-host prompt logging (spike S8, mitigated);
- the `ctypes` Job Object, `uno` under `-I`, and per-call against listener pixel parity (spikes S3, S1, S5).

## Round 2, at `78cfdacc` (plan rev 2)

**Verdict: REVISE (narrow).** No blockers.
- F1–F25: 16 CLOSED. 9 PARTIAL: F1, F2, F6, F9, F12, F16, F20 and F23, plus stale-text side effects.
- New findings: N1–N4 are major; N5–N11 are minor.
- The reviewer ran `python -I -c "import uri_office"` from the worktree root and got `ModuleNotFoundError`, which confirms N1.

| Id | Severity | Finding (short) | Disposition in rev 3 |
|---|---|---|---|
| N1 | MAJOR | `python -I -m uri_office.raster_worker` cannot import the package | Repaired. A standalone script, run by its absolute path under `-I`, imports only `pymupdf` and the standard library. |
| N2 | MAJOR | `run_plan` apply would run the workflow inside the global approvals lock | Repaired. Apply records the state and enqueues, then returns. Concurrency test added (section 5.1). |
| N3 | MAJOR | Offstage WebView2: hidden sheet could take keys, and its GPU use is unmeasured | Repaired. The controller is set invisible and focus moves to Flutter. New AC-O2-21. AC-O2-16 scope clarified. |
| N4 | MAJOR | Section 9.5 contradicted section 4.5 (names and titles sent to the Brain) | Repaired. Section 9.5 now matches, and a prompt test was added. |
| N5 | MINOR | Positional INSERT breaks after the new column. The ALTER is not idempotent. | Repaired. Named-column insert, and a `PRAGMA table_info` guard. |
| N6 | MINOR | Focus-aware history changes the existing test and rail Back | Repaired. Mode-only `history` kept. A separate Office view history. Rail Back unchanged. |
| N7 | MINOR | Stale passages: §1.2, §6.1 step 8, §6.3, §9.3, R10, "kept inert", U3/AC-O2-15, AC-O2-9 | Repaired. All aligned. `workflow.json` records the input path (not content) so resume can pre-fill the picker. |
| N8 | MINOR | An exclusive create is not atomic | Repaired. Temporary file, then fsync, then a rename that does not replace, with cleanup on failure. ENOSPC test. |
| N9 | MINOR | No lock for workflow subjects | Repaired. One lock per workflow, taken before the approvals lock. |
| N10 | MINOR | Census polling misses short connections; ambient SMB traffic | Repaired. Dedicated canary host `127.0.0.2`, census polled at ≤ 50 ms, canary servers primary. |
| N11 | MINOR | Programme plan correction note incomplete; "later run" unsupported | Repaired. Full table of committed against quoted values. Unsupported wording removed. |
| F11 note | — | The bundled Python's library and `share/` are checked only at service start | Stated in section 3. |

## Round 3

Recorded below after the check of the rev 3 diff.
