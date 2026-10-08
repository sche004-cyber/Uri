# INT-ARN-1 desktop reference clarification seam: superseded for Phase 1 only

Status: **SUPERSEDED for the Phase 1 paired runtime. Still in use by the legacy desktop `/ask` on this branch. Not deleted.** Marked 2026-10-05 during the Phase 1 second review.

This seam still serves the legacy product on this branch, so it must not be removed before a separately authorized legacy cutover.

The Phase 1 paired runtime does not import or port this seam. It covers the same needs inside the canonical C5 path:

| INT-ARN-1 element | Phase 1 replacement |
|---|---|
| Durable per-user reference store | The signed intent record in the client's `sessions` store |
| Approval identity | The approval digest, which binds the Confirmed Intent Contract digest |
| Render deadline | The clarification contract rendered by C5 itself |
| Round-3 lesson ("replay after restart") and the round-4 lesson (a durable marker before dispatch) | The server-ledger duplicate-execution, stale-replay and already-executed guards in `uri_core/core/paired_coordinator.py`, with the adversarial tests in `test_c2_uncertain_adversarial.py` |

The second review found no INT-ARN-1 code or test that covers a Phase 1 behaviour still missing from the Phase 1 tree.
