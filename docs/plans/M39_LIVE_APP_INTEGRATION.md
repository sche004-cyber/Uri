# M39 Live-App Integration — design/diff, prepared not applied

- **Status:** design document only. No file under `uri_core/` or `uri_ui/` has been changed by this document or by the M39 implementation session. This is the "prepare it, don't apply it" artifact Chetan asked for (project timeline, 2026-09-28 10:29): "Finish the isolated build, tests, and PR-ready live-app integration path... Continue building and testing the isolated `uri_v1/office/` implementation as far as possible."
- **Why prepared as a document instead of a working diff:** this session's own auto-mode permission classifier denies, at the outcome level, any instruction to write to `uri_core/app/server.py`, `uri_core/core/file_store.py`, or `uri_ui/*`, independent of user approval (denial reason `[Production Deploy]`, reproduced twice). Rather than try to route around that guardrail, this document specifies the change precisely enough that a session with the needed permission — or Chetan directly — can apply it as a small, reviewable patch.
- **Governing rulings this reflects:** Chetan 2026-09-28 10:24 (INT-001 approved: connect the experimental M38 harness path to the real app, isolated, reversible, `URI_OFFICE_SEAM` default OFF, provisional, no frozen-file changes); Chetan 2026-09-28 10:26 (use the PR-based path; the PR must separate isolated code, minimal live-app changes, config/flag, rollback, tests/evidence, and frozen-file confirmation; do not merge or perform the live-app write); Chetan 2026-09-28 10:29 (don't run the Office flow on real files until M36/M37/M38 pass fresh independent audits; subscription-authenticated Claude Code only).
- **Plan basis:** `docs/plans/M39_OFFICE_DEMONSTRATOR_PLAN.md` §4.2 (Server wiring) and §4.3 (UI), read at commit `bc12aa1` (current head of the plan branch as merged into this branch).

## 1. Scope of this integration

Wire the already-built, already-tested `uri_v1/office/` backend package (this branch, R0 scope — see `docs/plans/M39_IMPLEMENTATION_REPORT.md`) into the real request path, behind a flag that defaults OFF. Nothing here changes M33.x-anchored files, S6, M31, or the orchestrator/Brain/capability registry. Confirmed by reading `scripts/m33_3_r_anchors.py`'s anchor list: none of `server.py`, `file_store.py`, or `uri_ui/*` appears in it — they are not anchored, matching the plan's own baseline table.

## 2. `uri_core/core/file_store.py` — accept the two Office file types

Current state (verified, this file, lines ~55-73): `ALLOWED_EXTENSIONS` is a `frozenset` of `.pdf .txt .md .csv .json .log .xlsx .xls .png .jpg .jpeg .tiff .bmp .webp .docx .pptx` — no `.py`, no `.xlsm`. Uploads are stored as `<uuid>{extension}` (lines ~230-231 `_write_content`/`save_upload`-equivalent path), so a script's `load_workbook("sales.xlsx")` cannot find the uploaded workbook by its original name today.

**Proposed diff (additive, two lines):**

**CORRECTION (M39 repair round 1):** the diff below was checked against the actual file and did not match its context -- the real file has an M19 comment block (`uri_core/core/file_store.py:72-75`, explaining why generated `.pptx` presentations are stored the same way as uploads) between `".docx"` and `".pptx"` that this diff's context omitted, so it would not apply verbatim with `patch`/`git apply`. Corrected below:

```diff
 ALLOWED_EXTENSIONS = frozenset(
     {
         ".pdf",
         ".txt",
         ".md",
         ".csv",
         ".json",
         ".log",
         ".xlsx",
         ".xls",
+        ".xlsm",
         ".png",
         ".jpg",
         ".jpeg",
         ".tiff",
         ".bmp",
         ".webp",
         ".docx",
         # M19: generated presentations (see generate_document.py) - a
         # document URI itself produces is stored the same way a user's
         # own upload is, so it is downloadable via the existing
         # GET /files/{id}/content path.
         ".pptx",
+        ".py",
     }
 )
```

The filename-preservation gap (UUID storage defeats a script's hard-coded `load_workbook("sales.xlsx")`) is **not** closed at the `FileStore` layer in this design — `FileStore` stays a flat, extension-validated blob store, unchanged in behavior otherwise. Instead, `uri_v1/office/binding.py`'s existing role-binding step (already built, already tested against fixture files with real names) is the layer that resolves a role (`script`/`workbook`) to a `FileStore` id *and* to the original filename the script expects, and the Office seam (§3) is what materializes the bound files into the Edge/harness workspace under their **original** names, not their storage UUIDs — `uri_v1/execution/workspace.py`'s `Workspace` already copies-in by a chosen name, so no `uri_core` change is needed for this half of the gap. This keeps the `FileStore` diff minimal (two extensions) and keeps the name-resolution logic inside the already-audited-boundary `uri_v1/office` package rather than spreading Office-specific knowledge into `uri_core`.

Existing `test_file_store.py` expectations that assert `.py`/`.xlsm` are rejected need updating to match (identify and flip those specific assertions; do not touch unrelated test cases in that file).

## 3. `uri_core/app/server.py` — the Office seam in `/ask`

Current state (verified, lines 1631-1700 of this file, function `ask`): two existing seams already follow the exact pattern this needs —
- **Approval resumption** (M32.1, lines ~1640-1665): guarded by `approval_resumption_enabled()`, wrapped in `try/except Exception: result = None; early_executed = False` so any internal failure falls straight through to the unchanged chain below it, never raises past the seam.
- **Lifecycle intent** (M33.1 Batch 4, lines ~1667-1703, corrected from an earlier ~1658-1691 estimate in this document that was off by roughly 10 lines): guarded by `lifecycle_intent_seam_enabled() and user_id is not None`, same fall-through-on-`None`-or-failure discipline, narrow closure bound to the request's authenticated `context`/`user_id`.

**CORRECTION (M39 repair round 1, from the internal audit's §4 review of this document): the ordering claim below was wrong and is left uncorrected in the diff sketch pending a real design decision, not silently fixed.** Between the lifecycle-intent block (ending ~1703) and where a "Brain chain" actually begins, there is a third existing block this document previously did not account for: the M30.7 workflow-continuation seam (~1705-1760), which resumes a pending `WorkflowExecutor` pause. Inserting the Office seam "after ~1700" as originally written lands it *after* that block, not immediately before the Brain chain as claimed. Two consequences, both open and NOT resolved by this document:
1. The M32.1 approval-resumption seam runs *first*, before Office ever sees the turn. A plain "yes"/"approve" typed to confirm an Office write-back could instead be claimed by an unrelated *pending* M32.1 approval, if one happens to be outstanding for the same user/session, since M32.1 has no way to know the "yes" was meant for Office.
2. The M30.7 workflow-continuation block also runs before the proposed Office seam and could similarly claim a turn meant for Office.

Resolving this needs an explicit ordering decision (e.g., Office checks first when an Office task is active for that user/session, or the existing seams are taught to ignore a turn that names an active Office task) -- a genuine design question for whoever applies this patch, not something to guess at here. **Proposed addition (ordering not yet finalized -- see correction above):** a third seam, `office_seam_enabled()`, inserted after the lifecycle-intent block and before the existing Brain chain, following the identical shape:

```python
# M39: Office flow seam ("make this script work with this spreadsheet").
# Isolated, default-controlled by URI_OFFICE_SEAM (see office_seam_enabled()),
# authenticated users only. Any internal failure, or a None interpretation
# (the request isn't an Office-flow turn), falls straight through to the
# unchanged Brain chain below exactly as if this block did not exist. Once
# the seam CLAIMS a turn (returns non-None), it never falls through after
# that point even if something inside subsequently raises -- it returns a
# typed error envelope instead, because the Brain narrating a success that
# did not happen is exactly the failure mode this milestone exists to avoid
# (M39 rule 4.4.4, "claims are claims").
if not early_executed:
    try:
        from uri_v1.office.bootstrap import office_seam_enabled

        if office_seam_enabled() and user_id is not None:
            from uri_v1.office.flow import handle_turn as office_handle_turn

            office_result = office_handle_turn(
                context=context,
                user_id=user_id,
                session_id=payload.session_id,
                text=payload.text,
                attachments=current_turn_attachments,
            )
            if office_result is not None:
                result = office_result
                early_executed = True
    except Exception:
        result = None
        early_executed = False
```

`office_seam_enabled()` (new, in `uri_v1/office/bootstrap.py`, already-built package): reads `os.environ.get("URI_OFFICE_SEAM", "0") == "1"` — **default OFF**.

**CORRECTION (M39 repair round 1):** this document previously claimed that default-off is "opposite polarity from the two existing seams (which default on with an opt-out flag)". That is false: both `approval_resumption_enabled()` (`uri_core/core/approval_resumption.py:39-40`, `os.environ.get(...) == "1"`) and `lifecycle_intent_seam_enabled()` (`uri_core/core/lifecycle_intent_interpreter.py:40-43`, same shape, its own docstring says "production default" leaves `/ask` "byte-identical") are themselves opt-in, default-OFF, `== "1"` checks. `URI_OFFICE_SEAM` defaulting off is the *same* polarity as the two precedents it is modeled on, not the opposite. (Also note: neither has actually been built yet -- `office_seam_enabled()` and `handle_turn()` do not exist in the repository as of this repair round; this whole section remains a design proposal, not a description of code that runs today.)

`office_handle_turn` is new glue in `uri_v1/office/flow.py` (not yet built — the implementation session built `OfficeSession`/`flow.py`'s programmatic API for the CLI; this is a thin adapter from the FastAPI request shape to that existing API) returning `None` for anything the deterministic request parser (`uri_v1/office/request.py`, already built and tested — Q-O1, 61/61 cases) does not recognize as an Office-flow turn, so ordinary chat is completely unaffected when the flag is on.

**CORRECTION (M39 repair round 1):** the claim that "everything is unaffected when the flag is off (the `office_seam_enabled()` check short-circuits before any import of `uri_v1.office.flow` executes)" is also false as the snippet in §3 is actually written: that snippet imports `uri_v1.office.bootstrap` (to reach `office_seam_enabled`) *before* it checks the flag, on every `/ask` call, flag on or off. `uri_v1/office/bootstrap.py` in turn imports `.flow` at module top, which imports the edge, memory and harness modules. So with the flag OFF, every `/ask` call still imports the entire `uri_v1.office` package tree (Python caches this after the first import, so it is not a *repeated* cost, but it is not "never imported" either). The `try/except Exception` around the block means a failure in that import cannot crash the request, so this is not a correctness bug, but "zero behavioral change" and "never imported" are not accurate as written, and whoever applies this patch should move the flag check to gate the import itself (`if office_seam_enabled(): from uri_v1.office.bootstrap import ...`) if a true zero-import-when-off property is required.

**Two supporting endpoints** (plan §4.2, not yet designed in diff form — left for a follow-up patch once the seam itself is reviewed, since they depend on how background-run polling is wired):
- `GET /office/runs/{run_id}` — status of a background Office run, scoped to `user_id`.
- `POST /office/folders`, `GET /office/folders` — register/list write-back-eligible folders as M36 authorized roots.

## 4. `uri_ui/` — minimal client changes

Per plan §4.3: render `response.files` (fallback to `response.file`, which the existing envelope shape already supports — no server response-shape change needed beyond what §3 already returns); poll `GET /office/runs/{id}` while `execution.office_run_id` is present and `RUNNING`. Flutter is not installed in this container, so these changes cannot be authored or tested here — plan §4.3 already designates this as a `B-UI` (User's machine) evidence step, unchanged by this document.

## 5. Configuration / feature flag

| Name | Default | Effect |
|---|---|---|
| `URI_OFFICE_SEAM` | unset / `"0"` (OFF) | `"1"` enables the `/ask` seam in §3. OFF means the seam never claims a turn; it does **not** mean `uri_v1.office` is never imported by `uri_core` at request time -- see the correction in §3 (the proposed snippet imports `uri_v1.office.bootstrap` before checking the flag). |

## 6. Rollback

- **Immediate, zero-deploy rollback:** unset `URI_OFFICE_SEAM` (or set it to `"0"`) in the environment. The seam is a request-time env check; no restart-order dependency, no data migration, no schema change.
- **Code rollback:** revert the single commit that adds the seam block to `server.py` and the two-line `ALLOWED_EXTENSIONS` addition to `file_store.py`. Both are strictly additive diffs (no existing line removed or altered), so the revert is a clean inverse patch with no conflict surface against unrelated `server.py`/`file_store.py` changes made in the meantime, as long as nothing else in those files is edited in the same region.
- **Data:** any file stored while `.py`/`.xlsm` were accepted remains valid and downloadable after rollback (`FileStore` does not delete on a code rollback); only new uploads of those types would start being rejected again.

## 7. Tests / evidence this integration needs (not yet run — B-UI/server-side, out of this container's scope until applied)

- `test_file_store.py`: updated accept/reject assertions for `.py`/`.xlsm`.
- New `tests/test_m39_server_seam.py` (server-side, FastAPI test client): seam OFF → `/ask` behavior byte-identical to current; seam ON + non-Office text → falls through to Brain unchanged; seam ON + Office-flow text → claims the turn, returns the typed envelope; seam ON + an internal exception forced via monkeypatch → falls through cleanly (mirrors how M32.1/M33.1's own fall-through is tested, if such a test exists for them — check before writing a new pattern).
- Flutter widget/integration tests for the UI changes in §4 (`B-UI`, User's machine).
- Confirmation step before merge: `python scripts/m33_3_r_anchors.py` and `python scripts/governance/uri_state_validator.py` both still clean after the patch (this document's proposed diff touches no anchored file, so this is expected to be a no-op change to both, but must be re-run against the actual applied patch, not assumed from this description).

## 8. Frozen-boundary confirmation

This document proposes changes to exactly two files: `uri_core/app/server.py` (additive seam block) and `uri_core/core/file_store.py` (two-entry extension-set addition), plus new, non-anchored test files. Neither file appears in `scripts/m33_3_r_anchors.py`'s frozen-anchor list (verified by reading that script directly, this session). No M33.x, S6, M31, or existing M36/M37/M38 file is touched by this proposal. `uri_v1/office/bootstrap.py` and `flow.py` need one small addition each (`office_seam_enabled()`, `handle_turn()` adapter) to support §3 — those are within the already-authorized `uri_v1/office` package, not a frozen boundary.

## 9. What this document does not do

It does not apply any of the above. No `uri_core` or `uri_ui` file has been modified. Applying it requires a session with permission to write those files (this session's classifier denies it) and a fresh review pass by Chetan or the coordinator against the actual diff once written, per his PR-based-path ruling.
