# Lifecycle receipt — URI-OFFICE-M1

Stage: **VERIFIED** · baseline `ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` · candidate `25fce881bad918e32dbd732e8004dfabdfa41985` · events 78 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `7f03be1c-a804-4de6-853f-7594504d8ff4` | `3599db6ecd8d` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `7ebe3be0-0341-4b06-8445-ed0e6aaa70bb` | `68d60652e832` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R3 | claude_cli | `9061675f-3ee6-49fd-9a19-d4b34c71cb89` | `4743860bb104` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R4 | claude_cli | `8711d217-fb8b-4199-97a3-39ce2e06636e` | `dcab7e1b2138` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R5 | claude_cli | `218370ce-9ed2-44e7-a3ac-53712861e18a` | `a73daefef733` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R6 | claude_cli | `a95564d5-efa3-4a23-bc0e-97eba7320df0` | `ace76d3cae51` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R7 | claude_cli | `5931f0b4-2dd2-4da4-b2da-2f35ceccec98` | `65180741ee24` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R8 | claude_cli | `45120fde-bb79-459c-b1ce-e063232dd4e6` | `02c91b85a99a` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R9 | claude_cli | `fc4a852c-77d6-419f-9c4e-a3bbf5013925` | `25fce881bad9` | ACCEPT WITH FINDINGS | ACCEPT WITH FINDINGS | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `68d60652e832c0a92aa1b1998da09cee308a16fa` | R1-01, R1-02, R1-03, R1-04, R1-05, R1-06, R1-07, R1-08, R1-09, R1-10, R1-11 |  |
| P2 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |
| P3 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |
| P4 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no regression test fails on the pre-repair commit |
| P5 | REFUSED | `-` | R2-01, R2-02 | REGRESSION: no runnable regression test (a test file with a configured runner is required) |
| P6 | COMMITTED | `4743860bb104e49979ccbc016181facc3c440838` | R2-01, R2-02 |  |
| P7 | COMMITTED | `dcab7e1b2138d73b5b0904137fa6a79af99945bd` | R3-01, R3-02, R3-03, R3-04 |  |
| P8 | COMMITTED | `a73daefef7336f0d17d0cc57e1687b9567d6a9b1` | R4-01 |  |
| P9 | COMMITTED | `ace76d3cae51d74009cc32b73f532fae02078d73` | R5-01, R5-02 |  |
| P10 | COMMITTED | `65180741ee24366b17ad6923ff8e85e7a3ff9e09` | R6-01 |  |
| P11 | COMMITTED | `02c91b85a99a0db74477ace08d1dfbed581c0885` | R7-01, R7-02 |  |
| P12 | COMMITTED | `25fce881bad918e32dbd732e8004dfabdfa41985` | R8-01 |  |

## Qualification

- `25fce881bad9`: ok=True blocked=None new failures={"python-a2ui": [], "python-office": []}

## Open findings (latest round)

- R9-01 LOW blocking=False: The panel never shows how many proposed changes a reload dropped (proposals_dropped)
- R9-02 LOW blocking=False: No Dart test covers the controller reload path (RELOAD_REQUIRED, then POST /workbook/<id>/reload)

## Integration

```
{
 "at": "2026-10-11T15:29:02Z",
 "candidate": "25fce881bad918e32dbd732e8004dfabdfa41985",
 "mode": "none",
 "status": "NOT_INTEGRATED_BY_POLICY"
}
```

## Blocker

```
null
```
