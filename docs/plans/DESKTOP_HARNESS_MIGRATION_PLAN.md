# Desktop harness integration plan and live runbook

2026-10-02. References:
[root cause](../research/DESKTOP_HARNESS_ROOT_CAUSE_AUDIT.md),
[architecture](../architecture/DESKTOP_HARNESS_CANONICAL_ARCHITECTURE.md).
Scoped by the User's direct instruction; independent Claude review remains required.

1. Reuse M38 runner/contracts, M37 workspace/run store/verifier and M36 recorder;
   create `uri_v1/desktop_harness/` and a separate Core composition launcher.
2. Add only an optional `UriApp` builder hook, desktop test transport/widget
   and an entry-point compile-time flag. Normal builds retain normal behavior.
3. Test missing auth, cross-user approvals, strict payloads, expiration,
   single-use execution, false claims, extra changes, symlink escape, CLI
   failure after correction, safe error reporting, Windows path serialization
   and classification. Test Flutter approval sequencing and receipt rendering.
4. Run M38's focused regression/adversarial tests and Flutter analysis/build.
5. User confirms native subscription login manually. URI never performs login,
   extracts credentials, creates OAuth tokens or falls back to an API key.
6. Run the real fixed task through the native desktop controls. Measure CLI,
   Core and application round-trip time separately. Inspect original protection
   and URI verifier status. Preserve failures and do not retry automatically.
7. Prepare all evidence for a different Claude session to review actual paths.
   No Codex commit, push, freeze, release or independent-audit claim.

Run from repository root:

```powershell
python scripts/run_desktop_harness_test.py --enable-subscription-test --port 8018
```

In a second terminal:

```powershell
cd uri_ui
flutter run -d windows --dart-define=URI_DESKTOP_HARNESS_TEST=true
```

The flagged build uses `http://127.0.0.1:8018` without persisting a new server
address. Core stores are rooted in `scratch/desktop_harness_test_state`, a separate
test installation. The optional `--state-dir` launcher argument chooses another
explicit test state root. This root persists normal URI account/session records
for restart testing; fixture workspaces are temporary and separate. No installed
account database is copied. The Flutter test login has separate local preference
keys and cannot clear or replace the installation's normal saved session.
It reuses URI's normal login screen. Choose **New here? Create an account** and
register a disposable account with credentials of your choice. Confirm logout
and login via the normal controls. Then click **Prepare
disposable test**, review the fixed task and restrictive posture, then click
**Authorize this Claude Code run**. The receipt and application latency appear
in the bottom panel. Only this explicit click starts the harness. HTTP errors
never cause an execution retry. A new approval is required for another attempt.

The launcher uses an automatically disposable temporary root. Keep the process
alive while collecting the safe receipt; stop this launcher with Ctrl+C after
evidence collection. Do not stop the unrelated server on port 8000.

Rollback: stop the opt-in launcher and run a normal Flutter build without the
test flag. No existing Core or M38 files, provider config, user login credentials
or original documents are migrated. No old module is retired.

Known limits: native CLI file permissions are not an OS sandbox; this test
denies shell/web tools and executes no generated code. The fixed-file verifier
does not establish general Office correctness. No Brain discovery or reasoning
feedback is claimed. Raw Claude narrative is not returned; the UI displays
URI's verified result receipt. The fixed-task native controls and rendered receipt
passed on 2026-10-02; independent review and general operational acceptance remain
pending. See the [review package](DESKTOP_HARNESS_CLAUDE_REVIEW_PACKAGE.md).

For explicit driver reproduction (starts the same real app with a test extension):

```powershell
flutter run -d windows -t test_driver/desktop_harness_main.dart --dart-define=URI_DESKTOP_HARNESS_TEST=true
```

After normal signup/login or restoration, run in another terminal in `uri_ui`:

```powershell
dart run test_driver/desktop_harness_qualification.dart <local-VM-service-URL-printed-by-Flutter>
```

This script clicks the two native controls and performs one authorized execution.
It does not sign in, read credentials or retry. It saves the safe desktop receipt.
The launcher supplies an ephemeral Core external-store encryption secret when
unset; connected-service credentials must not be configured in this test install.
It is separate from subscription authentication and existing installed secrets.
