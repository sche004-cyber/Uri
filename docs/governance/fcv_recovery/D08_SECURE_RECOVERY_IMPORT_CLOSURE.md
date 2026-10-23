# D08 — secure recovery tree cannot import `uri_web` (AP-6 / OPEN-06)

Owner directive DEC-103 (2026-10-23), AP-6: investigate the secure-rollback `uri_web` import failure without weakening
frozen-core or security protections.

## Root cause (reproduced on canonical `c036a901`)

`scripts/fcv_guarded_rollback.py --secure-recovery` restores the Phase 1 checkpoint
(`final-closure-20261005-phase1.zip`, 124 files, no `uri_web/`) and installs the owner-approved secure
`uri_core/tools/fetch_url.py` (`404e6092…`, SSRF-1/IDN-1b). That secure version imports `uri_web.netpolicy`,
`uri_web.records` and `uri_web.safe_fetch`; `uri_web` was added later (`885483b1`, 2026-10-10). In the recovered tree
`import uri_core.tools.fetch_url` fails with `ModuleNotFoundError: No module named 'uri_web'`.

## Repair (non-frozen; only `scripts/fcv_guarded_rollback.py` and its test)

- `SUPPORT_FILES`: the full import closure of the secure `fetch_url.py` inside URI (`uri_web/__init__.py`,
  `netpolicy.py`, `records.py`, `safe_fetch.py`; computed with `ast`, no other URI module), pinned by SHA-256 and read
  from pinned canonical commit `c036a901`.
- Secure recovery reads and checks the closure **before** the frozen tool writes anything; a changed pin or an
  unavailable commit refuses (`SUPPORT_FILES_UNAVAILABLE`) with nothing written.
- After the two security transitions, the closure is written only where the restored tree has no such file
  (`SUPPORT_FILE_CONFLICT` otherwise); any failure removes the security files and the partial closure, as before.
- `secure-recovery-evidence.json` records the support files, their hashes and source commit.

Unchanged: the frozen rollback tool (`scripts/phase1_offline_rollback.py`, FCV-01 exact blob), the owner authority
record and its two approved security blobs, the security patch, the default refusal and `--inspect`. No protected path
changes (`ws_frozen_check` exit 0).

## Owner decision needed before canonical integration

Secure recovery would now install four non-security files in addition to the two owner-approved blobs. P0 notes (DEC-103
AP-6 gate) that changing the set of files the secure recovery installs needs an owner exception. Alternatives: approve
this repair, or keep D08 as a documented limitation (the recovered tree is an offline source rehearsal that is never
started).

## Residual

`uri_web/safe_fetch.py` needs `httpx` (and `httpcore`) in the environment. Neither the Phase 1 `requirements.txt` nor
canonical `requirements.txt` declares `httpx` directly (it arrives transitively); recorded as finding HTTPX-DECL-1
(LOW), not changed here.

## Evidence

`tests/governance/test_fcv11_guarded_rollback.py`: 14 passed (11 existing, one updated for the support files, 3 new),
including a subprocess import of `uri_core.tools.fetch_url` in the recovered tree.
