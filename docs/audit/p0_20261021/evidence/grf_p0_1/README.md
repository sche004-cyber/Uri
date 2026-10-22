GRF-P0-1 qualification evidence (P0, 2026-10-22)

- FB1_subagent_6a10d9b7.txt: fallback review of the first candidate (superseded by driver r2).
- gates_base.log / gates_cand.log: first source-tree gates (2aa0141e vs 6a10d9b7).
- Driver r2 (primary): D:/uri-dev/lifecycle/GRF-P0-1-r2 (Codex ACCEPT on eb6bf6c8, GR-01 FIXED, VERIFIED).
- Differential gate trees (identical setup: venv D:/uri-dev/uri-o2i-live/runtime/.venv, evidence folder copied from
  C:/Users/cheta/Development/uri-ctl-gate/evidence): baseline D:/uri-dev/uri-grf-gate2-base (canonical 38a6d124,
  paired_reasoning af96445d) vs candidate D:/uri-dev/uri-grf-gate2 (eb6bf6c8, paired_reasoning 69a19588).
  diff2_*_summary.txt: phase2, authority, Phase 1 full (pytest --continue-on-collection-errors, PH1-GATE-1).
  phase1_nonpass_*.txt: non-pass ids; identical sets (51 each).
- Superseded first differential attempt (D:/uri-dev/grf-evidence/diff_*): candidate tree went stale when the
  source branch was merged with canonical (RECEIPT_IDENTITY refusal, as designed); not used.
