# PH1-GATE-2 — clean whole-repository test collection (AP-32 / OPEN-24)

Owner directive 2026-10-23 (priority 1): repair the clashing test file names so the complete suite collects cleanly;
narrow scope; independent review.

| Cause on canonical `c036a901` | Repair |
|---|---|
| `tests/office_u2/test_contract.py` and `tests/a2ui/test_contract.py` share a basename in non-package folders ("import file mismatch") | renamed to `tests/office_u2/test_office_contract.py` |
| `tests/office_u2/test_workflow_resume.py` and the root Phase 1 `test_workflow_resume.py` share a basename | renamed to `tests/office_u2/test_office_workflow_resume.py` (the root Phase 1 file is untouched; its node id is referenced by the Phase 1 outcome baseline) |
| Whole-repository collection also entered `docs/`: `docs/evidence/` keeps deliberately colliding `test_same.py` fixtures, and `docs/ui_v2/tools/test_*.py` are one-off patch scripts that **rewrite `uri_ui` source files when imported** (whole-repository collection on canonical silently edited `main_v2_preview.dart`, `voice_stage.dart` and `ui_v2_test.dart`) | root `conftest.py`: `collect_ignore_glob = ["docs/*"]` (`docs/` holds records, not tests) |

`tests/phase2a/test_frozen_core.py` lists the materialised runtime files; only the two renamed entries change.

Evidence (`D:/uri-dev/ph1g2` vs canonical checkout):
- whole-repository `pytest --collect-only`: canonical 12153 collected / 5 errors and the three `uri_ui` files modified; candidate 0 errors, working tree unchanged after collecting twice;
- `tests/office_u2 tests/a2ui test_workflow_resume.py`: canonical 2 collection errors; candidate 429 passed;
- `tests/phase2a/test_frozen_core.py`: the same 3 known failures on both (Phase 2A expects uncommitted work on its
  frozen base), with an identical stray-path list;
- `scripts/ws_frozen_check.py`: see the driver gates.
