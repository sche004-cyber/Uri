# Lifecycle receipt — URI-OFFICE-M1-c3

Stage: **VERIFIED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `6348b1b11eeefbea9299fabf06c5f3815475cd76` · events 13 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `c45aa89c-ebd6-4862-9846-e97b886a6fb9` | `6348b1b11eee` | ACCEPT WITH FINDINGS | ACCEPT WITH FINDINGS | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|

## Qualification

- `6348b1b11eee`: ok=True blocked=None new failures={"python-a2ui": [], "python-office": []}

## Open findings (latest round)

- R1-01 LOW blocking=False: WebView2 request filter fails open on COM errors, contrary to the 'fail-closed' claim
- R1-02 LOW blocking=False: @grpc/grpc-js override still resolves to a nonexistent path; committed stub never installed (prior M1-c2 R1-03 still open)
- R1-03 LOW blocking=False: AC18 Python and Dart bundle-hash algorithms diverge for non-ASCII names, sort order and symlinked files
- R1-04 LOW blocking=False: Voice drafting mode in Office focus sends push-to-talk to the hidden draft desk instead of the workbook or a refusal
- R1-05 LOW blocking=False: Windows reserved-name check misses names with spaces before the extension (e.g. 'C:\CON .xlsx')
- R1-06 LOW blocking=False: serve() accepts any loopback address and a negative Content-Length bypasses MAX_BODY
- R1-07 LOW blocking=False: Companion live-check evidence predates the final repair commit and the ledger does not name its commit; resume() drops the kept workbook on any other service error

## Integration

```
{
 "at": "2026-10-12T01:42:15Z",
 "candidate": "6348b1b11eeefbea9299fabf06c5f3815475cd76",
 "mode": "none",
 "status": "NOT_INTEGRATED_BY_POLICY"
}
```

## Blocker

```
null
```
