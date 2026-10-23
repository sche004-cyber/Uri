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

## Verification of the four files (owner restriction, D08-03, 2026-10-23)

Owner decision: "APPROVED WITH RESTRICTIONS. The four additional secure-recovery files may be installed only after
their necessity, identities, destinations, hashes, and rollback behavior are verified" (owner to the Milestone
Manager session, 2026-10-23; P0 DEC-104 records both the wording given to P0 and this stricter wording).

| Path (identity) | Source blob at `c036a901` | SHA-256 (pinned in `SUPPORT_FILES`) | Bytes | Destination | Why it is needed |
|---|---|---|---|---|---|
| `uri_web/__init__.py` | `a3f00bfa519e1fc0c3e80c2e7051eb69676d0a58` | `2d9d4795d94020ea044ebda8c6c66d1ee3e511bbdc19e950aab28ed613e8107c` | 670 | `<restored tree>/uri_web/__init__.py` | package marker for the three modules below |
| `uri_web/netpolicy.py` | `bd1e1c26528e9632e7f627d5ec9169597c27bda1` | `c8b93927b6f3bf6da4b7a47275a7081be367b73b21680b09ca4d7b714eecd151` | 9065 | `<restored tree>/uri_web/netpolicy.py` | `fetch_url.py:48` `from uri_web import netpolicy` (public-address policy, SSRF-1) |
| `uri_web/records.py` | `55f523fe8e1a7b4ab7a95c3f661684cc97e929b8` | `b4be69088578e00a5c03b2dcd21dd4c87104d3b4f3d9a0630ff5afa899580cea` | 3160 | `<restored tree>/uri_web/records.py` | `fetch_url.py:49` `from uri_web import records` |
| `uri_web/safe_fetch.py` | `a905e719f17086f5690e33373b5880af089919c2` | `7e7778efac61e00b251a55eda02faf88cce7d830cd6f6faa04ab50ee19113315` | 22684 | `<restored tree>/uri_web/safe_fetch.py` | `fetch_url.py:50` `from uri_web.safe_fetch import SafeFetcher` (every hop checked) |

- **Necessity:** the closure is computed with `ast` from the secure `fetch_url.py` (`404e6092…`): exactly these four
  files, no other URI module. The recovered tree imports `uri_core.tools.fetch_url`, and the fetch tool refuses
  loopback and private addresses (review FB1 probes: `127.0.0.1`, `10.0.0.1`, `0x7f000001`, port 9).
- **How the closure was computed (review FB2 D08R2-02):**

  ```python
  import ast, subprocess
  def imports(path):  # module names imported by the file at the pinned commit
      src = subprocess.run(["git", "show", f"c036a901:{path}"], capture_output=True).stdout.decode()
      out = set()
      for n in ast.walk(ast.parse(src)):
          if isinstance(n, ast.ImportFrom) and n.module: out.add("." * n.level + n.module)
          if isinstance(n, ast.Import): out.update(a.name for a in n.names)
      return sorted(out)
  ```

  Output, URI modules and third-party network packages only: `uri_core/tools/fetch_url.py` ->
  `uri_core.services.file_extraction` (restored by the checkpoint itself), `uri_web` (`netpolicy`, `records`),
  `uri_web.safe_fetch`; `uri_web/safe_fetch.py` -> `httpcore`, `httpx` plus its sibling modules `netpolicy` and
  `records`; `uri_web/__init__.py`, `netpolicy.py`, `records.py` -> standard library only. Closure: the four files
  below. Independently reproduced by review FB2.
- **Identities and hashes:** read with `git show c036a901:<path>` and checked against the pins before anything is
  written; a changed pin or an unavailable commit refuses with nothing written (`test_d08_a_changed_support_pin_…`).
- **Destinations:** only `uri_web/` inside the recovered tree, only where no restored file exists
  (`SUPPORT_FILE_CONFLICT`, `test_d08_02_a_support_path_the_checkpoint_restored_…`).
- **Rollback behaviour:** on any failure after the frozen tool has restored the tree, the security files, every closure
  file written and every folder the closure created are removed (D08-01 repaired; `test_d08_02_a_write_failure_…`);
  no evidence file is written. The default refusal and `--inspect` are unchanged. The recovered tree is an offline
  source rehearsal; nothing is started.
- **No new dependency or privilege:** `safe_fetch.py` imports `httpx`/`httpcore`, which canonical `uri_web` already
  uses (environment: httpx 0.28.1, httpcore 1.0.9; pinned in `uri_ui/tool/voice/requirements-voice.txt`). The repair adds
  no package, no permission and no elevation; the frozen tool, the owner authority record and the security patch are
  unchanged.

## Owner decision (recorded)

D08-03 approved with the restrictions above (owner, 2026-10-23). Earlier text, kept:


Secure recovery would now install four non-security files in addition to the two owner-approved blobs. P0 notes (DEC-103
AP-6 gate) that changing the set of files the secure recovery installs needs an owner exception. Alternatives: approve
this repair, or keep D08 as a documented limitation (the recovered tree is an offline source rehearsal that is never
started).

## Residual

`uri_web/safe_fetch.py` needs `httpx` (and `httpcore`) in the environment. Neither the Phase 1 `requirements.txt` nor
canonical `requirements.txt` declares `httpx` directly (it arrives transitively); recorded as finding HTTPX-DECL-1
(LOW), not changed here.

## Evidence

`tests/governance/test_fcv11_guarded_rollback.py`: 16 passed at `c91de8aa` (11 existing, one updated for the support
files, 5 new: 3 at `4ae062cb`, 2 failure-path tests for review FB1 D08-01/D08-02),
including a subprocess import of `uri_core.tools.fetch_url` in the recovered tree.
