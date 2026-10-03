# Desktop recovery: narrow frozen-scope allowlist (record)

Status: AUTHORIZED AND IMPLEMENTED (candidate commit recorded in DESKTOP_RECOVERY_HANDOFF.md). Codex independent audit pending.

## Authority

- User (Chetan), 2026-10-01 18:10 UTC: authorized "the narrowly scoped desktop
  repair changes within `uri_core` and `uri_ui`, subject to the existing
  governance and frozen-file boundaries".
- User (Chetan), 2026-10-01 18:21 UTC, "APPROVED - Narrow Desktop Allowlist
  Amendment": authorizes the proposed allowlist solely for desktop recovery and
  mandatory Edge-first integration, with ten boundaries (frozen M36-M39 code,
  qualification oracles, anchors and security contracts preserved; exact files
  only, each recorded with its justification; no broad unfreeze; URI Core stays
  the orchestration authority; Edge tasks qualified with real tests; zero
  unnecessary Main Brain or harness calls on Edge-eligible tasks; escalation
  verified; end-to-end latency and actual model shown in the UI; regression,
  governance and frozen-boundary checks; Codex audit before acceptance).
- Precedent: the 2026-09-29 M39 allowlist entry in the M37 guard.

## Mechanism

The Edge route's code lives outside the frozen apps, in `uri_desktop_seams/`
(not in any guard's scope). Frozen files receive only a call-out hook, a
validation fix and telemetry fields. The three frozen-scope guards get one
exact-file allowlist (`DESKTOP_RECOVERY_ALLOWED_FILES`); no prefix entries, so
any other file under `uri_core`/`uri_ui` still fails the guards.

## Amended frozen-scope paths and justification

| Path | Why |
|---|---|
| `uri_core/app/server.py` | `/ask` call-out to the qualified Edge social route after approval resumption and lifecycle handling (S6 decides; any failure continues down the unchanged chain); per-turn model-call telemetry (all calls since turn start, not only the last) and turn duration in the response. |
| `uri_core/app/server.py` | Bounded LM Studio verification repair: discover model IDs from a loopback `/models` endpoint using the stored key, then probe and cache usable models. |
| `uri_core/core/response_validation.py` | Pure conversational turns (nothing dispatched) are no longer held to the capability-gap evidence-length cap, which rejected ordinary replies and made the UI show the decision rationale. Success-claim, credential, length and action-id checks unchanged. |
| `test_response_validation.py` | Root-level test for the validation change (outside guard scope; listed for completeness). |
| `uri_ui/lib/models/uri_turn.dart` | Carries model-call count and client-measured send-to-response time. |
| `uri_ui/lib/services/http_uri_client.dart` | Reads the new telemetry fields and times the `/ask` round trip. |
| `uri_ui/lib/widgets/turn_card.dart` | Caption shows the executing model, number of model calls, summed model time and send-to-reply time. |
| `uri_ui/test/chat_lifecycle_test.dart` | Caption text changed ("Model: ..." and "model N s"); one new test for multi-call and Send-to-reply time. |
| `tests/test_m36_memory_adversarial.py`, `tests/test_m37_edge_resolution.py`, `tests/test_m39_boundaries.py` | Exact-file exemption: a path passes only if it is listed in `desktop_recovery_allowlist.py` and its blob matches the pin; the module itself is blob-pinned in the M37 and M39 guards; the edited M36 guard is blob-pinned in both. |
| `tests/test_m37_frozen_guard_pin.py` | `GUARD_SHA256` re-pinned to the amended M37 guard. Tamper tests unchanged. |
| `uri_core/app/server.py` | Per-user Gmail registry construction and lifecycle refresh now use that user's OAuth token path. |
| `uri_ui/lib/services/http_uri_client.dart` | Failed `/ask` turns show the backend's `response.message` when no top-level error or Brain setup reason applies. |
| `test_gmail_user_scope.py` | Root-level regression proof for Gmail token-path isolation across registry creation and refresh; outside frozen guard scope. |
| `uri_ui/test/desktop_recovery_failure_reason_test.dart` | Mock HTTP regression cases for capability failure text and existing fallback priority. |
| `desktop_recovery_allowlist.py` | Re-pins the changed server and UI client blobs and pins the new UI test. |
| `tests/test_m37_edge_resolution.py` | Re-pins the desktop allowlist module blob. |
| `tests/test_m39_boundaries.py` | Re-pins the desktop allowlist module and both authorized frozen guard edits. |
| `tests/test_m37_frozen_guard_pin.py` | Re-pins the normalized M37 guard SHA-256. |
| `docs/plans/DESKTOP_RECOVERY_ALLOWLIST.md` | Records this bounded Gmail and failure-reason repair and its exact changed paths. |

Outside the guards' scope (not frozen, listed for completeness):
`desktop_recovery_allowlist.py` (the pinned list), `uri_desktop_seams/`
(the Edge route's code), `test_response_validation.py`,
`test_desktop_edge_seam.py`, `run_desktop_server.py`.

Verification (2026-10-02): guards pass on the amended tree; appending one line
to `uri_core/app/server.py` makes all three guards fail; adding an unlisted
file under `uri_core/core/` makes the M37 and M39 guards fail.

Changing any listed file later requires updating its pin in
`desktop_recovery_allowlist.py`, which changes that module's blob and so the
pins in the M37/M39 guards and the M37 guard hash: a visible, reviewable chain,
and a new User authorization for anything beyond this scope.

## 2026-10-02 Batch 1 Google onboarding

Authority: Chetan, 2026-10-02 04:01 UTC, authorized Google onboarding and
help with Google Drive requests. This batch changes onboarding only; Google
Workspace creation remains in Batch 2. Each frozen path below is pinned to its
working-tree blob in `desktop_recovery_allowlist.py` for Claude's review.

| Path | Justification under the 04:01 UTC authorization |
|---|---|
| `uri_core/app/server.py` | Return and recover a per-user Google sign-in URL, cancel a stuck flow, and report setup steps. |
| `uri_core/capabilities/gmail/capability.py` | Show the actionable Google failure reason to the user. |
| `uri_core/services/gmail_service.py` | Publish the loopback OAuth URL before waiting for consent, preserving state and PKCE. |
| `uri_core/services/google_errors.py` | Share safe classification of consent, token, and API failures. |
| `uri_core/tools/drive_search.py` | Show the actionable Google failure reason for existing Drive search. |
| `uri_core/tools/drive_upload.py` | Show the actionable Google failure reason for the existing approved Drive upload. |
| `uri_ui/lib/screens/connections/connections_screen.dart` | Expose Google setup and open sign-in initiated from the connection row. |
| `uri_ui/lib/screens/connections/google_setup_card.dart` | Show setup steps, help links, sign-in, reopen, cancel, and refresh actions. |
| `uri_ui/lib/services/app_state.dart` | Hold per-user setup and sign-in URL presentation state. |
| `uri_ui/lib/services/http_uri_client.dart` | Read setup, start sign-in, receive the URL, and cancel via HTTP. |
| `uri_ui/lib/services/mock_uri_client.dart` | Supply offline setup state for the existing UI flows. |
| `uri_ui/lib/services/uri_client.dart` | Define the setup/cancel client methods and sign-in URL outcome. |
| `uri_ui/test/google_setup_card_test.dart` | Verify setup presentation and opening the returned URL. |

The root-level `test_google_onboarding.py` is outside the frozen directories
and checks the Python handoff, cancellation, step classification, and errors.
The exact-file guard pins are updated only to authorize these paths.

## 2026-10-02 Batch 2 Google Workspace creation

Authority: Chetan, 2026-10-02 04:01 UTC, authorized Google Docs, Slides,
Forms, and other Google tools through Drive requests, with approval and
onboarding help. This batch adds creation for folder, sheet, doc, slides,
and form. The tool requires approval before any write and uses the user's
own Google token. A matching destination name is reported instead of silently
duplicated. The Batch 1 setup card already reports Sheets, Docs, Slides, and
Forms API status as unknown until their use can establish availability.

| Path | Justification under the 04:01 UTC authorization |
|---|---|
| `uri_core/tools/google_workspace_create.py` | Validate structured requests; find or create a destination folder; create a Google file and apply requested content only to that new file; report links and partial failures. |
| `uri_core/core/canonical_execution.py` | Forward only declared creation arguments from the Brain's proposal into the existing approval gate while preserving runtime-owned identity and session fields. |
| `uri_core/services/google_errors.py` | Classify disabled Workspace APIs and insufficient OAuth scopes with actionable, non-secret messages. |
| `uri_core/core/tool_schema.py` | Advertise the new tool's structured inputs to the canonical Brain's native tool schema. |
| `desktop_recovery_allowlist.py` | Pin the exact new and changed `uri_core` blobs. |
| `tests/test_m37_edge_resolution.py`, `tests/test_m39_boundaries.py`, `tests/test_m37_frozen_guard_pin.py` | Re-pin the allowlist and dependent frozen guards to the authorized content. |
| `uri_workspace/capabilities_registry.json` | Register the tool, explicit external-write effect, description, and user approval requirement for `/ask` discovery and dispatch; outside frozen guard scope. |
| `test_google_workspace_create.py` | Root-level mocked regression checks; outside frozen guard scope. |
| `test_m32_capability_effect_classification.py` | Root-level enumerator accepts an explicit, verified external-write effect from the descriptor because the M33.3 effect-map source is independently frozen; outside guard scope. |

## 2026-10-02 Batch 3 Google catalogue live availability, unread email summarization, and multi-turn context

Authority: Chetan, 2026-10-02 04:01 UTC and 05:48 UTC, authorized Google tools work in URI with live per-user OAuth availability, unread email body summarization, approval-gated drafts, and multi-turn context continuity.

| Path | Justification under the 04:01 / 05:48 UTC authorization |
|---|---|
| `uri_core/core/capability_feasibility.py` | Check live per-user OAuth token and credentials.json for Google tools (`gmail_search`, `gmail_find_draft`, `gmail_create_draft`, `drive_search`, `fetch_drive_spreadsheet`, `drive_upload`, `google_workspace_create`), overriding the static registry availability for authenticated users while preserving non-user ambient checks. |
| `uri_core/capabilities/gmail/capability.py` | Bound search messages queries (limit 1-20), fetch full message payloads to extract and bound plain-text bodies (`<=12,000` chars), skip downloading attachments, and auto-initialize Gmail client from token on demand. |
| `uri_core/app/server.py` | Supply user-scoped `CapabilityFeasibility` during `_build_user_context` and `refresh_user_external_lifecycle` to align orchestrator and gateway feasibility; safely record canonical execution turns via `_record_conversation_turn_safely` in `ask()`. |
| `uri_core/core/decision_engine.py` | Use user-scoped `capability_feasibility` from orchestrator or construct with principal `user_id` in `build_turn_state_and_directory`. |
| (reviewer note) | Claude reverted the implementer's orchestrator.py change (standing rule: orchestrator.py must never grow); failure text already reaches the history via response.message. |
| `test_google_batch3.py` | Root-level mock regression test suite covering live per-user availability, unread email body extraction without attachments, approval-gated drafting, and multi-turn context continuity; outside frozen guard scope. |

## 2026-10-02 Batch 4 Capability question conversational handling, unsupported routing correction, web research & presentation routing

Authority: Chetan, 2026-10-02 04:01 UTC and 05:48 UTC, authorized desktop recovery repair and asked Antigravity to implement capability question handling, truthful unsupported outcomes, web research routing, and PPT creation with tests.

| Path | Justification under the 04:01 / 05:48 UTC authorization |
|---|---|
| `uri_core/core/tool_schema.py` | Distinguish web_search (general web research without URL) from fetch_url (exact URL required) and update generate_document/google_workspace_create parameter descriptions. |
| `uri_core/core/decision_engine.py` | Add capability-question and web/PPT routing guidance to DECISION_CONTRACT_SYSTEM_PROMPT; the Brain remains responsible for classification. |
| `uri_core/core/canonical_execution.py` | Ensure _canonical_nonexecution_envelope only reports 'That capability is not connected right now.' when the Brain contract names a capability and mode is not unsupported; otherwise report the unsupported reason or generic fallback. |
| `uri_core/core/model_reasoning_adapter.py` | Add routing guidance in REASONING_SYSTEM_PROMPT for web research without URL (web_search), presentations (generate_document vs google_workspace_create), and capability inquiries. |
| `uri_workspace/capabilities_registry.json` | Update web/PPT routing descriptions and six Google tool entries to reflect live per-user connection availability; outside frozen guard scope. |
| `uri_core/app/server.py` | Fix the Gmail setup probe to call labels.list with supported arguments. |
| `test_google_onboarding.py` | Add a mocked successful Gmail setup-probe regression. |
| `test_capability_questions.py` | Root-level regression suite covering prompt and registry guidance, Brain-contract pass-through, non-execution messaging, and Google registry availability; outside frozen guard scope. |
| `test_capability_registry.py` | Update the real-registry assertion for fetch_drive_spreadsheet now that static availability is available and live per-user feasibility decides connection usability. |

## 2026-10-02 Batch 4 follow-up: conversational capability evidence

Authority: Chetan's direct implementer instruction, 2026-10-02, to ground canonical conversation drafts in currently usable per-user capabilities without editing orchestrator.py.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py` | Attach a bounded projection of usable current-user Capability Directory entries to canonical conversation response evidence only; preserve non-conversation envelopes and execution state. |
| `uri_core/core/response_drafting.py` | Tell the drafting Brain how to use the conversation envelope's capability evidence; its existing payload already forwards outcome.response. |
| `test_capability_questions.py` | Mock the per-user directory and drafting provider to prove usable-only, bounded conversation evidence, validation acceptance, and unchanged non-conversation response. |

## 2026-10-02 Gmail multi-step read prefix repair

Authority: Chetan's direct implementer instruction, 2026-10-02, for canonical
Gmail unread-message summarization and safe multi-step execution. Claude
re-pins frozen-file hashes after review.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py` | Independently gate and execute only the ready read-only prefix of a multi-action proposal when later steps lack evidence-derived inputs; carry evidence and deferred-action markers to drafting. |
| `uri_core/core/decision_engine.py` | Guide the Brain to search unread inbox mail with a concrete Gmail query and use recent conversation for follow-ups. |
| `uri_core/capabilities/gmail/capability.py` | Advertise unread inbox queries and bounded body evidence in the Gmail search action description. |
| `uri_core/core/response_drafting.py` | Guide the Brain to summarize actual partial-read evidence, identify messages for follow-up, and describe deferred work accurately. |
| `test_gmail_multi_step.py` | Root-level mocked regression for read prefix, evidence, missing inputs, approval, and follow-up context; outside frozen guard scope. |

## 2026-10-02 Research-to-PPT implementation

Authority: Chetan's direct implementer instruction in-thread, 2026-10-02.
Claude re-pins frozen-file hashes after independent review. No milestone status
or release checkpoint is claimed by this implementation.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py` | Execute one independently gated legacy research read from a multi-action proposal and defer its suffix; pass recent conversation to a later document generation turn. |
| `uri_core/core/tool_schema.py` | Expose Brain-proposed PPTX theme and licensed-image controls. |
| `uri_core/core/model_reasoning_adapter.py`, `uri_core/core/decision_engine.py` | Guide the Brain to research, offer three options, and await the user's choice before creating the deck. |
| `uri_core/core/response_drafting.py` | Guide the drafting Brain to report research evidence and deferred creation accurately. |
| `uri_core/tools/generate_document.py` | Pass research context and selected design controls to the existing Brain composer, PPTX renderer, and FileStore. |
| `uri_core/services/office_document_writer.py` | Render themed PPTX slides and optional embedded CC images with a credits slide, degrading to a deck without photos when retrieval fails. |
| `test_ppt_research_chain.py` | Root-level mocked regression for read prefix, deferred creation, schema, styling, credits, and image failure. |

## 2026-10-02 Research-to-PPT live repair

Authority: Chetan's direct implementer instruction following the two-turn live
`/ask` test at `8f7b7d2`. Claude re-pins frozen-file hashes after review.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py` | Give the read-prefix drafting Brain bounded, current-user capability evidence alongside the deferred steps and successful research result. |
| `uri_core/core/response_drafting.py` | Direct the Brain to offer three researched choices and accurately say it can build the selected PPTX with photos when the available capability evidence supports it. |
| `uri_core/core/tool_schema.py` | Expose Brain-selected output format and document topic/title as structured document inputs. |
| `uri_core/core/decision_engine.py`, `uri_core/core/model_reasoning_adapter.py` | Instruct the Brain to carry the original presentation topic, format, design, and photo request through a short choice follow-up using recent conversation. |
| `uri_core/tools/generate_document.py` | Use structured format and title for composition and filename; derive bounded image queries from the Brain's deck topic and slide titles when photos were requested without queries. |
| `test_ppt_research_chain.py` | Mocked regressions for read-prefix evidence and validation, structured follow-up PPTX and photos, format fallback, and DOCX preservation; outside frozen guard scope. |

## 2026-10-02 Foundational web search catalogue repair

Authority: Chetan's direct implementer instruction in-thread, 2026-10-02.
Claude re-pins frozen-file hashes after independent review. No milestone status
or release checkpoint is claimed here.

| Path | Justification |
|---|---|
| `uri_core/core/capability_registry.py` | Carry the registry entry's optional boolean `foundational` value into its descriptor. |
| `uri_core/core/capability_feasibility.py` | Preserve that value in the feasibility snapshot consumed by the directory. |
| `uri_workspace/capabilities_registry.json` | Declare `web_search` foundational so topic-only information requests expose it to the Brain. Memory capabilities retain their existing fallback. No other capability was promoted. |
| `test_preselection_foundational.py` | Root-level offline regressions for registry-to-directory propagation, web and memory visibility, and non-foundational lexical filtering; outside frozen guard scope. |

Adjacent reachability check: with the real directory and top-five preselection,
`make a presentation on X` and `make a presentation on the solar system` omit
`generate_document`, although its registry description says it creates
presentations. The terms `presentation` and `make` do not give it a top-five
discriminating match. `summarise my unread emails` puts the multi-action
`Gmail` capability first, exposing `search_messages`. This repair does not
change presentation routing or promote another capability to foundational;
the presentation gap needs a separate review of the general preselection
behavior, without a phrase-specific keyword classifier.

## 2026-10-02 Openverse PPTX image retrieval repair

Authority: Chetan's direct implementer instruction, 2026-10-02, following a
live PPTX run with zero added images. Claude re-pins frozen-file hashes after
independent review. No milestone status or release checkpoint is claimed.

| Path | Justification |
|---|---|
| `uri_core/services/office_document_writer.py` | Prefer Openverse thumbnail downloads, validate HTTPS redirect chains and image bytes, try up to five candidates per query, and return a bounded retrieval failure reason. |
| `uri_core/tools/generate_document.py` | Pass the retrieval reason into a truthful plain-language image note when no images were added. |
| `test_ppt_research_chain.py` | Mocked regressions for thumbnails, redirect policy, size cap, multiple credited slides, fallback, and image-note reasons; no network. |

## 2026-10-02 Openverse PPTX query recovery

Authority: Chetan's direct implementer instruction following a live deck with
zero images, despite successful generic Openverse searches. This bounded repair
does not claim milestone verification or release. Claude re-pins frozen-file
hashes after independent review.

| Path | Justification |
|---|---|
| `uri_core/core/tool_schema.py` | Ask the Brain for short generic visual subjects, one per content slide, without institution names. |
| `uri_core/tools/generate_document.py` | Derive generic slide queries when absent, retry one broader query per empty result, cap lookups and images, and report tried queries. |
| `test_ppt_research_chain.py` | Mocked regressions for Brain-provided and derived queries, broader retry, and lookup/image caps; outside frozen guard scope. |

## 2026-10-02 INT-ARN-1 Slice C (canonical /ask wiring and route guards)

Authority: Chetan, 2026-10-02 08:46 UTC (INT-ARN-1), 09:02, 09:24 and 09:32 UTC (exact files). Plan: docs/plans/INT_ARN_1_PLAN.md (accepted with amendments at f212b0d).

| Path | Justification |
|---|---|
| `uri_core/core/multi_action_dispatch.py` | Per-action `reference_bindings` transport to `MultiActionExecutor` (single and chain). |
| `uri_core/core/approval_resumption.py` | Pre-consumption binding recheck for natural-language approval; shared resume-by-action-ID entry for `/approve` registered records. |
| `uri_core/core/native_tool_loop.py` | Both `_execute_canonical` sites fail closed for pending rounds / slot-bearing proposals. |
| `uri_core/core/approval_store.py` | `ProposedAction` binding identities + `requires_reference_binding`; `propose()`/`_load()`. |
| `uri_core/core/approval_gate.py` | Pre-consumption binding recheck for legacy-tool `/approve`; registered records never legacy-dispatched. |
| `uri_core/core/decision_engine.py`, `canonical_execution.py`, `uri_core/app/server.py` | Optional `reference_slots`, clarification intake/stream intercept, pre-dispatch hook, central fail-closed exclusions, clarification wire projection. |

## 2026-10-02 INT-ARN-1 Slice D (Flutter clarification card)

Authority: Chetan, 2026-10-02 (INT-ARN-1 "yes to all" for `ask_uri_screen.dart`, `clarification_card.dart`, `clarification.dart`; 14:37 UTC "OK" for `status_pill.dart`). Drafted by Antigravity (Codex quota exhausted), reviewed and repaired by Claude.

| Path | Justification |
|---|---|
| `uri_ui/lib/models/uri_turn.dart` | `TurnStage.awaitingClarification`, clarification / tentative binding / retry fields, `copyWith(userText)`, history decode. |
| `uri_ui/lib/models/clarification.dart` | Tolerant decode of the backend wire projection, `expires_at`, `toJson`, `ClarificationResponsePayload.fromJson`. |
| `uri_ui/lib/services/uri_client.dart`, `http_uri_client.dart`, `mock_uri_client.dart` | `submitClarificationResponse` sends the typed `clarification_response` through `/ask`; decode `clarification`; malformed card fails closed as a visible failed turn. |
| `uri_ui/lib/services/app_state.dart` | Duplicate-submit guard; answer appended as its own turn; stale/rejected answer keeps the card with the server's retry text. |
| `uri_ui/lib/widgets/turn_card.dart`, `uri_ui/lib/screens/ask/ask_uri_screen.dart` | Embed the existing `ClarificationCard`; only the latest turn's card is interactive. |
| `uri_ui/lib/widgets/clarification_card.dart` | Submit lock, read-only history, retry banner, five-option presentation cap, Semantics labels. |
| `uri_ui/lib/widgets/status_pill.dart` | One label for the new turn stage (exhaustive switch). |
| `uri_ui/test/int_arn_1_clarification_test.dart` | 14 widget/state/HTTP-contract tests. |

## 2026-10-02 INT-ARN-1 audit repair (Codex audit REJECT findings 1-5)

Authority: Chetan's INT-ARN-1 approvals (same exact files as Slices C and D). Implemented by Codex; reviewed, regression-compared and re-pinned by Claude.

| Path | Justification |
|---|---|
| `uri_core/core/decision_engine.py` | One consistent contract (nine required keys, optional `reference_slots`); real action argument names exposed when the flag is on. |
| `uri_core/app/server.py` | Flagged first `/ask/stream` turns go through `/ask`; rejected/unavailable answers rebuild a fresh round or block clearly; history projection and tentative binding. |
| `uri_core/core/canonical_execution.py` | Bounded Brain render draft validated by the frozen renderer (template fallback); tentative binding projection. |
| `uri_ui/lib/services/*uri_client.dart`, `app_state.dart`, `screens/ask/ask_uri_screen.dart`, `widgets/clarification_card.dart` | Old card locks after a dead round; typed "Change" request through `/ask`. |

## 2026-10-02 INT-ARN-1 re-audit repair (redo lifecycle, render deadline, flag-OFF prompt)

Authority: Chetan's INT-ARN-1 approvals (same approved files). Implemented by Codex; reviewed, regression-compared and re-pinned by Claude.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py` | Record APPLIED binding state after a bound action actually runs; render draft gets a real deadline with template fallback. |
| `uri_core/core/approval_resumption.py` | Approved bound dispatches record APPLIED state; a recording failure keeps the true execution result and only blocks later Change. |
| `uri_core/app/server.py` | Change after execution goes through frozen `authorize_redo` and stops before any repeat dispatch. |
| `uri_core/core/decision_engine.py` | Original "exactly these keys" contract when the flag is off; flag read through `reference_clarification_enabled()`. |

## 2026-10-02 INT-ARN-1 round-3 repair (durable execution marker)

Authority: Chetan's INT-ARN-1 approvals. Implemented by Codex; reviewed, regression-compared and re-pinned by Claude.

| Path | Justification |
|---|---|
| `uri_core/core/canonical_execution.py`, `approval_resumption.py`, `uri_core/app/server.py` | Durable per-user "execution pending/unknown" marker written before bound dispatch; APPLIED after success; Change fails closed on pending/unknown, including after restart; render slot released if the worker fails to start. |

## 2026-10-03 INT-ARN-1 live fix (Brain unavailable message, prompt size)

| Path | Justification |
|---|---|
| `uri_core/core/decision_engine.py` | Flag-ON decision prompt drops the duplicate mode glossary so it is no larger than flag-OFF plus slot instructions. |
| `uri_core/core/canonical_execution.py` | With the flag on, an unreachable Brain reports that truthfully (not a reference question) and never executes. |

## 2026-10-03 uploaded-file use and local drafting latency repair

Authority: Chetan's instruction for the two everyday-use defects on `experimental/desktop-recovery-repair`. Claude owns blob pin updates.

| Path | Justification |
|---|---|
| `uri_core/core/decision_engine.py` | Guide the Brain to read uploaded content before answering and request a filename when multiple files are plausible. |
| `uri_core/core/response_drafting.py` | Keep outcome, evidence, and authority rules while shortening repeated drafting instructions; ground file answers in extracted text and report truncation or unreadability honestly. |

## 2026-10-03 desktop Ollama large-model residency repair

Authority: Chetan's direct desktop change instruction on `experimental/desktop-recovery-repair`. The frozen path below requires User frozen-scope approval before commit; this row records the proposed exception and does not grant it.

| Path | Justification |
|---|---|
| `uri_core/core/model_providers/ollama_provider.py` | Wrap both Ollama completion paths with the desktop residency guard so large local Brain calls unload other idle large models before inference. |
