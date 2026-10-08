# Desktop harness qualification architecture

2026-10-02. Bounded test architecture derived from
`docs/research/DESKTOP_HARNESS_ROOT_CAUSE_AUDIT.md`. Direct User instruction assigns
implementation to Codex. This document does not redefine or independently accept
M38/M39 architecture. Governing model/runtime and four-stage rules still apply.

Path: real Flutter `UriApp` opt-in test control -> HTTP -> existing Core
authenticated-principal dependency -> isolated qualification router/service ->
M38 `HarnessRunner` -> native authenticated Claude Code CLI -> URI-owned
verifier -> safe receipt -> Flutter display.

The launcher composes Core and the new router only in a loopback test process.
No `uri_core` module or M38 source changes. `uri_v1` never imports Core; only
the composition script imports both. The normal Core route table remains
unchanged. The opt-in routes have an explicit USER classification map and
require login, including when existing Core routes allow legacy ambient state.

Execution requires preparation and a separate, strict boolean approval bound
to authenticated URI user and one random token; it expires after ten minutes,
is consumed before execution, and cannot replay. At most one execution runs.
Clients cannot supply a goal, file path, command, model, capability or elevation.
The test task is fixed infrastructure qualification, not task-specific Brain logic.

Only a disposable fixture script/workbook is registered. The CLI edits its
copy, with the same restrictive M38 flags and no grants. The subclass uses an
empty inventory and no auth environment variables: Claude Code alone reads its
existing native login. API keys, OAuth tokens and Brain provider configuration
are never used as URI authentication material for this run.

The isolated adapter maps the exact Windows workspace path to official POSIX
permission syntax. It adds no directories, tools, shell access or bypass flags.
M38 stays byte-for-byte unchanged. Native write denial after this adaptation is
a live test gate; failure must not be solved by broadening permissions.

URI verifies the exact expected repaired source, allowing only CRLF/LF
equivalence, using the existing registered `report_recomputes` seam. No
harness-written script executes. The result must pass URI verification and
also have a successful CLI result and exit code. A repaired file followed by
CLI failure is not desktop test success. The receipt excludes raw text,
transcripts, session handles, paths and auth metadata. It reports provisional
state, URI verdict, CLI completion, safety flags, exit and measured timings.

This is an opt-in desktop qualification seam. It does not register a production
Brain capability or claim the permanent acceptance rule has passed. Main Brain
access remains independent of harness access. Production canonical-loop
integration remains provisional and outside this test's completion claim.
