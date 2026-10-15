# FCV-11: guarded Phase 1 rollback

**Finding.** Rolling back to the accepted Phase 1 checkpoint (`final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb…98cf7`) restores two security files without their fixes, and the frozen tool gives no warning:

| File | Restored version | Comes from | Missing fix | Owner-approved secure version |
|---|---|---|---|---|
| `uri_core/app/server.py` | `7b455f05…` | the checkpoint | GRAPHIFY-LEAK-1 | `59cfde59…` |
| `uri_core/tools/fetch_url.py` | `f0970062…` | the `e8e3b65` base | SSRF-1, IDN-1b | `404e6092…` |

The `e8e3b65` base `server.py` (`404aad61…`) also lacks the fix. A checkpoint without `server.py` would restore that version.

## Procedure

Use `scripts/fcv_guarded_rollback.py`. Do not call `scripts/phase1_offline_rollback.py` directly.

| Command | What happens |
|---|---|
| `--inspect` | Reports the version and state (SECURE, VULNERABLE or UNKNOWN) of each security file the restored tree would hold. Writes nothing. Exit code 3 when unsafe. |
| default | Refuses (exit code 2, `UNSAFE_ROLLBACK_REFUSED`) when any security file is not the approved secure version. Prints which files, which fix is missing, and the secure procedure. Writes nothing. |
| `--secure-recovery` | Approval-gated, see below. |

### Secure recovery: approval gate

Secure recovery runs only when every one of these holds:

1. The operator passes `--secure-recovery` explicitly.
2. The owner authority record `docs/governance/windows_restoration/OWNER_RUNTIME_AUTHORIZATION.json` (decision `OWNER_WINDOWS_RESTORATION_20261014`) names:
   - this exact checkpoint hash;
   - the base `e8e3b65`;
   - the security patch hash `ba9249da…`;
   - the two approved secure versions.

   Any other checkpoint is refused with `SECURE_RECOVERY_NOT_AUTHORIZED`.
3. The patch file still has hash `ba9249da…`.
4. The restored security files are exactly the patch's before-versions.

Every check, and the patch application, completes before anything is written:

1. The patch is applied outside any repository, with CRLF conversion disabled. Each result must equal the approved secure version.
2. The frozen tool then restores the checkpoint unchanged.
3. The two files are replaced with the verified secure versions.
4. `secure-recovery-evidence.json` records the before and after hashes.

If replacing a file fails, both security files are deleted from the restored tree, so a vulnerable version is never left in place.

## What does not change

- The checkpoint archive is never modified. The tests re-hash it.
- The frozen rollback tool (`50f8540d…`, FCV-01) is unchanged. No frozen file or frozen test changes, so this needs no new owner authorization.

## Residual risk

Calling the frozen tool directly still restores the vulnerable versions without a warning. Making the frozen tool itself refuse by default would change:

- a frozen file;
- three frozen positive rollback tests. Every rehearsal restores the base `fetch_url.py`.

Both changes need separate owner authorization. Until then, the runbook (`docs/governance/consolidation/URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md` section 4) points only to the guarded procedure.

The restored tree is an offline source rehearsal. Restoring it does not start, deploy or cut over anything.
