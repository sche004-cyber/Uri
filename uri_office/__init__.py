"""URI Office: live spreadsheet co-editing (milestone URI-OFFICE-M1, docs/office/00_PLAN_AND_ACCEPTANCE_CRITERIA.md).

A separate local service (`python -m uri_office.service run`), modelled on `uri_scheduler.service`: it binds 127.0.0.1
only, needs the per-launch bearer token from `<state>/api-token` (current user only), and is the authority for every Office
change.

  grants      files the owner opened (file picker) or approved for "save as"; every path is checked here
  refs        A1 cell/range parsing
  xlsx_model  .xlsx -> workbook JSON shown in the panel (openpyxl, read only)
  xlsx_patch  writes approved cell changes into the original package; untouched parts stay byte-identical
  ops         closed op schema the Brain and the panel may use
  draft       one versioned draft per open workbook: URI changes are marked and decided one by one
  approvals   save/apply and discard are A2UI confirmed actions bound to the SHA-256 of the exact change shown
  google      Google Sheets through URI's existing Google sign-in (read, export, copies); in-place writes need the
              owner-gated `spreadsheets` permission (O1)
  brain       one Brain call per instruction (BrainClient, strict JSON op schema)
  history     consented, per-workbook correction history: what changed and why, never cell values (AC12)
  service     HTTP API + CLI

Nothing here writes to a file or a Google Sheet without an approve action whose hash matches what was shown.
"""
