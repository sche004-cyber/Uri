# Lifecycle receipt — SCHED-TOKEN-ACL-1b

Stage: **FIXING** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `51f6eedd0ca480f92a38dc2bf7d49ed440be1d7c` · events 33 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `d6870d26-afb3-40cb-b061-02fa2bb094d0` | `a52aecab0e96` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `b10db514-70f2-4c81-a5da-2eb7044cc8d2` | `31f4eb3544ae` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R3 | claude_cli | `edce273e-0344-488e-871b-be4bafc3ad4e` | `6a88dbcf1f5b` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R4 | claude_cli | `50ebed57-e337-409a-8efb-9f5b94b7fb68` | `b79c123ad050` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R5 | claude_cli | `8a7ff734-6050-4fd8-961b-81c299d87f00` | `51f6eedd0ca4` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `31f4eb3544ae389744653130a7933b3b4c23c5ea` | R1-01, R1-02 |  |
| P2 | COMMITTED | `6a88dbcf1f5b80c65ad15407f52081f5e4be698c` | R2-05 |  |
| P3 | COMMITTED | `b79c123ad05032991e0437892787b7fa732a0082` | R3-01 |  |
| P4 | COMMITTED | `51f6eedd0ca480f92a38dc2bf7d49ed440be1d7c` | R4-01 |  |

## Qualification


## Open findings (latest round)

- R5-01 MEDIUM blocking=True: Children are listed before the state folder is closed and never re-listed, so a file created after the listing (by timing, or through a folder handle opened under the old (M) access) is never taken over or reset, and the scheduler then uses it (e.g. an attacker-owned scheduler.db)
- R5-02 LOW blocking=False: drop_foreign_entries/owner_sid use path-based SetFileSecurityW/GetFileSecurityW, which follow a junction swapped in after same_folder()

## Integration

```
null
```

## Blocker

```
null
```
