# DEV-LIFECYCLE-2 — integration receipt (2026-10-11)

**Integrated:** `integration/git-sync-20261008` on `github.com/sche004-cyber/Uri` fast-forwarded
`ce1a90c046d2e9566a86d8dccf25df0e2bc98c80` → `cbdf3f2ceb5eea4e8b634f92c8e3dee4571a3b35`, verified with
`git ls-remote` before (tip = `ce1a90c`) and after (tip = `cbdf3f2c`). Authority: owner decision D1 (2026-10-11,
conditional canonical integration after independent ACCEPT on the exact commit, blocking findings resolved,
provenance, frozen-file integrity and combined gates). Production deployment and cutover are not part of this.

This file is on branch `receipts/dev-lifecycle-2-20261011` (one commit on `cbdf3f2c`), not on canonical.

## Candidate and provenance

| Commit | Content | Author route |
|---|---|---|
| `f3706e03` | F1-F3, L1, L3: Windows Job Object containment, no POSIX-only crash, canonical remote by URL | cloud development session |
| `73bdbef1` | W-1..W-3 from the first Windows gate: `/` test paths, reviewer identity behind `.cmd` launchers, portable tests | owner-PC coordinator (W-findings found on the PC) |
| `0ee6885a` | r2 R1-01: Windows `precheck()` fail-closed when a job was not created/verified | lifecycle driver, separate implementer process |
| `cbdf3f2c` | r2 R1-02 (cmd.exe/.bat launcher refused, `%*` on the launch line), R1-03 (W-2 tests fail on `ce1a90c` on Linux too), R1-04 (ledger/doc wording), R2-01 (OSError path) | lifecycle driver, separate implementer process |

The candidate was taken from `lifecycle-checkpoint/milestones.bundle` at `ccr-cab5ed06-9hwyc4` commit `92929dac`
(`git bundle verify` ok; ref `milestone/dev-lifecycle-2-20261011` = `cbdf3f2c`; `ce1a90c` and `73bdbef1` are
ancestors). **Correction recorded:** the later checkpoint `38037759` (W1/A0 run) had rewritten that bundle with the
stale ref `f3706e03`; the cloud coordinator restored `cbdf3f2c` in `3a0d9ed0` and confirmed no other ref moved back.

## Independent review (lifecycle driver, Linux cloud)

| Run | Round | Reviewer | Candidate | Verdict |
|---|---|---|---|---|
| DEV-LIFECYCLE-2-r2 | R1 | `claude_cli` session `4ea43b42-633b-46ea-8a8a-09ef2c55de7f` | `73bdbef1` | REJECT (R1-01 HIGH blocking; R1-02..R1-05 LOW) |
| DEV-LIFECYCLE-2-r3 | R1 | relay of the owner decision (imported, never evidence) | `0ee6885a` | REJECT (routes LOW R1-02..R1-04 to repair) |
| DEV-LIFECYCLE-2-r3 | R2 | `claude_cli` session `e5872d00-ff46-43ed-afe1-343fff3ccfd1`, independent | `cbdf3f2c` | **ACCEPT WITH FINDINGS** |

Driver receipt: `lifecycle-checkpoint/lifecycle-runs/DEV-LIFECYCLE-2-r3/receipt.json` at `92929dac` (git blob
`8f04bdaa2ed14ecdbb3d8232f974aaa5d9aacc06`); stage VERIFIED, `chain OK` as reported by the driver, integration
`AWAITING_OWNER_AUTHORIZATION` with `authorized: false` (the owner-PC coordinator performed the push under D1).
**Not independently re-verified here:** the driver's hash chain (`lifecycle verify`) was not re-run on the PC; its
state paths are the cloud container's.

Owner decisions during the milestone: plan A (PC repairs W-1..W-3, cloud W-repair `fcc0ebdd` superseded and never
merged); route LOW r2.R1-02, R1-03, R1-04 to repair, R1-05 a documented limitation (owner "Yes", 2026-10-11).

## Gates

| Platform | Commit | Result | Evidence |
|---|---|---|---|
| Linux (cloud, driver qualification) | `cbdf3f2c` | 238 passed, 5 platform-gated (`windows_only`), no new failure vs `ce1a90c` | driver receipt |
| Windows 11, Python 3.13.15 (owner PC, clean detached checkout) | `cbdf3f2c` | **238 passed, 0 failed, 0 errors**, 5 platform-gated (`linux_only`, listed by name) | `evidence/dev_lifecycle_2_windows/gate_cbdf3f2c.{xml,log}` |
| Windows, history | `ce1a90c` / `f3706e03` / `73bdbef1` | 72 failed, 114 passed / 17 failed, 194 passed / 0 failed, 222 passed | `gate_ce1a90c.xml`, `gate_f3706e03.xml`, `gate_73bdbef1.xml` |

SHA-256 of the evidence files (in `docs/dev_workflow/evidence/dev_lifecycle_2_windows/`):

```
58ce4c609ffecf050c0221bd5e679e254d47a323ff4c1472fd22d6eabade10a8  gate_cbdf3f2c.xml
f9e7a746f2ff52eb551b03e840f2492258d541b1c9af691fe1052ba997bafdde  gate_cbdf3f2c.log
199a3ae4247c52d889e7354db1cec40003a46a38c0132c003ab0dc752c72b7a9  gate_ce1a90c.xml
4f99187427f169bca7ade4b98dc51479bc75776f130857acb0ff56f11cdfac18  gate_f3706e03.xml
8b48b58c1e9c1edf0745d861a1cbb4d1af9d450a0dfce2513c5390e236c16aee  gate_73bdbef1.xml
```

Frozen-file check (`scripts/ws_frozen_check.py`) on `cbdf3f2c`: `ok: true`, no protected path changed vs baseline.

## Open after integration

- **r3.R2-01 LOW (accepted, documented limitation):** containment cleanup covers `OSError` from `communicate()` only;
  any other exception (e.g. `UnicodeDecodeError`, a Windows reader-thread error on undecodable output) skips
  `containment.finish()`, so the job stays unterminated and untracked and the next `precheck()` reports contained.
  Effect: in that rare case a later review could be counted as contained when it was not. Not repaired here.
- **r2.R1-05 LOW (documented limitation):** `_norm_url` resolves relative paths against the cwd; a legacy
  `baseline.ref` is still chosen by remote name.
- **Windows qualification still NOT VERIFIED end to end:** no real lifecycle milestone run (DEVTEST round with a live
  `claude_cli` reviewer, `contained: true`, `is_independent` true) has run on the PC yet. The unit and integration
  tests above passed.
- **L2:** the precedence note in the older `uri-development` skill is local and untracked on the PC (by design).
- **Merge order:** W1/A0 targeted `ce1a90c`; it must now be brought onto `cbdf3f2c` and re-reviewed before it can
  integrate.
