"""URI Operational Intelligence (development candidate).

Connects the frozen Runtime v1 resident Brain (llama.cpp b11425 + Qwen3.6-35B-A3B) to URI through
adapters that sit OUTSIDE the frozen Phase 1 Core and the accepted Phase 2 packages:

  runtime_v1        discover / verify / start-or-attach / stop the single resident llama-server
  brain_client      streamed and structured inference with cancellation, deadlines and honest errors
  reasoning_policy  deterministic FAST / NORMAL / ESCALATE selection (freeze record section 4)
  triage            deterministic request triage (no model call)
  core_provider     ModelProvider adapter for Core's accepted `brain_composition` seam
  answer            conversation/answer channel with an action-claim guard
  planner           bounded multi-step plan proposals, validated deterministically
  task_ledger       durable task / step state with restart recovery
  harness_choice    provider options + recommendation; never switches silently
  orchestrator      one turn: triage -> Core authority or answer channel -> events
  events            UI event contract; simulator for the parallel UI session

Authority: URI Core decides every action. Nothing in this package approves, executes, claims or
settles a capability; it only proposes, answers language requests, and relays Core results.
Status: development candidate, not integrated, not production-active.
"""

__all__ = []
