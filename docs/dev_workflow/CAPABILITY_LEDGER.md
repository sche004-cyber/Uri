# Capability ledger update — development lifecycle (2026-10-11)

Ladder as in `docs/integration/final_20261010/CAPABILITY_LEDGER.md`. Claimed only with COMPLETED_WITH_RESULT evidence.

| Capability | Highest level | Evidence | Not yet |
|---|---|---|---|
| `uri-development-lifecycle` driver (state, evidence binding, gates vs baseline, repair discipline, integration policy, receipts) | TESTED (DEVTEST, scripted processes) + live DEVTEST demonstration with separate Claude processes | `LIFECYCLE_QUALIFICATION.md` §1-2 | independent review of the skill (§3); integration into canonical (owner) |
| Independent reviewer launch (`claude_cli`) | TESTED live (DEVTEST) | demo 2 sessions R1/R2 | Windows PC run |
| `codex_cli` provider | IMPLEMENTED, NOT VERIFIED | — | Codex not installed |
| Status as A2UI surface | TESTED (validates against `uri_a2ui`) | `test_status_surface_is_valid_a2ui` | not wired into the Developer Console UI |
| GPU-gated gates via `gpu_lease` | TESTED (lease-unavailable path only) | `test_gpu_gate_without_lease_blocks` | lease-held path on the PC |
