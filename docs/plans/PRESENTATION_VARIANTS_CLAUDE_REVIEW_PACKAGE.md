# Presentation workflow repair: independent Claude review package

2026-10-03. Candidate implementation only; no independent VERIFIED status,
commit, push, frozen-pin update or milestone completion is claimed.
User explicitly selected the running `uri-m37-m39-integration` checkout.

## Evidence and design

- [Root-cause evidence](../research/PRESENTATION_VARIANTS_ROOT_CAUSE_AUDIT.md)
- [Bounded implementation design](../architecture/PRESENTATION_VARIANTS_CANONICAL_ARCHITECTURE.md)
- [Integration plan](PRESENTATION_VARIANTS_MIGRATION_PLAN.md)
- [Real Core qualification](PRESENTATION_VARIANTS_LIVE_CORE_RESULT.json)
- [Failed first live run](PRESENTATION_VARIANTS_LIVE_CORE_FAILED_SCHEMA_RACE.json)
- [Failed canonical dispatch run](PRESENTATION_VARIANTS_LIVE_CORE_FAILED_DISPATCH.json)
- [Failed content qualification](PRESENTATION_VARIANTS_LIVE_CORE_FAILED_CONTENT.json)
- [Failed photo narrative/count qualification](PRESENTATION_VARIANTS_LIVE_CORE_FAILED_PHOTO_NARRATIVE.json)

The original user session really generated one generic six-slide deck with no
images, then routed the local-output follow-up to Drive. The first candidate
live test also failed: eight files existed after generation/review turns. A
concurrent edit removed the variant schema while that run was in progress.
The failure is retained, not counted as acceptance evidence. The User confirmed
the other editing session is paused/finished; only the missing schema property
was merged back into its latest file, preserving the reference security work.
The second live run exposed a separate discovery defect: the Brain proposed
three legacy actions, canonical dispatch returned none, and fallback generated
seven files without variant arguments. The generator's declared content schema
is now also exposed to the preselected canonical Brain. Both failures remain
review evidence; no generation retries are hidden inside production execution.
The next run fixed the three-file/three-theme/photo return path and inventory
review with zero extra writes, but failed content qualification: seven slides
and an invented administrative reference/header instead of two subject slides.
The PPTX composition prompt now uses its own output shape while keeping identity,
applicable drafting policy, factual discipline and the existing document validator.
That fix produced subject content and actual photos, but another run claimed
photos were absent. A narrow result-consistency check now rejects that exact
contradiction. Generation reports actual total slide counts; qualification
separately counts subject slides and the existing licensed-image credit slide.

## Exact implementation scope

| Path | Repair |
|---|---|
| `uri_core/tools/generate_document.py` | Optional validated 1–3 distinct visual variants; compose once, reuse licensed-image lookup, render/save separate files; exact actual counts and embedded-image reporting; retain single-file compatibility. |
| `uri_core/core/tool_schema.py` | Advertise the bounded content-only variant argument. Preserve removal of model-selected attachment identity fields. |
| `uri_core/core/decision_engine.py` | Authenticated own-session metadata inventory, bounded to ten references; generator content-schema discovery, single-call variant planning and metadata-only local review guidance. |
| `uri_core/core/model_reasoning_adapter.py` | Match presentation/local-review guidance on the legacy reasoning path. |
| `uri_core/core/response_drafting.py` | Ground file counts and photo claims in actual generation results. |
| `uri_core/core/response_validation.py` | Reject a narrative denying photos/images when the tool counted embedded pictures. |
| `uri_core/services/document_composer.py` | Use a slide-specific composition prompt for PPTX; preserve institutional-note and other format paths. |
| `uri_core/core/native_tool_loop.py` | Carry recent dialogue and local metadata through continuation; return actual runtime file references to the client; guide one call for the design set and no generation for inventory review. |
| `uri_ui/lib/models/uri_turn.dart` | Backwards-compatible plural generated-file result. |
| `uri_ui/lib/services/http_uri_client.dart` | Parse/deduplicate actual references while retaining legacy first-file compatibility. |
| `uri_ui/lib/widgets/turn_card.dart` | Show/open every output through the existing authenticated attachment callback. |

New regression files: `test_presentation_variants.py` and
`uri_ui/test/presentation_variants_test.dart`. Opt-in real local Brain test:
`scripts/qualify_presentation_variants.py --real-brain`. It uses a disposable
normal registered URI account, temporary state and a harmless supplied brief.
Only public policy/capability data is copied; installed accounts, credentials
and provider configuration are not copied. It does not invoke Claude Code.

## Implementer checks

- 203 tests and 13 subtests passed: presentation, existing research/document,
  canonical dispatch, decision engine, native loop and institutional principal
  threading regression suites.
- 22 Flutter tests passed: plural-file client/widget, desktop failure and chat
  lifecycle checks. Windows debug build succeeded.
- Targeted Dart analysis reports no errors/warnings and three existing info
  lints in `http_uri_client.dart` (unused clarification import, two brace-style
  suggestions). Those unrelated lines were not changed for this repair.
- Neighbouring concurrent work: 33 tests and 19 subtests pass; one test in
  `test_int_arn_1_file_selection.py` expects a model `file_id` schema that the
  concurrent reference-security repair deliberately removed. Codex did not
  restore that identity proposal or alter the other worker's test.
- Three frozen guards fail against existing accepted blob pins. Candidate and
  unrelated dirty changes need independent review. Pins and guard logic remain
  unchanged; do not interpret focused test success as frozen acceptance.
- Native live UI verification remains pending until recorded separately.

## Latest real Core result and desktop checkpoint

`PRESENTATION_VARIANTS_LIVE_CORE_RESULT.json` reports `passed=true`. A harmless
supplied brief was acknowledged in 20,891.4 ms; actual generation/return took
26,798.7 ms; local inventory follow-up took 11,778.1 ms. Three actual PPTX
files were independently downloaded through the authenticated file endpoint
and inspected: distinct academic/modern/warm colors, original subject heading,
two subject slides plus one image-credit slide, one embedded picture per file.
The reply carried all three references. Follow-up inventory remained three,
with conversation mode, zero dispatch and no Drive access. Canonical telemetry
records READY/single_action generation, with no legacy fallback.

These structural checks do not certify every institutional fact or visual
quality. The supplied topics were illustrative; independent review should
check suggestion labeling and evidence discipline in actual slide content.

Additional response suites: 77 pass / 2 fail under current canonical defaults.
Both failures are legacy M8 endpoint tests that stub only the legacy
orchestrator, which canonical execution now precedes. All six endpoint tests
pass when run with their intended legacy-only flags and an unreachable mock
provider address. Production flags were not disabled to make these pass.

The existing port-8000 Core was restarted through its normal `.venv` desktop
launcher; loopback health is OK. Existing account/provider configuration and
security flags were retained, with no credential reset/copy. The candidate
Windows debug UI is open (process 23900 at this checkpoint); normal account
sign-in/session restoration remain user-controlled. The separate port-8018
harness test Core was left untouched. A native manual three-chip/open/follow-up
test was requested; no desktop presentation acceptance is claimed yet.
Core listener process at this checkpoint is 22860 (the `.venv` launcher process
delegates to the installed Python runtime); the UI is responsive. No installed
authentication store was replaced, copied or reset.

Final release gates: independent Claude review, accepted frozen pins/scope,
resolution of the neighbouring file-selection test/schema conflict, and live
native presentation UI evidence. No commit or push was performed.

## Reviewer instructions

### 2026-10-03 layout and approval follow-on candidate

The User's overlap screenshot supersedes prior visual acceptance assumptions.
Renderer text now fits a shared measured body region, preserves all bullets,
and bounds portrait images. Actual PPTX geometry/text estimates are inspected
before publication. The existing composition role reviews the request, source
evidence and rendered extraction, with at most one validated correction and
one final review (two calls maximum). Unresolved review/layout failure publishes
zero files. Unavailable review is explicitly provisional; no visual/independent
audit is claimed. DOCX/PDF/XLSX review remains deferred.

See DOCUMENT_LAYOUT_REVIEW_ROOT_CAUSE_AUDIT.md (research), the corresponding
architecture/migration records, and APPROVAL_RESULT_ROOT_CAUSE_AUDIT.md (research).
ApprovalStore hashing now matches existing data-class serialization, without
rebinding old records. The declared Google content schema reaches the Brain;
actual approval status/links reach Flutter and the own-session transcript.
Review the original gate paths, wrong-session/argument/principal/capability
rejections and single-use consumption. No Google creation was retried.

Latest deterministic checkpoint: 139 Python tests (layout, variants, office,
research, approval store/gate and new binding/transcript cases), 18 Flutter
tests (approval responses, file chips and failure reasons). Windows Release
build succeeded. Flutter analysis reports seven info-level findings in this
working tree, with no warnings/errors. No frozen guard/pin changes, commits
or pushes. This is Codex self-qualification, not Claude's independent audit.

Live failures retained: DOCUMENT_LAYOUT_REVIEW_LIVE_CORE_FAILED_REVIEW_FORMAT.json
(27,450.3 ms, files returned provisionally, fenced JSON rejected), and
DOCUMENT_LAYOUT_REVIEW_LIVE_CORE_FAILED_COUNT_CONTEXT.json (28,078.8 ms, zero
files, reviewer failed to distinguish content slides from credit slide).
The corrected result is recorded separately. Fixture decks are retained only
under scratch/document_layout_qualification; isolated account credentials are
not exported. The unsafe legacy test-isolation incident and its remedy are
disclosed in APPROVAL_RESULT_ROOT_CAUSE_AUDIT.md; those failures are not a pass.

Corrected live Core checkpoint: DOCUMENT_LAYOUT_REVIEW_LIVE_CORE_RESULT.json
reports passed=true. Generation and authenticated return took 22,260.9 ms;
the composition-role recheck accepted with zero corrections; all three actual
downloaded files passed geometry/font estimates, had two subject-content slides
plus one credit slide, distinct themes and licensed photo embedding. Own-session
inventory follow-up took 11,706.4 ms and remained three files with no dispatch.
Native UI/raster visual review and independent audit remain unperformed. The
Windows Release app was reopened against the normal Core (health OK, port 8000,
listener 20488) using the existing installation/account configuration. No stale
Google action was replayed and no additional Google write test was attempted.

Remaining acceptance gates: actual native rendering/download/result UI,
fresh explicit cloud approval if the User elects that test, and independent
Claude review of the complete dirty-worktree diff and accepted scope/pins.

Trace actual `/ask` planning → canonical/native gate → approval gate → generator
→ own-user FileStore → response → Flutter chips/download endpoint. Test one-file
compatibility, variant bounds/unknown fields, partial storage, denied execution,
original-topic/photo carryover, and an inventory-only follow-up with zero writes.
Check session/user isolation and ensure metadata/proposals never become file
identity, permission, approval, credential or execution authority.

Preserve pre-existing changes in server/canonical execution, read/convert tools,
capability registry and reference tests. The bounded overlapping baseline
snapshots in `scratch/presentation_repair_baseline/` are evidence only; never
restore a whole overlapping file from them. Inspect current HEAD/diff directly.

M36–M39 implementations, credential handling, Main Brain/harness separation and
existing security gates are outside this repair. Claude must decide acceptance
and any authorized pin changes; Codex self-tests are not an independent audit.
