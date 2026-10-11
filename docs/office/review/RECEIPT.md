# Lifecycle receipt — URI-OFFICE-M1

Stage: **BLOCKED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `68d60652e832c0a92aa1b1998da09cee308a16fa` · events 21 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `7f03be1c-a804-4de6-853f-7594504d8ff4` | `3599db6ecd8d` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `7ebe3be0-0341-4b06-8445-ed0e6aaa70bb` | `68d60652e832` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `68d60652e832c0a92aa1b1998da09cee308a16fa` | R1-01, R1-02, R1-03, R1-04, R1-05, R1-06, R1-07, R1-08, R1-09, R1-10, R1-11 |  |
| P2 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |
| P3 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |
| P4 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |

## Qualification


## Open findings (latest round)

- R2-01 MEDIUM blocking=True: Formula fill/insert-function cells that carry only a shared-formula id (si) are reported to the service as empty values, so the draft clears cells the grid shows as formulas
- R2-02 MEDIUM blocking=True: PATCHES.md doesn't list the network kill switch or the WebRTC/WebTransport removal, yet says the diff from 9765e780 is exactly the listed patches
- R2-03 LOW blocking=False: The host network kill switch can be overridden by Dart-supplied browser arguments or the WebView2 environment variables and policies; 'no API to turn the lockdown off' is not accurate
- R2-04 LOW blocking=False: The request filter fails open on errors, ignores install HRESULTs and doesn't cover worker request sources
- R2-05 LOW blocking=False: An edit reply for a previous workbook can overwrite the newly opened workbook's draft in the panel
- R2-06 LOW blocking=False: The approval card keeps bidi/format control characters in values and formulas, and shows sheet names raw
- R2-07 LOW blocking=False: AC15 row still says the host layer and real-WebView2 run are 'open' while §13 records them done; the real-WebView2 probe hasn't been re-run on bundle faf22fb3; the gRPC placeholder cites a README that doesn't exist
- R2-08 LOW blocking=False: The Dart page-hash check happens before the live folder is mapped, and symlinks are not hashed (TOCTOU)

## Integration

```
null
```

## Blocker

```
{
 "at": "2026-10-11T14:00:55Z",
 "kind": "REPAIR_FAILED",
 "needs": "manual repair",
 "reason": "REGRESSION: no regression test fails on the pre-repair commit",
 "stage": "FIXING"
}
```
