# Lifecycle receipt — SCHED-TOKEN-ACL-1c

Stage: **VERIFIED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `11ec4a21f2efcaa1a40493f4208f0cc5cd7f108e` · events 18 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `c76a8015-07c3-477f-89ae-0307a03a1276` | `5b7c05498618` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `ab26664b-5da2-4844-9b71-367a6788e7b6` | `11ec4a21f2ef` | ACCEPT WITH FINDINGS | ACCEPT WITH FINDINGS | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `11ec4a21f2efcaa1a40493f4208f0cc5cd7f108e` | R1-01, R1-02 |  |

## Qualification

- `11ec4a21f2ef`: ok=True blocked=None new failures={"python-scheduler": []}

## Open findings (latest round)

- R2-01 LOW blocking=False: If both the final rename and the restore rename in secure_state fail, the state path is missing and the next run creates an empty locked folder and starts on an empty DB

## Integration

```
{
 "at": "2026-10-11T14:44:38Z",
 "candidate": "11ec4a21f2efcaa1a40493f4208f0cc5cd7f108e",
 "mode": "none",
 "status": "NOT_INTEGRATED_BY_POLICY"
}
```

## Blocker

```
null
```
