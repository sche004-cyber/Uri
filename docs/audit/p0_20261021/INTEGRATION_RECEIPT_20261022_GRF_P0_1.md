# Integration receipt — GRF-P0-1 (2026-10-22)

Authority: owner decisions OPEN-14 (frozen-Core exception, DEC-096 item 4) and OPEN-20 (conditional integration once
all mandatory gates are met, DEC-098). Order after the Milestone Manager integration per the owner's decision relayed
by the Milestone Manager session (canonical `375b6ea9` first). Push approved through the session's permission prompt;
no force-push; no security control changed.

| Item | Value |
|---|---|
| Canonical before | `375b6ea96f9a22053f42bd27ded7c716b4ddd8ac` (Milestone Manager, `ls-remote` verified before the push) |
| Canonical after | `8ff6186b7c42bc4e8f997ba38b4581dc9fc5a20e` (fast-forward; pushed 2026-10-22 ~13:35Z; `ls-remote` 13:35:16Z) |
| Reviewed candidate | `eb6bf6c851c622683e333cce35e09d7ab17e7a21` (branch `repair/grf-p0-1-graphify-paired-hint-20261022`) |
| Integration-specific change | `8ff6186b` = `--no-ff` merge of canonical `375b6ea9` into `eb6bf6c8`; no conflicts; the 9 GRF files are byte-identical to `eb6bf6c8`; diff vs `375b6ea9` = exactly those 9 files |
| Files | `uri_core/core/paired_reasoning.py` (the only protected path, exception OPEN-14), `scripts/ws_frozen_check.py`, `scripts/ws_materialized_verify.py`, `scripts/oi_materialize_test_runtime.py`, `tests/graphify/test_grf_p0_1_paired_hint.py`, `tests/governance/test_materialized_output.py`, `tests/phase2a/test_frozen_core.py`, `docs/graphify/GRF_P0_1_PLAN_AND_ACCEPTANCE.md`, `docs/graphify/GRF_P0_1_RUNTIME_AMENDMENT.md` |
| Independent review | driver `D:/uri-dev/lifecycle/GRF-P0-1-r2`, round 1, `codex_cli`, independent ("separate process, fresh session, clean checkout, integrity verified"), ACCEPT, no findings, GR-01 FIXED; QUALIFICATION ok; VERIFIED, `evidence_ok_for_candidate: true` (history: fallback FB1 ACCEPT WITH FINDINGS on `6a10d9b7`) |
| Mandatory gates | Phase 1/2 differential on materialised gate trees, canonical `38a6d124` vs `eb6bf6c8`: phase2 484/2 both, authority 134 both (FLAKY-1 setup error seen once per tree), Phase 1 full 27F/10,357P/24E both with identical non-pass ids (PH1-GATE-1 workaround `--continue-on-collection-errors` applied to both) — `evidence/grf_p0_1/` |
| Gates on the exact merge `8ff6186b` | Graphify, governance, decision-engine, turn-state and Milestone Manager tests: 682 passed, 25 skipped, 0 failed (`D:/uri-dev/grf-evidence/gates_8ff6186b.log`) |
| Frozen integrity | `ws_frozen_check` ok on `8ff6186b` (merge worktree and clean canonical checkout `D:/uri-dev/uri-canon-8ff6186b`): no unapproved protected change, no unapproved Phase 1 drift; exact-blob exception `69a19588...` |
| Runtime reach | a runtime materialised from the candidate carries `paired_reasoning.py` `69a19588...` (amendment from overlay blob `af96445d...`), recorded in its `OI_MATERIALIZATION_RECEIPT.json` |
| NOT VERIFIED | a live paired turn with the real Brain through the Windows UI after this change |
| Rollback | `git revert -m 2 8ff6186b` as a new commit (parent 1 is the GRF branch `eb6bf6c8`, parent 2 is canonical `375b6ea9`; `-m 2` restores the `375b6ea9` tree; no force-push); a runtime materialised from that tree keeps the overlay blob |
