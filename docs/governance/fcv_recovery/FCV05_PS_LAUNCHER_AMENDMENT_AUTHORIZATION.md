# FCV-05: owner-authorized amendment to the frozen PowerShell client wrapper

**Decision:** OWNER-FCV05-20261015. The owner chose "Authorize amendment" on 2026-10-15 at 07:35 +05:30, in the FCV recovery milestone.

**File:** `scripts/uri_client.ps1` is one of the 121 frozen Phase 1 files.

| | SHA-256 |
|---|---|
| Frozen | `c8401bc06caa2fdd82838d69e9a93698bd19d741296f596b38ac6929e0409404` |
| Authorized amendment | `3a01127775a6075a5a971fc63944ef4ce7d8fb3f62af8f1866553587ecd3e34e` |

## Root cause (reproduced)

Under a UTF-8 console code page (65001), Windows PowerShell 5.1 creates `Process.StandardInput` with the console's UTF-8 encoding. Its preamble, `EF BB BF`, is written before the first byte the bridge copies. The client worker reads that as a frame header and refuses with `FRAME_LIMIT`, which surfaces as `CLIENT_WORKER_REFUSED`.

| Evidence | Result |
|---|---|
| Byte probe | First bytes `41424344` under code page 437; `efbbbf41424344` under 65001 |
| Test | `test_c3_client_worker.py::test_windows_powershell_client_launcher_preserves_binary_frames` passes under 437 and fails under 65001 |
| Worker trace | `FRAME_LIMIT` at `read_frame` |

## Change

The writer is created while `[Console]::InputEncoding` is a UTF-8 encoding without a preamble. The console encoding is then restored in a `finally` block. Nothing else changes: frame bridging, the interpreter hash check and the launch arguments are all unchanged.

Regression: `tests/governance/test_fcv05_ps_launcher_bom.py` runs the script's own bridge block under code pages 437 and 65001. It fails on the frozen bytes and passes on the amendment.

No canonical integration, deployment or cutover is authorized by this record.
