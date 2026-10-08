# Antigravity harness integration feasibility

2026-10-03. Codex reconnaissance and self-check evidence; provisional, not an
independent audit, milestone acceptance, freeze or release.

## Finding

**A supported integration surface exists and works locally. A URI-compatible
restrictive execution boundary has not been qualified.** Antigravity CLI
`agy` 1.2.14 successfully completed native-account, no-tool headless probes.
Do not describe Antigravity as GUI-only or claim it has no CLI.

The current integration stop is narrower: the documented CLI inherits native
global permission settings, whereas URI's qualified Claude seam supplies its
restriction and capability configuration per run. No documented equivalent
for replacing/ignoring Antigravity's global permission rules and inherited
customizations was located in the installed help or sources reviewed below.
This is an unresolved qualification prerequisite, **not proof that such an
interface is impossible or absent from every Antigravity release**.

The repair task was not submitted, no production/desktop adapter was installed,
and no Antigravity desktop-success claim is made. The User explicitly requires
preserving containment and permits a documented technical blocker.

## Supported interfaces and actual qualification

| Mechanism | Documented | Observed here / limitation |
|---|---|---|
| Official Windows CLI | Yes: `agy` | Installed at `C:/Users/cheta/AppData/Local/agy/bin/agy.exe`; version 1.2.14; help executed. |
| External task submission | `-p` / `--print`; text or streaming input | Native headless response succeeded. Only harmless reconnaissance prompts were submitted. |
| Result retrieval | JSON / NDJSON events and terminal result | Real `init`, `step_update`, `result`, and `SUCCESS` observed. Exit 0 alone cannot establish a successful file repair. |
| Existing account authentication | Native OS keyring sign-in | Probes worked with M38's allowlisted environment, no auth variables, and no forwarded Gemini/API keys. Subscription tier and identity were not inspected. |
| Session lifecycle | Continue and conversation selection | Documented only; no resume test. No session handle or transcript retained in URI evidence. CLI-native session persistence was not disabled or erased. |
| Model selection | `models`, `--model`, `--effort` | Installed help agrees; selection and automatic selection not live-qualified. Main Brain configuration was never used. |
| Streaming | NDJSON output | Events observed; no desktop streaming UI or cancellation API implemented. |
| Local API | Python SDK | Official SDK exists. Its published quickstart uses a Gemini API key or Google Cloud credentials; existing subscription-account reuse was not established. Not a substitute for this account-backed assignment. |
| Local IDE HTTP task API | Not established | No undocumented IDE/authentication endpoint used. MCP server management is not itself agent task submission. |
| GUI automation | Technically experimental | Not used. It does not solve the unresolved policy-isolation boundary. |

Primary sources reviewed:
[installation/authentication](https://www.antigravity.google/docs/cli/install/),
[headless execution](https://www.antigravity.google/docs/cli/headless/),
[permissions](https://www.antigravity.google/docs/permissions?tab=cli),
[sandbox](https://www.antigravity.google/docs/sandbox?tab=cli),
[custom agents](https://www.antigravity.google/docs/subagents/),
[CLI settings](https://antigravity.google/docs/cli/using/), and
[SDK](https://www.antigravity.google/docs/sdk/overview/).

## Permission qualification prerequisite

The permission guide documents allow/ask/deny rules in
`~/.gemini/antigravity-cli/settings.json`. Native allow rules take precedence
over defaults; defaults are not a URI-issued per-run deny policy. Headless
approval requests may be soft-denied while the CLI still exits 0. The sandbox
flag controls terminal sandboxing; it is not evidence that direct file tools
ignore existing non-workspace grants or that inherited capabilities are disabled.
See the [permission guide](https://www.antigravity.google/docs/permissions?tab=cli)
and [headless behavior](https://www.antigravity.google/docs/cli/headless/).

A metadata-only inspection found the local CLI settings file present, with the
five inspected policy/provider fields unset and no permission rules. This
snapshot does not establish per-run isolation or cover every native store.
No account tokens, keyring entries, credential files or session histories were read.
Global settings were not changed. A preflight snapshot alone would not prove
that the child cannot inherit broader policy during another native session.

Custom agents provide a promising documented tool subset. Tests used a
temporary workspace agent with only `view_file` and `replace_file_content`,
`mainAgent: true`, `subagent: false`, `commandExecutionPolicy: off`, and empty
MCP/skill/plugin lists. The selected agent appeared in the startup event, but
that event advertised the broad built-in tool inventory. A follow-up read
probe actually completed `view_file`; no `list_dir` execution event appeared,
and the model reported that the undeclared tool was unavailable.

**This is not a demonstrated allowlist bypass.** It is positive, limited
tool-subset evidence, not adversarial proof of all file/network/capability
boundaries. The startup inventory cannot presently serve as a reliable
confirmation of the effective subset. No shell, network or protected-original
operation was attempted under an unqualified boundary.

To reopen implementation, establish and reproduce a supported per-run policy
or an independently contained execution profile that preserves native account
authentication and normal approval controls. It must enforce workspace scope,
deny protected-original access, deny shell/network/escalation and ungranted
capabilities, and remain restrictive in the presence of permissive native
settings. Do not solve this by changing the user's global configuration,
forwarding an API key, enabling a bypass flag, or treating model obedience as
authorization enforcement.

## Repository and integration findings

This checkout started detached at
`62d564cf9d2fa25e5a9860d20dcc7070b112badb`, with extensive existing dirty work.
The Claude qualification is already provisional, documented in
[its review package](../plans/DESKTOP_HARNESS_CLAUDE_REVIEW_PACKAGE.md).
Its 11.367-second result is prior recorded evidence, not a run made here.

Relevant preserved path:
`uri_ui/lib/widgets/desktop_harness_test.dart` -> authenticated qualification
routes -> `DesktopHarnessService` -> protected M38 `HarnessRunner` -> supervised
CLI -> M37 URI diff/verifier/lineage -> safe desktop receipt. The launcher is
`scripts/run_desktop_harness_test.py`. Preparation and one-use user-bound
approval are separate; clients cannot supply arbitrary paths or grants.
The fixed repair uses a disposable copy of `report.py` and `sales.xlsx`, exact
byte verification, original-file checks, and no generated-code execution or
write-back. The current test panel is Claude-specific, not an existing general
harness selector. Brain-provider controls must not be repurposed as harness
authority.

M38's `HarnessType` lists Claude and Codex, not Antigravity. This assignment
does not modify that protected contract or disguise Antigravity as Claude.
No production Brain discovery/feedback integration is inferred from this
fixed-task seam.

The distinct installed integration worktree was inspected read-only at
`eb7369331e8c2ed7c7a8ea85db9ce1382fe3913f`, branch
`experimental/desktop-recovery-repair`. Its `M39_LIVE_APP_INTEGRATION.md`
describes a prepared Office integration design, distinct from this checkout's
qualification seam. No M39 or frozen code was changed, merged, or requalified.
Existing harness strategy research and development-workflow actor references
were inspected; no reusable Antigravity execution adapter was found in the
searched relevant experiment/adapter areas. Actor naming is not an adapter.

## Measurements and evidence

| Probe | Supervised CLI duration | Result |
|---|---:|---|
| Default-agent no-tool marker | 20,298.4 ms | Exit 0, SUCCESS, zero tool events, marker observed |
| Selected custom-agent no-tool marker | 17,013.9 ms | Exit 0, SUCCESS, zero tool events |
| Undeclared `list_dir` request | 18,531.5 ms | Exit 0, SUCCESS, no tool event; does not prove enforcement |
| Allowed file read plus undeclared listing | 29,028.2 ms | Exit 0; `view_file` ACTIVE/DONE; no `list_dir` event |

All four processes settled; no supervisor timeout was observed. Prompts used
`--sandbox`, `--disable-slash-commands`, `--output-format stream-json` and a
bounded `--print-timeout`; no permission bypass was passed. The first probe
also used `--mode plan`. Temporary probe directories contained no real user
documents and were removed by the temporary-directory context. No manual
sign-in or approval intervention was needed. Native CLI session persistence
may remain in its own store; no cleanup of that store was attempted.

These are CLI reconnaissance durations including startup, **not repair-task
latencies comparable to Claude's desktop baseline**. Separate startup, task,
Core overhead and application response times are unmeasured. No repair receipt,
native Antigravity UI screenshot, live provider-switching result, protected
original denial, network denial, authentication-failure, or cancellation
qualification is claimed.

Sanitized evidence (native transcript text, account identifiers, paths and
conversation handles omitted):

- [Default probe](ANTIGRAVITY_HARNESS_RECON_PROBE.json)
- [Scoped probe](ANTIGRAVITY_HARNESS_SCOPED_PROBE.json)
- [Undeclared-tool probe](ANTIGRAVITY_HARNESS_TOOL_POLICY_PROBE.json)
- [Allowed-read check](ANTIGRAVITY_HARNESS_ALLOWLIST_CHECK.json)

## Existing-path regression and self-review

Commands actually run, with no application-code edits in this assignment:

```text
python -m pytest tests/test_desktop_harness_integration.py tests/test_desktop_harness_auth.py tests/test_m38_harness.py tests/test_m38_harness_qualification.py -q
49 passed, 2 deprecation warnings in 40.61s

cd uri_ui
flutter test test/desktop_harness_auth_test.dart test/desktop_harness_test.dart
7 passed

flutter build windows --debug --no-pub --dart-define=URI_DESKTOP_HARNESS_TEST=true
Succeeded: build/windows/x64/runner/Debug/uri_ui.exe
```

This is a fresh focused sweep, not the prior 105-test Python sweep. Existing
fake-harness adversity and approval tests exercise the preserved Claude/M38
path; they do not qualify Antigravity. The widget receipt emitted by Flutter
tests is test data, not live desktop evidence. The Windows build was not
launched for an Antigravity run.

Separate self-review corrected two potential overclaims: the broad startup
inventory is not proof of callable undeclared tools, and successful no-tool
responses are not a desktop integration. `git diff --name-only --
uri_v1/execution/harness uri_core` returned no files. Existing dirty UI/platform
work was preserved. No new adapter, application code, tests, permission
configuration, milestone status, or installed Core change was made.

Development branch: `codex/antigravity-harness-recon`, created at the existing
baseline above without moving or committing unrelated dirty work. **No new
commit SHA:** findings remain uncommitted and provisional; Codex has no release
commit/push authority under the standing instructions.

Only Stage 1 evidence/reconnaissance has been completed. Adapter architecture,
migration, real desktop repair, provider-selection UI and full Antigravity
security qualification remain unimplemented pending the containment prerequisite.
No milestone has been marked complete, accepted, frozen or merged.
