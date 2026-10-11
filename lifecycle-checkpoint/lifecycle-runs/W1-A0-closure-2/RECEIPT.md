# Lifecycle receipt — W1-A0-closure

Stage: **BLOCKED** · baseline `ffdf534386a3d40cf9e1646ef1080bee28dd3aa9` · candidate `f5a5b8ecbb5c524b3b768cc09ae71dfa2bcc068b` · events 36 · chain OK

## Review rounds

| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |
|---|---|---|---|---|---|---|---|
| R1 | claude_cli | `20329ef7-e90c-4054-b1eb-ab5e87feda1d` | `67aff5042c0f` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R2 | claude_cli | `100f4590-1645-4c04-b2db-d4e28e47940d` | `ca622bc0354a` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R3 | claude_cli | `c9556679-5432-4d0c-9e5d-806fdc2bba47` | `f370064354ba` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R4 | claude_cli | `7fb002ae-d084-4e18-b13d-6cbc18118a09` | `462be42c992c` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |
| R5 | claude_cli | `6f65a79d-136c-41cb-9cce-3a488617959e` | `f5a5b8ecbb5c` | REJECT | REJECT | True | COMPLETED_WITH_RESULT |

## Repairs

| # | Status | Commit | Addresses | Reason |
|---|---|---|---|---|
| P1 | COMMITTED | `ca622bc0354a960c82acd7a33ecc6de5bb9f360a` | R1-01, R1-02, R1-03, R1-04, R1-05, R1-06 |  |
| P2 | COMMITTED | `f370064354ba678ec5fed956a709cd0e7626c269` | R2-01, R2-02, R2-03 |  |
| P3 | COMMITTED | `462be42c992c273155e83801b32dc01580a897ef` | R3-01, R3-02 |  |
| P4 | COMMITTED | `f5a5b8ecbb5c524b3b768cc09ae71dfa2bcc068b` | R4-01, R4-02 |  |

## Qualification


## Open findings (latest round)

- R5-01 HIGH blocking=True: R1-01 class still open: a link next to an underscore or hyphen ('_refunds-portal.com_', 'refunds-portal.com_', '-refunds-portal.com') passes has_link_or_contact, mask_links, verify(), extractive(), the research surface and the A2UI validator
- R5-02 MEDIUM blocking=True: D7 bypass at the sentence edge: _excerpt lets a claim drop a leading qualifier ('Less than', 'Fewer than', 'Well short of') before an undetected quantity word (plurality, quintet, quorum), so a changed quantity is shown unquoted in the Brain's words

## Integration

```
null
```

## Blocker

```
{
 "at": "2026-10-11T10:27:04Z",
 "kind": "RETRY_LIMIT",
 "needs": "owner or a more capable implementer",
 "reason": "still failing after 3 repairs (diagnosed: R3-01: the candidate regex _BARE (uri_web/untrusted.py:64, unchanged since f370064) only accepts a top-level label of 2-24 letters ([^\\W\\d_]{2,24}) and forbids a hyphen or word character after it ((?![\\w-])). A punycode/ACE TLD such as 'xn--p1ai' (digits and hyphens) never produces a match, so _is_d): R1-01",
 "stage": "AUDITING"
}
```
