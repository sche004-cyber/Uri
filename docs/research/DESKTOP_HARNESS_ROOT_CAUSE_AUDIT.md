# Desktop Claude Code integration: evidence and root cause

2026-10-02. Codex implementation-session inspection; not an independent closing audit.

Repository HEAD: `62d564c`. M38 is present under
`uri_v1/execution/harness/`. The HEAD implementation report, machine state and
independent batch audit record M38 as provisional, not frozen. The User requires
preserving it; this assignment treats M38 as protected regardless of that discrepancy.

No M39 runbook or `uri_v1/office/` implementation exists in this checkout.
Untracked `docs/plans/UI_WORKSPACE_RESEARCH_2026-10-01/` notes cite
`docs/reviews/M39_RECHECK_e9c891f.md` and `M39_LIVE_APP_INTEGRATION.md`; those
referenced files are absent here. No replacement M39 qualification is inferred.

Actual desktop path: `uri_ui/lib/main.dart` builds `HttpUriClient`, which uses
Core HTTP routes. Core `uri_core/app/server.py` handles `/ask` and `/approve`;
neither calls M38. No `uri_desktop_adapter.py` or `run_desktop_server.py` exists
here. The isolated M38 runner has no HTTP or Flutter entry point. This is a
missing integration, not an authentication-provider change.

M38 already provides native CLI `-p`/stream-json, scrubbed environment,
no-session-persistence, strict per-run MCP config, path-scoped tools, `dontAsk`,
shell/web denial, hash-bound copy-in capsule, process supervision and Windows
Job Object cleanup, URI diff/claim/verifier lineage and original-file checks.
Its discovery tests credential-file existence, not authenticated access.
Elevation and native capability grants require trusted, explicit, named input.
No write-back is performed by `HarnessRunner`. Subscription is never API access.

CLI installed: Claude Code `2.1.281`. The User manually confirmed an existing
subscription login. No credential file, session history or token was inspected.

Real native probe 1: exit 0, harness 15,252.2 ms / Core 15,564.2 ms;
URI verification FAILED, original unchanged. Probe 2: exit 0, harness
12,683.5 ms / Core 12,990.1 ms; unchanged candidate and structured `Edit`
permission denial. M38 serializes Windows scopes as `//C:\Users\.../**`.
Official CLI matching normalizes Windows paths to `/c/Users/...`.
The integration layer corrects serialization without changing the authorized path.
Raw CLI result text, transcripts, credentials and auth status details are not
included in these evidence artifacts.

References: [native CLI interface](https://code.claude.com/docs/en/headless),
[permission rules](https://code.claude.com/docs/en/permissions),
[subscription login](https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan).

Further gaps remain outside this bounded assignment: general Brain discovery,
automatic escalation, canonical result feedback into Brain reasoning, Office
binding/write-back, production route integration and final independent acceptance.

## Installation reconciliation and authentication follow-up

The running installed Core on port 8000 belongs to
`C:/Users/cheta/Development/uri-m37-m39-integration` (process cwd confirmed),
whose inspected HEAD is `a5920b0`. Its M36/M37/M38 freeze record records a freeze
at `bd7c450`; its M39 implementation report and `M39_LIVE_APP_INTEGRATION.md`
describe isolated Office work and a prepared, unapplied production seam. The
runbook/recheck records Windows/live closing gates and API-key-source checks as
open. These documents were inspected read-only; no changes were made to that
installation. The initial absence finding applies specifically to `_V1` at
`62d564c`, not to the installed checkout. No branch state was merged or inferred.

Port 8018 initially used `_V1`'s separate account database by relative-path
resolution. Metadata comparison found one account in `_V1`, two in the installed
checkout, with one username shared. Different databases explain why an installed
login cannot be assumed available or current in the test process. Neither
database was copied, reset or edited by implementation commands. The User
reported a failed login and a 35-pixel overflow before further qualification.

The launcher now changes cwd before importing Core to the dedicated
`scratch/desktop_harness_test_state` installation. Normal signup/login/logout
and persisted-session validation remain unchanged. The test build uses separate
local URI-session preference keys. The fixed login form scrolls when the viewport
is too short; the test panel itself is height-bounded and scrollable. Authentication
checks exercise actual Core endpoints in a disposable process, not an auth bypass.

Official `claude auth status --json`, executed with the scrubbed harness
environment, returned exit 0, `loggedIn: true`, `authMethod: claude.ai`, and
`subscriptionType: pro`. Only these non-secret fields were retained; no email,
account identifier, token, credential file or raw auth response was exposed.
