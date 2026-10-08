# Harness desktop completion — bounded architecture

2026-10-03. Implements the direct User assignment using
[Stage 1](../research/HARNESS_DESKTOP_COMPLETION_ROOT_CAUSE_AUDIT.md).
Extends the provisional desktop seam; does not edit frozen M38/Core contracts.
Governing ADR-018, operating policy, model/runtime contract, lifecycle and
acceptance rule remain authoritative.

Real UriApp → Harness Management → authenticated isolated Core composition →
small registry / user-selected task controller → existing DesktopHarnessService
→ M38 Claude runner → M37 independent result verifier → safe receipt.
Registry reports discovered/available/authorized/tested/blocked separately.
Native descriptor discovery uses supported CLI commands, strips paths,
arguments, credentials and transcripts, and never grants capabilities.
No native plugin/MCP executes by default. Gmail permissions are unchanged;
none are qualified through this seam.

Antigravity implements discovery and an explicit fail-closed execution method.
No alias to M38 Claude or change to HarnessType. Unknown quota/authentication is
shown explicitly. Prior native-login evidence is dated, not current auth proof.
Codex existing adapter is discoverable but not desktop-qualified here.

Provider choice is required before preparation, bound into one-use user approval
and persisted task checkpoint. Only the fixed disposable repair is executable.
No arbitrary prompt/path/model/elevation from clients. Brain configuration is
not touched. Polling returns safe status, final receipt and measured duration,
not raw CLI events. Native streaming/session continuation remains unsupported
at this desktop seam and is declared as such.

Controller supports user-bound cancellation through the existing runner event.
Checkpoints conservatively record interrupted/potentially non-idempotent work;
restart never replays it. Quota blocks further submission until explicit wait
and retry authorization. Recovery never switches/transfers/replays a task;
new provider/task needs a fresh approval. Verified work remains in the separate
persisted qualification root, without write-back.

General Brain discovery/feedback integration cannot be claimed through a fixed
fixture. Production canonical-loop acceptance and independent review remain
open gates. Launcher adds an explicit provisional mode without changing installed
production checkout, accounts or server on port 8000.
