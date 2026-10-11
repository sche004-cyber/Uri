# Away mode — unattended operation while the owner is away (from 2026-10-11, 10+ days)

Owner request (2026-10-11): "continue but I will be away from computer for more than 10 days, find a way for it to
work while am away from pc". This file is the standing plan; every check-in follows it and records what it did.

## Mechanism

- A Routine fires into this same Claude Code session every 4 hours. Each firing is one check-in.
- At each check-in, Claude does the following:
  1. If the container was reset, restore it from `RESTORE.md`.
  2. Read the lifecycle state and the driver's state.
  3. Act on the outcome, following the rules below.
  4. Update this checkpoint and push it to `ccr-cab5ed06-9hwyc4`.
  5. Re-arm a watcher for the running driver.
- Between check-ins the lifecycle driver runs as a detached process, with independent reviewers and repair workers as
  separate `claude -p` processes, exactly as in an attended run.

- Routine `trig_015qjUTUMbs595nDBNdzpYBW` ("URI away-mode lifecycle check-in"), cron `16 */4 * * *` UTC, fires into
  session `session_01P2p3uVP5b87uL5UMyWApaJ`.
- Driver launches go through `lc-launch.sh <config>` (copy kept here; installed at `/tmp/claude-0/lc-launch.sh`), which
  accepts only configs under `/home/user/uri-wt/lifecycle-runs/`.
- Owner-approved narrow allow rules (2026-10-11) in the container's `~/.claude/settings.json`: that launcher,
  `create_trigger` and `send_later`. **Known limit:** a container reset loses these rules. A check-in after a reset can
  still restore, verify and push the checkpoint, but auto mode may refuse driver launches. That refusal is recorded as
  BLOCKED until the owner is back; it is never worked around.

## Queue (in order)

1. **W1/A0 closure** (running). Independent ACCEPT on the exact commit, then the gates, then the D1 merge into
   `integration/git-sync-20261008` (expected tip `ce1a90c`) with a receipt.
2. **SSRF-1** (D2). Plan: `lifecycle-runs/SSRF-1_PLAN_DRAFT.md`. The branch is cut from the canonical tip after step 1,
   and `authorized_protected_changes` is `uri_core/tools/fetch_url.py` only.
3. **W2** (brief `docs/plans/W2_SITE_DOCUMENT_SEARCH_BRIEF.md`). Owner direction, 2026-10-11:
   - Downloaded documents are temporary. Each is read, then deleted when the work is done, including on failure or
     cancel; leftovers are swept at the next start.
   - What stays is a memory record: source URL, site, the menu path where the document was found, the linking page,
     title, date, reference number, per-page text, content hash and retrieval time.
   - Relations go in the existing M23 `GraphStore`: notice → attachment, corrigendum → original, same reference number,
     same department, supersedes.
   - Answers cite URL and page, and quote numbers from the stored text (D7).
   - Correction to the earlier "PDF-to-image library needs an owner decision": URI already ships PyMuPDF and
     pytesseract (`requirements.txt`, `uri_core/services/pdf_reader.py`). Scanned PDFs therefore use the existing
     `PDFReader` OCR, with no new dependency. OCR needs Tesseract installed on the PC: NOT VERIFIED in the cloud.
   - Still open, with conservative defaults until the owner decides:
     - no scheduled refresh;
     - the benchmark site list is a proposal only;
     - personal data in public documents (for example names in results lists) is indexed for search only and never
       written to user memory or learning (D5);
     - no permanent copies of PDFs are kept.
4. **RW1** is NOT started unattended. Its benchmark needs Windows and WebView2 on the owner's PC.

## Allowed unattended (already authorised)

- Lifecycle runs, repairs, reviews and gates (skill policy).
- D1 merge integration after the driver's own evidence checks.
- The D2 change to `fetch_url.py` only.
- Pushes to the session branch.

## Never unattended (waits for the owner)

- Production deployment or cutover.
- Any other frozen-file change.
- New runtime dependencies.
- Edits to `~/.gitconfig` (the three leftover test entries stay until the owner removes them).
- Weakening gates or suppressing findings.
- RW1, the social-search hand-off and YouTube work.
- Any blocker whose `needs` names the owner, except this one: a TAMPER whose only cause is a container reset
  (a different reviewer CLI path or version, or fresh git config).
  - It may be unblocked only after inspection, with a note that lists what changed.
  - If anything else changed (hooks, repo config, refs, `url.*`, filters), the run stops and waits.
- **Budget:** each milestone keeps its own lifecycle budget (W1/A0: $400, 30 rounds, 36 h). The whole away period is
  capped at **$600 of worker spend**. On reaching the cap, work stops at a checkpoint and waits.

## If a check-in cannot act

Permission refusals, missing tools or network blocks are recorded here and in the closure report as BLOCKED. Claude
retries at the next check-in and never works around them. After 3 check-ins in a row with nothing new and nothing
runnable, the Routine is paused and the reason is written here.

## Check-in log

| UTC | What happened |
|---|---|
| 2026-10-11 06:20 | Checkpoint created. W1/A0 round 9 review of `3dd9cde` running (driver PID 15820). Spend so far $32.94. |
| 2026-10-11 06:25 | R9 REJECT (6 blocking MEDIUM: R9-01..06), driver repairing. Allow rules added and routine created with owner approval. |
| 2026-10-11 06:30 | Owner switched back to Auto. Allow-rule test in auto mode: `lc-launch.sh` with a nonexistent config ran and refused (exit 2) - launches are permitted unattended. |
| 2026-10-11 06:40 | Owner direction for W2 documents recorded: temporary download, memory record and relations, then delete. PDF-library decision corrected: PyMuPDF and Tesseract OCR already exist. |
