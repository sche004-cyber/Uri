# Lifecycle receipt — W1-A0-closure

Stage: **BLOCKED** · baseline `ffdf534386a3d40cf9e1646ef1080bee28dd3aa9` · candidate `20a646fd3fe8c48367bdc1cc995df5d09c3e7dab` · events 80 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | ccr_session | `session_017GFBkin32NjEb6jYwvN6vS` | `8019d41b77ba` | REJECT | REJECT | False | IMPORTED |
| R2 | claude_cli | `12b38140-caae-4bc9-af6f-f280844a5a0e` | `16f75d8e2e5f` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R3 | claude_cli | `dc854df5-6539-4d67-a07b-d78745165ebc` | `627f6b93d3f3` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R4 | claude_cli | `5874814d-5471-4904-911b-6b967b71f305` | `16155129b726` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R5 | claude_cli | `789f4eaf-8aee-442f-a567-e36ebb0a4464` | `52e852dcce59` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R6 | claude_cli | `79002ead-1ff3-4b60-857c-38e2cf67ca44` | `08a4569908d7` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R7 | None | `None` | `87720d6dcd76` | None | None | None | None |
| R8 | claude_cli | `ea66c95f-0132-47b0-b8ec-ad4326276010` | `87720d6dcd76` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R9 | claude_cli | `ce6ea834-ed6e-4ef5-91f8-9fdc31f027f8` | `3dd9cde91818` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R10 | claude_cli | `4f8c44cf-8eb5-407d-bf7a-6b574b4d1502` | `20a646fd3fe8` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `16f75d8e2e5f537749b32b1d754c347cbebdfc36` | R1-01, R1-02, R1-03, R1-04 |  |
| P2 | COMMITTED | `627f6b93d3f3a3de0ba60b1d0c58b9fe5729fede` | R2-01 |  |
| P3 | COMMITTED | `16155129b72685f25eca48a65252f6cd51fa47e4` | R3-01 |  |
| P4 | COMMITTED | `52e852dcce592e15fc2098bc1e169a7e009eb26a` | R4-01, R4-02, R4-03 |  |
| P5 | COMMITTED | `08a4569908d7b9db2e22366cada632e5ebe40639` | R5-01, R5-02 |  |
| P6 | COMMITTED | `87720d6dcd765e7e08ae3f44b4e141aa6c2b3bf0` | R6-01, R6-02, R6-03 |  |
| P7 | COMMITTED | `20a646fd3fe8c48367bdc1cc995df5d09c3e7dab` | R9-01, R9-02, R9-03, R9-04, R9-05, R9-06, R9-07, R9-08 |  |
| P8 | REFUSED | `-` | R10-01 | REGRESSION: no regression test fails on the pre-repair commit |
| P9 | REFUSED | `-` | R10-01 | REGRESSION: no regression test fails on the pre-repair commit |
| P10 | REFUSED | `-` | R10-01 | REGRESSION: no regression test fails on the pre-repair commit |

## Qualification


## Open findings (latest round)

- R10-01 MEDIUM blocking=True: R9-01 repair regression: the rebuilt selection copies hidden text (display:none, aria-hidden, tiny/transparent/off-screen) and <script>/<style> source into 'Selected text', bypassing the hidden-text filter; injected instructions and page-state secrets reach the Brain request
- R10-02 LOW blocking=False: Assist UI poll path has no epoch or ask-id check: an assist_ask_status reply in flight when the user presses Stop (or Stop, re-grant and a new ask) can still show the old answer (R9-05 class on the polling path)

## Integration

```
null
```

## Blocker

```
{
 "at": "2026-10-11T06:42:00Z",
 "kind": "CONFIG",
 "needs": "owner: review the policy change (CONFIG_CHANGED event) and `unblock --note`",
 "reason": "milestone config or resolved policy changed since the plan (now config e9f199344cb0, policy 60c95fb8b36f)",
 "stage": "READY_TO_RESUME"
}
```
