# Lifecycle receipt — URI-OFFICE-M1-c

Stage: **VERIFIED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `e6a4dcd501089d4889d08a7e5f3425179d8246c6` · events 13 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `244f828e-dbf7-4490-86ef-3cbf75311380` | `e6a4dcd50108` | ACCEPT WITH FINDINGS | ACCEPT WITH FINDINGS | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|

## Qualification

- `e6a4dcd50108`: ok=True blocked=None new failures={"python-a2ui": [], "python-office": []}

## Open findings (latest round)

- R1-01 LOW blocking=False: Office companion conversation is not cleared when another workbook is opened
- R1-02 LOW blocking=False: Host request filter fails open on internal errors; lockdown install cannot report failure
- R1-03 LOW blocking=False: Host filter and RTC/WebTransport removal do not cover workers
- R1-04 LOW blocking=False: Bundle-hash checks ignore symlinks; Python/Dart algorithms diverge for non-ASCII names
- R1-05 LOW blocking=False: @grpc/grpc-js override resolves to a nonexistent path; committed stub is never used
- R1-06 LOW blocking=False: Shared overlap files converted LF->CRLF, turning additive edits into whole-file rewrites
- R1-07 LOW blocking=False: Minor page/service hardening gaps

## Integration

```
{
 "at": "2026-10-12T00:54:14Z",
 "candidate": "e6a4dcd501089d4889d08a7e5f3425179d8246c6",
 "mode": "none",
 "status": "NOT_INTEGRATED_BY_POLICY"
}
```

## Blocker

```
null
```
