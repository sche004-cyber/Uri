"""URI Phase 2B: the Core <-> Supervisor integration boundary (candidate, uncommitted).

A third package. `uri_core` (frozen Phase 1) never imports it; `uri_supervisor` (Phase 2A) never imports it.
It composes the two at the client-side execution seam of the paired loop:

    User -> Intent Discovery -> confirmed intent (digest) -> approval (digest) -> signed ExecutionTicket
         -> [this package: verify the ticket, derive a bounded authorization, submit_task]
         -> uri_supervisor (admission, fenced attempt, contained executor, reconciliation)
         -> ExecutionReceipt (verified | failed | cancelled | execution_uncertain) -> Core settles.

Authority is CONSUMED here, never created: the only input that can start an executor is a ticket signed by the
server after an explicit, digest-bound user confirmation and approval. A successful executor stream is evidence,
never authorization; the supervisor's URI-observed postconditions decide `verified`.
"""
SCHEMA = "uri.phase2b.bridge.v1"
