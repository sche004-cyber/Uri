# GRF-P0-1 — runtime amendment and review follow-up (2026-10-22)

Addendum to `GRF_P0_1_PLAN_AND_ACCEPTANCE.md`, which stays byte-identical because it is the provenance witness
pinned by SHA-256 in `scripts/ws_frozen_check.py`.

## Finding (coordinator, during integration qualification)

The working system does not run canonical's source tree: it runs a runtime materialised from `e8e3b65` plus the
committed Phase 2 OQ overlay (`scripts/oi_materialize_test_runtime.py`), and the overlay supplies
`uri_core/core/paired_reasoning.py` (blob SHA-256 `af96445d...`, identical to canonical `2aa0141e`). An authorised
frozen change reaches that runtime only through `RUNTIME_AMENDMENTS` in `scripts/ws_materialized_verify.py` (precedent
FCV-05, `f808c0fa`). Candidate `6a10d9b7` changed the source file only, so the repair would not have reached the
running working system.

## Change (same owner exception OPEN-14, same file)

- `scripts/ws_materialized_verify.py`: `RUNTIME_AMENDMENTS["uri_core/core/paired_reasoning.py"]` with the overlay
  blob as the required before-hash; the after-bytes must equal `F.APPROVED[...]["sha256"]` (the generic FCV-05 rule).
- `scripts/oi_materialize_test_runtime.py`: the provenance record is copied into the runtime (`OI_PATHS`).
- `tests/phase2a/test_frozen_core.py`: the provenance record is a recognised runtime path (as for FCV-05).
- `tests/governance/test_materialized_output.py`: the amendment set test includes the new entry; a new test checks
  before = overlay blob, after = authorised blob, provenance pinned and copied.
- GR-01 (LOW, FB1): the `ws_frozen_check` decision label is now `OPEN-14/GRF-P0-1`, matching the plan.

No protected path changes beyond the already authorised `paired_reasoning.py` blob.
