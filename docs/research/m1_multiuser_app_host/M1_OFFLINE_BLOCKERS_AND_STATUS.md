# M1 offline blockers and status

The owner's Windows PC is offline. This document records what was verified in the cloud, what is deferred to the PC,
and the status of each research deliverable.

## 1. Verified in the cloud (`COMPLETED_WITH_RESULT` only)

| Run | Result | Record |
|---|---|---|
| Line A multi-user, auth and isolation suites + A2UI + harness boundary | 315 passed, 0 failed | `evidence/CLOUD_TEST_EVIDENCE.md` Run 1 |
| `tests/scheduler` | 56 passed, 15 skipped | Run 2 |
| SSRF probe against `fetch_url` | Loopback page fetched directly and through a redirect (defect SSRF-1) | Run 3 |

**Not claimed:**
- `tests/ws`, `tests/oi` and `tests/phase2a` fail in the cloud mainly on `msvcrt` and `WINDOWS_REQUIRED`. That is
  neither a pass nor a defect.
- No hardware, Windows, GPU, login or Flutter result is claimed.

## 2. Deferred verification (needs the physical PC)

| # | Item | Blocks |
|---|---|---|
| V-1 | Canonical tip vs PC-local work; TIWS push record and staging receipt | Every slice (P0-1) |
| V-2 | Windows suites: phase1 chain, `tests/ws`, `tests/oi`, `tests/phase2*`, frozen check with the checkpoint zip | Integration of any slice |
| V-3 | SAFE-1, the unexplained whole-PC hangs: investigate or accept | Serving other users |
| V-4 | Runtime v1 behind Line A: tool calling, timeouts, decode with three users, p95 queue wait | P1-3 |
| V-5 | Tailscale install, ACLs, TLS certificate, remote device login | P1-4 |
| V-6 | Windows accounts per user, NTFS ACLs, Job limits, firewall-per-account | P1-6, P2-6, P5-2 |
| V-7 | Native harness logins per user (each user, themselves) | P1-6 |
| V-8 | Google consent per user, publishing status, Calendar | P1-7, P2-8 |
| V-9 | Flutter builds: gateway client, folder picker, storage surfaces, app surfaces | P1-8, P2-4, P2-5 |
| V-10 | Client-side Playwright browser worker on Windows | P4-2 |
| V-11 | faster-whisper transcription throughput on CPU; GPU coexistence with the Brain | P3-5 |
| V-12 | Windows path APIs (`GetFinalPathNameByHandleW`, reparse attributes) on the installed Python | P2-1 Windows path |

## 3. External blockers (not PC-related)

| Item | Blocks |
|---|---|
| Reddit API approval | P3-6 |
| Meta App Review + business verification; LinkedIn partner approval | P6-3 |
| Owner-paid keys: Tavily (exists), YouTube Data API, X credits | P3-2, P3-5, P6-2 |

## 4. Owner decisions pending

| ID | Decision |
|---|---|
| D-1 | Line A as the front door |
| D-2 | Authorize the frozen repair scope (P1-5, P2-3, P1-6, P1-7, P2-8) |
| D-3 | Tailscale vs Headscale vs WireGuard |
| D-4a | Hosted Claude Code for household users: is it under the consumer or the commercial terms? |
| D-4b | Whether `CLAUDE_CODE_OAUTH_TOKEN` forwarding stays, and whether URI may show a CLI's own login URL |
| D-5 | Google OAuth publishing status |
| D-6 | Job limits: a frozen change or a wrapper |
| D-7 | Client secure token storage (a new Flutter dependency) |
| D-8 | Harness access for non-owner users before P1-6 |
| D-9 | Server-side storage roots vs the "client owns content" rule |
| D-10 | Enable X pay-per-use spend |
| D-11 | Apply for Reddit API access |

## 5. Deliverable status

| Deliverable | Status |
|---|---|
| The 12 required reports | Written; committed on `research/m1-multiuser-app-host` |
| Implementation | **Not started.** Not authorized. |
| Canonical branches | Untouched |
