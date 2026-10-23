# PH1-GATE-1 — test-only dependency `jsonschema` (plan and acceptance)

Owner decision OPEN-22 (2026-10-22): narrowly scoped dependency repair; determine whether `jsonschema` is needed for
testing or runtime, declare it in the appropriate manifest, run targeted tests, verify independently, avoid
unnecessary production dependencies. Finding source: P0 audit (`docs/audit/p0_20261021/P0_CLOSURE_20261022.md`
Addenda H, K on branch `audit/p0-comprehensive-20261021`). Baseline: canonical `8ff6186b`.

## Evidence

- Importers (`git grep` at `8ff6186b`): `tests/office/test_sheet_name_contract.py:8` and
  `tests/office/test_xb1_brain_status.py:9` only (Draft 2020-12 validation of `uri_office` Brain schemas). No runtime
  module imports it.
- Effect: in a materialised gate runtime (venv without `jsonschema`) whole-repository Phase 1 collection is
  interrupted at those two modules.
- Not this issue (recorded separately as PH1-GATE-2): `tests/office_u2/test_contract.py` and
  `tests/office_u2/test_workflow_resume.py` fail collection with "import file mismatch" (basename collisions with
  `tests/a2ui/test_contract.py` and the root `test_workflow_resume.py`).

## Change

New `requirements-test.txt` (test-only): `jsonschema>=4.18` (`Draft202012Validator` and the `referencing` back end).
`requirements.txt` is unchanged (it is also hashed by the frozen `uri_core/core/runtime_identity.py`, so changing it
would touch the frozen runtime identity). No code, test or tooling change.

## Acceptance criteria

- AC-1 `jsonschema` is declared only in a test manifest; `requirements.txt` and every runtime module are unchanged.
- AC-2 With `pip install -r requirements-test.txt`, the two Office modules collect and pass.
- AC-3 Whole-repository Phase 1 collection no longer stops on `jsonschema` (remaining errors are PH1-GATE-2 only).
- AC-4 `ws_frozen_check` clean; no protected path changes.

## Pre-review evidence

| Check | Result |
|---|---|
| Gate venv copy + `pip install -r requirements-test.txt` (jsonschema 4.26.0) | the two modules: 68 passed |
| Whole-repository `--collect-only` in that gate tree | 10,534 collected, 2 errors (PH1-GATE-2 only) |
| `tests/governance`, `tests/consolidation`, the two modules (system Python) | 217 passed, 25 skipped |
| `ws_frozen_check` | ok |
