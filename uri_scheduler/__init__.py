"""URI Scheduler: durable, timezone-correct scheduled agent execution owned by URI Core's operational layer.

The scheduler decides WHEN work is due and WHETHER it is still authorized. Execution of harness work is delegated to
the accepted Phase 2 supervisor (`uri_supervisor`): admission, contained spawn, raw stream capture, quota breakers and
postcondition reconciliation are reused, never re-implemented. Nothing here needs the Brain, a UI window or an open
conversation: a single `SchedulerService` process with a state directory is sufficient.

Modules:
  timespec        schedule kinds (once, recurring, calendar-relative) -> concrete occurrences
  calendar_store  versioned festival calendar records with provenance
  store           SQLite state (jobs, occurrences, attempts, artifacts, reviews, hash-chained audit events)
  engine          the scheduler: activation, due detection, claiming, missed/interrupted recovery, review actions
  harness         harness gate (availability, authentication, qualification) and supervised Claude execution
  gif_task        the festival GIF task template: task package, scene validation, render, GIF validation
  renderer        URI-owned deterministic scene renderer (Pillow) used by the GIF template
  service         process entry point: single-instance run loop, CLI, local HTTP API for the UI
"""

SCHEMA_VERSION = 1
DEFAULT_TZ = "Asia/Kolkata"
