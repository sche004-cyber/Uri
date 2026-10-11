# Lifecycle receipt — SCHED-TOKEN-ACL-1

Stage: **VERIFIED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `33fc419ab1d9f7f286a313ebd794fd1c0248cb4f` · events 18 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `aa433228-260c-4e22-a339-3ad10a439ca3` | `1465e164729c` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `f3ac8b9f-6dd5-4b17-a91e-5886ffdd4f33` | `33fc419ab1d9` | ACCEPT WITH FINDINGS | ACCEPT WITH FINDINGS | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `33fc419ab1d9f7f286a313ebd794fd1c0248cb4f` | R1-01 |  |

## Qualification

- `33fc419ab1d9`: ok=True blocked=None new failures={"python-scheduler": []}

## Open findings (latest round)

- R2-01 LOW blocking=False: Windows: icacls /inheritance:r /grant:r leaves pre-existing explicit ACEs of other principals on the folder and on files already inside, so S1 'exactly one entry' and S2 are not guaranteed
- R2-02 LOW blocking=False: S2 test asserts nothing on POSIX
- R2-03 LOW blocking=False: service.py committed with CRLF line endings (whole-file churn)
- R2-04 LOW blocking=False: EVIDENCE.md test counts are stale after the R1 repair

## Integration

```
{
 "at": "2026-10-11T13:49:39Z",
 "candidate": "33fc419ab1d9f7f286a313ebd794fd1c0248cb4f",
 "mode": "none",
 "status": "NOT_INTEGRATED_BY_POLICY"
}
```

## Blocker

```
null
```
