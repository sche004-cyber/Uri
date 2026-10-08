# Claude / Antigravity desktop implementation report

2026-10-03. Codex implementation and separate self-audit, **provisional / not
complete / not independently audited**. No commit, merge, freeze or publication.
Development branch `codex/antigravity-harness-recon`; HEAD
`62d564cf9d2fa25e5a9860d20dcc7070b112badb`. No new commit SHA.

## Outcome and use

Implemented live harness management, explicit provider selection, asynchronous
Claude fixture execution, authenticated polling/cancellation, persisted task
checkpoints and explicit quota recovery in the existing real URI application.
Antigravity is discoverable and fails closed before task spawning. Fresh Claude
repair is **BLOCKED by native quota**. General canonical-loop integration and
Antigravity containment remain acceptance gates; this is not both adapters
fully completed for production.

Double-click `Launch URI Harness.bat` for the explicit provisional mode. It
calls the existing `scripts/launch_uri.ps1 -HarnessManagement`, opens the real
flagged URI desktop build and uses separate persisted test Core on port 8018.
Ordinary use requires no Python terminal. Normal `Launch URI.bat` continues to
open the installed production application; this work is not silently promoted
into the separate installed checkout. The normal desktop build has no Flutter
driver and accepts native keyboard input. A disposable local test URI account
was created through its UI; no provider account/credential was created or copied.

## Reuse and new implementation

- Reused M37 copy-in, original fingerprints, workspace diff, exact-byte
  verifier, result lineage, run store; M38 restrictive Claude adapter and
  supervised Windows process tree; existing subscription adapter, separate
  URI login store, router/composition launcher and real UriApp builder hook.
- Added `uri_v1/desktop_harness/registry.py`: native read-only installation,
  Claude subscription authentication status, Antigravity models, sanitized
  Claude plugin metadata, explicit unknown inventory/quota/auth states.
  No credential files or private session histories were inspected.
- Added `controller.py`: provider-bound one-use approval, task status,
  per-user ownership, one active run, atomic checkpoints, termination event,
  conservative restart state, explicit wait/stop recovery. No replay, context
  transfer, automatic external provider choice or Main Brain change.
- Extended USER-classified routes in `routes.py`, preserving the old test API.
  New selection/recovery payloads forbid arbitrary paths/prompts/permissions.
- Extended `service.py`: existing approval checks reused; cancel event passed
  to the unchanged M38 runner; native error classification and safe receipt.
- Extended `desktop_harness_test_client.dart` and existing panel: management,
  selection, permissions, approval, running state/cancel, URI verification,
  timing and recovery. Native plugin list is expandable and never authorized.
  Added opt-in Navigator hook to `app.dart`/`main.dart` so dialogs work in the
  actual MaterialApp builder placement, and auth-field keys for native tests.
- Added opt-in launcher and test-driver evidence/runbook. Native keyboard is
  the test-driver default now; signup automation temporarily enables emulation
  and restores keyboard input in finally. Normal builds never use the driver.

## Security qualification

Antigravity help and official permissions/custom-agent/sandbox documentation
were checked in the requested order against the prior reconnaissance. Declared
tools and terminal sandboxing do not demonstrate independent per-task file,
shell, network, plugin/MCP or global-allow isolation. Documented sandbox mounts
and network scopes inherit native grants and unsandboxed exceptions. M38 job
objects provide termination, not access containment. Windows Sandbox feature
inspection hit DISM access denial; no authenticated OS-contained profile was
qualified. No global settings, token copies, API-key forwarding or bypass flags.

All Antigravity task entry attempts are rejected locally before spawn. This
application-gate test is not native containment qualification.

| Mandatory Antigravity test | Status | Evidence / remaining gate |
|---|---|---|
| Authorized file modification | BLOCKED | No contained repair submitted |
| Protected-file access denial | BLOCKED | Not adversarially qualified against native tools |
| Unauthorized command denial | BLOCKED | No independently enforced task policy |
| Unauthorized network denial | BLOCKED | Native grant inheritance unresolved |
| Global-allow inheritance | BLOCKED | No qualified per-run replacement of global rules |
| Plugin / MCP denial | BLOCKED | Native access qualification absent; URI grants none |
| Approval rejection | PASS | URI selection/approval boundary rejects ineligible harness before spawn |
| Cancellation / process termination | BLOCKED | No Antigravity execution admitted; M38 termination separately tested |

Sources: [permissions](https://www.antigravity.google/docs/permissions?tab=cli),
[sandbox](https://www.antigravity.google/docs/sandbox?tab=cli),
[custom agents](https://www.antigravity.google/docs/subagents/).
No live Gmail or external-account demonstrations. Personal Gmail remains
read-only, drafts limited to the designated account, sending prohibited by
default; no native harness Gmail capability is qualified or granted.

## Real-world results

| Capability | Claude Code | Antigravity |
|---|---|---|
| Installation discovery | PASS: native version 2.1.287 | PASS: agy resolved; live version unknown, prior 1.2.14 evidence retained |
| Authentication | PASS: native auth status says subscription | UNTESTED current status; prior account-backed probes passed, explicitly dated |
| Actual repair execution | BLOCKED: fresh task reached native CLI, native rate-limit error | BLOCKED: containment gate |
| Result verification | PASS negative case: unrepaired bytes fail; no fresh successful repair | BLOCKED |
| Desktop accessibility | PASS: actual real-app controls and native keyboard build | PASS discovery/details; execution disabled |
| Permissions | PASS focused M38/approval regressions; bounded fixture only, not general OS sandbox | BLOCKED native containment; PASS local execution denial |
| Cancellation | PASS real supervised fake-process regression; native Claude cancellation UNTESTED due quota | BLOCKED |
| Native capabilities | PASS sanitized installed plugins discovered, all unauthorized/untested/blocked | PASS no imported plugins reported; skills/MCP unknown |
| Native capability invocation | UNTESTED: no harmless plugin execution grant qualified | BLOCKED |
| Quota handling | PASS real failure classified, checkpoint restored, recovery UI captured | UNTESTED native quota |

Fresh path: actual URI Desktop selection → prepared user approval → isolated
Core → M38 → native Claude CLI → independent M37 negative verification →
displayed receipt. Run `9fe01bc849784d3c9f39378dd30f50b8`; task
`cb03a28caa65487c9f0c9f0494dcdb2c`. Native auth source `none` (no metered API key).
Exit 1; no shell/network/write-back; safety flags empty. Actual workspace and
original script remain broken, and workbook copy matches original. A harmless
CLI response is not counted as repair success.

The first receipt said FAILED because quota appeared in a native assistant
`is_api_error_message=true,error=rate_limit` event and the terminal result used
generic failure text. Self-audit added explicit-event classification, replayed
only those already captured events offline, and repaired the checkpoint to
QUOTA_INTERRUPTED. Original receipt is preserved. No second CLI submission or
quota bypass occurred. Core restart loaded the durable gate; native UI refresh
displayed it. Non-idempotent/incomplete work is conservatively flagged.

Prior 11.367-second successful Claude desktop repair is historical evidence,
preserved in the earlier review package; it is not this run's success.

## Performance

Fresh failed/quota run: harness 4,538.8 ms; total Core 4,903.7 ms; measured
Core overhead about 364.9 ms; desktop receipt 5,023 ms, about 119.3 ms after Core
timing. These are failure-path measurements, not successful repair benchmarks.
Separate CLI startup/model processing/desktop rendering durations are UNTESTED.
No comparison with Antigravity no-tool reconnaissance latency is made.

## Checks actually executed

- Combined Python focused regression: **89 passed**, 3 deprecation warnings,
  65.77 seconds. Tests include desktop auth/integration, new completion
  controller, M38 harness/qualification, M37 execution/qualification and both
  M37 repair suites. Post-self-audit controller rerun: **12 passed**; final desktop/controller
  check after receipt/UI updates: **21 passed**.
- Full Flutter suite: **214 passed**. Focused post-repair auth/management
  rerun: **7 passed**. Widget test now uses the actual above-Navigator builder
  placement and checks selection before preparation, disabled Antigravity,
  separate approval and final receipt.
- Targeted Flutter static analysis: no issues.
- Windows debug build with `URI_DESKTOP_HARNESS_TEST=true`: passed. Actual
  native app was launched and exercised using Flutter driver, not a separate
  demonstration app, with screenshots of its rendered interface.
- Launcher PowerShell syntax parsed; explicit launcher invocation exited 0
  and opened the real non-driver desktop build. Cold-start check stopped only
  the owned test Core; the launcher restarted it hidden and restored its
  persisted checkpoints successfully, exit 0. Port 8000 / installed production
  process was preserved.
- M39 gates were not rerun: its implementation/design is in a distinct dirty
  branch and has not been merged or requalified here.

Python suite commands are the nine test modules named above; Flutter commands:
`flutter test --no-pub`, focused `flutter test --no-pub
test/desktop_harness_test.dart test/desktop_harness_auth_test.dart`,
`flutter build windows --debug --no-pub
--dart-define=URI_DESKTOP_HARNESS_TEST=true`.

## Separate Codex self-audit

Findings and repairs: actual Navigator placement fixed and regression matched;
native quota event schema fixed without task replay; restarted unknown tasks
now expose recovery and can be listed per user; another user's visible receipt
is cleared on account change; unsafe verifier flags prevent completed-work
qualification; quota visually disables further preparation; test-driver keyboard
emulation defaults off and is restored after automated input. No independent
audit claim. Frozen `uri_core/` and `uri_v1/execution/harness/` source diff is empty.

Unrelated dirty source work and installed checkout were not edited or merged.
**Generated-file limitation:** Flutter regenerated the three Windows plugin
registrant/CMake files during the required build; they were initially dirty and
are now clean against HEAD. Their initial generated contents were not captured,
so exact pre-run preservation of those generated artifacts cannot be attested.
No source-file reset was used to remove unrelated work.

## Visual evidence and remaining acceptance

Evidence directory: `docs/plans/HARNESS_DESKTOP_COMPLETION_EVIDENCE/`:
`management.png`, `antigravity_details.png`, `select.png`, `prepare.png`,
`execution.png`, `result.png`, `quota_recovery.png`; original
`fresh_claude_receipt.json`, corrected `reclassified_claude_checkpoint.json`,
and `side_effect_check.json`. Images are captures of the running native URI
widget tree. Earlier capture/signup images are diagnostic states, not success.

Remaining gates: Antigravity adversarial containment profile; successful fresh
subscription-backed Claude repair after quota recovery; qualified native tool
reuse; general task interface; desktop streaming tool events/session continuation;
live failure cases beyond the observed quota (unit/fake-process evidence is not
all native-provider evidence); production Brain discovery/action feedback through
the canonical loop; independent review and required release checkpoint.

The current UI executes only the disposable repair fixture. Provider model
selection is unavailable; onboarding/configuration gives native sign-in guidance
and refresh, not an automated provider-login/config editor. These limitations
remain explicit. Do not mark the assignment DONE or claim production acceptance.
