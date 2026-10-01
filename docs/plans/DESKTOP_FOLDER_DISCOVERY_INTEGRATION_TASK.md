# Desktop folder discovery: deferred integration task

Status: RECORDED, NOT STARTED. Recorded 2026-10-01 during desktop recovery.

## Why it exists

The desktop app's canonical `POST /ask` (uri_core) has no capability that
discovers files inside a user-permitted folder. M39 (`uri_v1/office`) contains
deterministic folder discovery and binding, but by its own plan it never
imports `uri_core`, and the M36/M37/M39 frozen-scope guards treat `uri_core`
and `uri_ui` as frozen on this line. Wiring M39 discovery into `/ask` is
therefore a gated INT-* integration event, not a desktop repair.

User decision, 2026-10-01 17:57 UTC (Chetan): for the immediate demonstration
use the existing Flutter attachment path (attach a workbook, URI reads it with
`read_attached_file` through canonical `/ask`). Record folder discovery as a
separate, dependency-aware task; do not modify frozen M39 contracts or open a
substantial integration branch during the recovery. This is a demonstration
choice, not a permanent limit: URI must eventually discover files in
explicitly permitted workspaces without manual attachment.

## Dependencies

1. A User-authorized INT-* integration milestone that permits a uri_core
   adapter to call `uri_v1.office` (and the M36 memory / M37 Edge / M38
   execution layers it composes) without editing their frozen code.
2. A permitted-workspace model the desktop can show and the user can grant:
   which folders, read-only by default, consistent with M38 workspace
   containment and the approval gate.
3. Resolution of how desktop users grant and revoke a folder (UI surface is
   owned by the Hybrid/Combined UI plan; not designed here).
4. Independent audit of the integration, including the frozen-scope guards
   (any allowlist entry needs explicit User authorization, as with M39).

## Acceptance sketch (to be refined in the milestone plan)

- "Find the attendance workbook in my permitted folder and summarize it"
  discovers the real file only inside granted folders, asks when ambiguous,
  reads real contents, and returns a grounded summary with provenance.
- Paths outside the grant are never listed or read.
- No mocked discovery or contents in acceptance evidence.
