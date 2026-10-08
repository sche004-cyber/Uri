# Intent workflow candidate — implementation and evidence

2026-10-04. Provisional, uncommitted development work. No independent VERIFIED status, milestone completion, production adoption, or release claim.

Candidate: `C:\Users\cheta\.codex\worktrees\intent-discovery\_V1`, detached HEAD at base `62d564cf9d2fa25e5a9860d20dcc7070b112badb`. Installed integration authority remains `C:\Users\cheta\Development\uri-m37-m39-integration\docs\governance\URI_STATE.yaml`; this candidate does not supersede it.

## Reuse and actual changes

The [reuse map and gaps](../research/INTENT_WORKFLOW_ROOT_CAUSE_AUDIT.md), [bounded design](../architecture/INTENT_WORKFLOW_CANONICAL_ARCHITECTURE.md), and [migration plan](INTENT_WORKFLOW_MIGRATION_PLAN.md) record the first three lifecycle stages. They are candidate documents, not independent plan approval.

Existing ModelReasoningGateway supplies interpretation. Existing ConversationHistoryStore supplies bounded current/prior-session transcripts with stable source references. Existing GraphifyIndex, graph queries, TurnState and ContextBuilder supply their existing projections. URI-Memory retrieval projects grounded candidates through existing RAR; ARN.1 provides not-found recovery bookkeeping. Optional Context Bridge retrieval verifies capsule freshness before extracting source-bound evidence. None of these components was rewritten.

New glue is under `experimental/intent_workflow/`: authenticated preparation routes, persisted user-owned cycles, strict proposal validation, five-question ceiling, duplicate key/text protection, revision-bound acceptance, correction continuity, and source-backed preparation packages. Corrections retain answers and question counts, invalidate acceptance, and clear stale interpretation if reasoning becomes unavailable. A new unrelated task gets a new cycle.

The Flutter block reuses the existing provisional Workspace panel and approved inline clarification-card structure. It presents the audit fields, Accept/Correct, installed executor choices plus URI, and denial. It is disabled unless `URI_INTENT_PREPARATION=true`. It does not replace normal Ask routing or rebuild Console.

The only changes to copied dependencies are `uri_ui/lib/services/desktop_harness_test_client.dart` and `uri_ui/lib/widgets/desktop_harness_test.dart`. [114-file comparison manifest](../evidence/intent_workflow/dependency_provenance.json) separates copied provisional work from this task's changes. Its timestamps describe a post-copy comparison, not a historical attestation. Source candidate and original user checkout were preserved.

## Evidence actually obtained

| Check | Result and limits |
|---|---|
| New Python protocol/interface tests | 17 passing; scripted interpretation plus real component interfaces and isolated Core composition/authentication |
| Copied candidate Python regressions | 24 passing; fake harness fixtures and disposable state, no live provider |
| Flutter intent/harness/auth tests | 10 passing, including 2 new Intent Preparation tests |
| Focused Flutter analysis | No issues found in the three affected UI/service files |
| Protected-path comparison | No changes to `uri_core`, `uri_v1/execution`, `uri_v1/edge`, `uri_v1/turn`, or `uri_v1/memory` relative to base |
| Whitespace check | `git diff --check` passes |

Python command: `python -m pytest tests/test_intent_workflow.py tests/test_desktop_harness_auth.py tests/test_desktop_harness_integration.py tests/test_harness_desktop_completion.py -q` — 41 passed. Three dependency/copied-code deprecation warnings remain. An initial composition smoke-test assertion used the wrong expected gateway error; corrected to the actual `model_not_configured` result and reran successfully.

Flutter command: `flutter test --no-pub test/intent_preparation_test.dart test/desktop_harness_test.dart test/desktop_harness_auth_test.dart` — 10 passed. Dependencies resolved from the existing offline cache; no Flutter upgrade performed.

[HTTP demonstration trace](../evidence/intent_workflow/scripted_http_demo.json): request → one clarification → answer → direct correction → Accept → Codex preference → deny. The cycle and count persist. No intent run route exists (404). This is a scripted Brain control-flow demonstration, not real semantic understanding or a live desktop/provider demonstration. Mock receipt fields in copied harness tests are fixture outcomes, not this candidate's independent verification.

The real Core composition smoke test uses disposable signup/authentication, rejects anonymous access, and reports unavailable reasoning with Brain calls disabled. It sends no inference request.

## Remaining links and measurement limits

Intent preparation and executor preference work at the protocol/UI-component level. Packages explicitly retain `workspace=null`, empty permissions and `execution_authorized=false` until a governed workspace/profile approval connection exists. They are not execution-ready. Assumptions remain separate from confirmed intent; model-derived constraints still require human assessment in the audit.

General dispatch, permission-profile admission, observation-policy changes, native-session clarification transport, canonical Brain execution-result feedback, and live UI journeys are not implemented/qualified by this slice. Existing fixed repair approvals and receipts remain a separate task and are not misused as general execution evidence. Semantic paraphrases of answered questions are constrained by the model protocol; runtime duplicate protection alone cannot prove semantic non-repetition.

Prior-session retrieval is bounded, not an exhaustive cross-session search. ARN.1 is not a memory store; the candidate currently projects recovery bookkeeping and does not claim a durable cross-turn ARN search-budget integration. The launcher uses disposable candidate state, not installed production accounts/history. Context Bridge remains an optional experiment. No general-intent Edge specialist was selected or qualified.

Question counts, interpretation/context duration, and time-to-accept are recorded per cycle. Interpretation correctness, necessary-versus-unnecessary questions, reference accuracy, package sufficiency, avoidable rework, actual Edge latency, live execution time and provider consumption require real trials. Scripted timings do not establish these qualities. No subscription savings claim is made.

## Concrete approval gates and next demonstration

1. **Brain-only live candidate trial:** separately approve invoking the existing configured URI reasoning router for three representative requests (simple, ambiguous prior decision, complex clear), up to 20 inference calls total. Use disposable state and explicitly supplied test context; no installs, account/configuration changes, protected-source edits, external execution harness, or observed-profile changes. Exercise the candidate Flutter panel and collect actual interpretation, question, provenance and latency evidence. Stop on unavailable reasoning or exhausted budget. Existing local/Edge routing may be used as configured; no silent provider substitution. This is the next recommended approval.
2. **Observed harness pilot:** requires a separate named task/workspace/permissions/provider authorization and a scoped amendment to the source candidate's `docs/plans/HARNESS_CONNECTIONS_CONSOLE_FROZEN_EXTENSION_PROPOSAL.md`. Item 3 currently requires ignoring ambient rules/hooks/plugins and an enforceable profile; its prerequisite requires repaired/qualified deny-read containment or a separately approved and qualified OS alternative. The User's latest prompt explicitly says conceptual observed execution does not override those boundaries. Any permitted native plugins, observational reporting, critical-stop policy, visibility limits and session answer channel must be stated in that amendment. Preserve the contained path.
3. **Frozen/production integration:** independent review and the corresponding protected-source/adoption authorization are required before implementing general capsule/Edge contracts, verification changes, S13/INT adoption or production routing. Release remains with the governing release authority. No governance file or milestone tracker was changed here.

Manual candidate activation after the applicable approval: run `python scripts/run_intent_workflow_candidate.py --enable-intent-preparation --enable-brain-requests` in this worktree, optionally supply the existing experiment directory with `--bridge-dir`, and start the copied Flutter candidate pointed at loopback port 8022 with `--dart-define=URI_INTENT_PREPARATION=true`. Reuse the copied candidate's authentication and launch instructions. Intent acceptance never starts a harness. Default flags stay off; rollback is simply not using this composition.

The complete requested workflow remains unfinished pending these gates. This report is implementation evidence for review, not a declaration that URI is integrated end to end.
