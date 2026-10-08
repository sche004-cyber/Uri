# Needle + Granite pairing requirement

Date: 2026-09-29. Status: USER-REQUESTED ROLE SPLIT; PLANNING INPUT ONLY.

User instruction: "I want them to be used together with needle handling simple and direct tasks only".

This records the requested behavior and evidence-based constraints for the canonical planning process. It is not an accepted architecture, runnable configuration, qualification record, integration event, or milestone-state change. No production behavior was changed.

## Requested division of work

| Component | Intended responsibility |
|---|---|
| Needle 3 | Propose one registered tool and its explicit, grounded arguments for a direct request within its independently qualified envelope. |
| Granite `granite4:350m-h` | Bounded semantic work outside Needle's envelope: structured extraction and, if separately qualified, short transformations or drafts. Can propose a replacement after a rejected Needle proposal when still inside Granite's own qualified envelope. |
| Configured Brain | Interpretation, clarification, planning, context-dependent reasoning, and work beyond both Edge envelopes. The paired specialists do not replace the configured Brain. |
| URI runtime | Validate proposals, enforce qualification and configuration, ground arguments, authorize, obtain required approval, execute permitted tools, persist/audit, verify results, and feed results back into reasoning. |

"Used together" means complementary roles under URI coordination, not calling both models on every request. Do not use Needle as a universal front-door classifier, safety filter, plan reviewer, or mandatory gate before Granite.

## Needle envelope to qualify

A candidate direct task has one requested operation, one registered capability, and all required arguments supplied explicitly or bound by canonical session/source resolution. It needs no composition, document interpretation, generation, arithmetic, or recovery reasoning. An existing capability's permission/approval requirements still apply; calling a request simple grants no authority.

Examples to qualify: locating an explicitly named file, reading an explicitly named file or bound source, selecting a registered lookup with a literal argument. Examples are illustrative, not an exhaustive hard-coded phrase router or an assertion that a capability is available.

Exclude from the initial Needle envelope:

- Missing/ambiguous arguments, unresolved pronouns or previous-session references.
- Multiple requested operations, ordering/dependencies, correction/recovery instructions.
- Contrasts and negations requiring semantic disambiguation, such as "find it, don't read it".
- Quoted/document instructions, retrieved content, attachment interpretation, or prompt-injection handling.
- Text composition, rewriting, summarization, invoice/amount extraction, arithmetic, complex structured transformations.
- External sending/uploading, deletion/overwrite, security or privilege changes, unsupported modalities and capabilities.

These are proposed qualification exclusions, not implemented keyword rules. Eligibility must reuse accepted interpretation/binding and capability-envelope contracts, with runtime structural/authority checks. A model-produced "simple" flag or high confidence cannot authorize execution. If the existing path cannot establish eligibility safely without new semantic routing, that is an explicit Stage-2 design issue; do not quietly introduce task-specific Python reasoning.

## Proposal handling

1. Reuse the canonical request/task context and available capability registry. Resolve missing/stale/ambiguous arguments through the existing binding/clarification path.
2. Invoke Needle only inside its qualified direct-task envelope. Otherwise bypass Needle and choose Granite or the configured Brain according to their own envelopes and existing routing policy.
3. A Needle response must contain exactly one emitted registered tool call, satisfy its schema, and preserve the canonical requested operation and source-bound arguments. A schema-valid proposal is not proof of semantic correctness.
4. Suppressed calls, empty outputs, multiple calls, invented/modified arguments, mismatched operations, or transport errors cannot execute. Never promote `suppressed_calls` or substitute defaults for missing values. Preserve the reason for rejection.
5. Delegate unresolved bounded semantic work to Granite once when qualified for that work. Otherwise use the configured Brain or ask an essential clarification. Do not force Granite to solve missing information or work beyond its measured ability.
6. All proposals use the same runtime validate → authorize/approve → execute → verify path. Execution results return to canonical reasoning before any success claim. Never repeat a completed side effect while falling back or resuming.
7. Preserve configured `EDGE_ONLY`, Edge-off, provider selection, user isolation, and timeout behavior. In `EDGE_ONLY`, unresolved work returns the policy-defined clarification/unavailable outcome rather than silently using a capable/cloud provider. Edge-off bypasses both specialist models.

## Evidence and unresolved risks

The [fresh report](REPORT.md) and its raw records are Stage-1 inputs. They are exploratory evidence, not a qualification certificate:

- Needle matched 7/12 explicit supported tool requests. It matched several bare lookup/read/recipient requests but also truncated an explicitly supplied filename. "Direct" alone is therefore insufficient qualification.
- Needle mishandled negation/contrasts and used quoted instructions as a filename. Both must remain outside its initial envelope until independently qualified.
- Both models invented arguments and substituted available tools for unsupported requests; neither is a sole eligibility or safety authority.
- Granite matched 9/14 bounded extraction cases in schema-constrained JSON, including failures on injection, absent values, exact strings, and an action label. Its fallback envelope must also be measured rather than assumed.
- Granite was faster in the installed GPU configuration than CPU Needle. The pairing's benefit must be measured against Granite-only on the same workloads; it cannot be justified by assuming Needle always saves latency.

## Concrete acceptance evidence required before enabling

Freeze a fresh independently authored battery and thresholds before qualification. Do not select only the prompts Needle already passed. Include new filenames/recipients, diverse phrasing, Unicode, near-neighbor operations, and out-of-envelope requests.

- Positive direct tasks: exact emitted tool and exact grounded arguments, with omissions and truncations counted as failures.
- Boundary tasks: zero execution of invented/mismatched/unregistered calls, suppressed candidates, missing/ambiguous requests, duplicate side effects, and out-of-envelope work. Retain both raw model error rate and runtime containment rate.
- End-to-end paired behavior: Needle success, Needle rejection → Granite, bypass Needle → Granite, Granite rejection → configured Brain, clarification, provider failure, interruption/resume.
- Configuration: Edge-off and `EDGE_ONLY`; no provider substitution or authority changes; isolation between users/sessions.
- Compare paired, Granite-only, and the existing qualified baseline. Report accuracy, completion/escalation rates, false admissions, median/p95 total latency, resident memory, and model invocation counts. Count only actual model calls in specialist latency; distinguish proposals from verified completion.
- Canonical agent-loop and live user-path evidence: Brain discovery, availability, envelope choice, registered action contracts, execution result feedback, follow-up grounding, and truthful visible results. Component tests alone do not close the work.

## Canonical planning handoff

The current [M37 plan](../../../docs/plans/M37_EDGE_MINIMUM_PLAN.md) §2.2 explicitly excludes "local-model qualification" and production wiring; §1 restricts its qualified mechanisms to deterministic ones. Existing experimental results do not alter those records.

The user's role preference is established; do not request the same preference again. Under [AO-4](../../../ORCHESTRATION.md) and the [four-stage lifecycle](../../../docs/governance/URI_FOUR_STAGE_DEVELOPMENT_LIFECYCLE.md), Claude should plan/pre-audit the smallest separate qualification/integration scope from this requirement and the fresh evidence, with Antigravity coordinating implementation against the accepted plan. Do not retrofit an unreviewed model-backed mechanism into M37 or reopen frozen routing implicitly.

Stage sequence: targeted evidence/root-cause audit from the existing records → accepted canonical design → accepted migration/integration plan → implementation, independent review and live verification. Name any necessary integration boundary explicitly; do not invent a milestone identity, mark either model qualified, or advance governance state in this planning note.
