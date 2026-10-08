# Superseded: experimental intent workflow controller

Status: **SUPERSEDED for Phase 1. Kept as evidence. Not deleted.** Marked 2026-10-05 during the Phase 1 second review.

The canonical intent discovery path is `uri_core/core/intent_discovery.py`, inside the C5 `PairedCoordinator`, in the Phase 1 integration worktree (`C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent`).

What was salvaged from this candidate, as behaviour rather than code:

- the five-question ceiling;
- blocking a repeated question key or text;
- revision-bound acceptance;
- corrections that keep earlier answers and the question count;
- corrections that invalidate an earlier acceptance;
- each new request gets its own question allowance. The second review added a regression test for this last one: `test_a_new_request_after_a_stopped_one_gets_its_own_question_allowance`.

What was not salvaged, and why:

- **The `/desktop/intent` route, the separate cycle store and the Brain-only prompt contract.** Porting them would add a second controller and a second store next to C5.
- **Brain-dependent tests** (`reasoning_unavailable_preserves_user_correction`, `higher_reasoning_is_never_coerced`, and the scripted-Brain authority mutations). These are reference material for the C5 Brain interpreter/planner slice.
- **Cross-session evidence with stable provenance** (`ExistingContext`, `ConversationHistoryStore`). Context continuity is deferred, and Phase 1 C5 is session-first.

This directory is still uncommitted work in a Codex worktree. The user decides whether to archive or delete it.
