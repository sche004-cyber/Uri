# Windows assistant recovery — bounded migration and qualification plan

Stage 3 proposal, following the Stage 1 root-cause audit and Stage 2 architecture
disposition with the same prefix. Implementation and release acceptance have
not occurred. The owner-controlled frozen-runtime boundary stops this plan
before its first production change.

1. Obtain authorization for the exact two-file runtime transition proposal,
   with independently reviewed provenance verification. Keep the existing
   accepted source checker, checkpoint and accepted Office/Assist refs intact.
2. Implement the smallest unprotected materialization-tool reconciliation in
   the isolated repair branch. Materialize a fresh real e8 runtime plus accepted
   overlay; copy exactly the approved canonical `server.py` and `fetch_url.py`
   blobs, not novel Core code. Retain before/after hashes, source SHA/tree,
   authority receipts and output manifest. Stop on any additional protected
   change. Independently audit the output verifier before relying on it.
3. Run original frozen, source-pin, C1/Phase 2, authority and regression gates
   against the actual materialized output. Required original checks cannot be
   silently weakened to accommodate approved transitions; any additional
   governance reconciliation must be separately explicit and independently
   reviewed. Preserve rejected experiments and command deviations.
4. Provision private test state and use the existing manifest/opt-in interface
   to launch the actual production Flutter app and integrated worker/server.
   Use separate loopback ports and existing installed dependencies. Verify
   launcher refusal of legacy roots/ports, exact source/build identity and
   model artifacts. Never connect to legacy port 8000.
5. Before model startup, inspect current services, GPU lease, memory and models.
   Use the existing guard and one resident model. No prior one-run override is
   reused as blanket authorization. If safe headroom remains unavailable, stop
   and report the environmental gate; do not kill OS/other agent services.
6. Execute the original accepted WS journeys first: ordinary answer, bounded
   multi-turn context, memory remember/recall/list, grounded intent discovery,
   clarification, confirmation, approve/deny, refusal, streaming, cancellation,
   worker/Brain recovery and stopped-Brain deterministic commands. Exercise
   actual UI controls and correlate stdio events, Core settlements and model
   usage. Prove both client memory isolation and approval digest binding.
7. Use resulting evidence to choose minimal OI/UI repairs, not parallel routing
   abstractions. Fix and review any reproducible defect in isolation, preserving
   Core authority. A necessary additional frozen edit stops for authorization.
8. Compare bounded Office schema repairs using deterministic original-failure
   proof and actual backend constrained decoding. Run Office/approval/atomic
   save/>500 tests, then the original live native workflows and the initially
   failing add-sheet plus 600-row request. Preserve all original failures; a
   different recovery request does not overwrite the original result.
9. For Edge and Assist, separate configuration from missing implementation.
   Any new adapter/inference bridge gets an isolated slice, frozen lifecycle
   requirements, a real target/model and security proof. Until implemented and
   live-qualified, expose unavailable status and report the unmet feature gate.
10. Run focused regressions, then the prescribed combined Python, Flutter,
    Office, security, lifecycle and governance portfolio against one exact
    committed candidate and its bound materialized runtime. Preserve tests and
    security assertions. Linux remains outside the Windows-only scope unless
    a mandatory governance requirement makes a specific gate applicable.
11. Measure UI request-to-visible-answer latency, model TTFT/decode, tokens,
    GPU per-engine activity, dedicated/non-local memory and process RAM. Report
    model speed separately from application latency; require correctness before
    calling a response useful.
12. Obtain a fresh independent exact-commit/tree audit of the complete repair,
    provenance, regression and actual Windows main-UI live results. Reviewer
    must not implement repairs. Record ACCEPT/REJECT/BLOCKED and all limitations.
    Repeat applicable gates after fixes; stop at persistent blocking defects.
13. Produce the engineering report and readiness decision. No canonical merge,
    push, deployment or cutover follows automatically. Preserve owner-approved
    integration policy; require its acceptance, authorization and receipt.

Rollback is abandonment of the new isolated candidate/runtime and graceful
cleanup of only owned test processes, lease and temporary state. Never reset
accepted refs, existing worktrees, original checkpoint, canonical or legacy
services. No production state migration is part of this plan.

## Required qualification distinctions

| Evidence | Required separation |
|---|---|
| Deterministic diagnostic and regression | May use existing fixtures/fakes; never reported as live Brain evidence |
| Main UI + integrated worker + paired Core + real Brain | Full intended profile, not the classic HTTP or Office-only harness |
| Memory/context | Persistent scoped store retrieval vs supplied conversation context |
| Edge | Pure routing/triage vs executed real inference and escalation |
| Assist | Snapshot/probe algorithm vs real permission-bound capture transport |
| Security | Source frozen PASS vs actual materialized output verification |
| Independent pre-audit | Investigation/plan finding, not final repair or release acceptance |
