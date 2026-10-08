# URI GitHub Publication — Final Integration Receipt (2026-10-08)

Author of record: Claude (publication session). Every result below is `COMPLETED_WITH_RESULT` from a command run in
this session; nothing is carried over from another agent's claim.

## 0. Acceptance criteria (set before publication)

| # | Criterion | Result |
|---|---|---|
| P1 | Candidate tip is `90f3714`, working tree clean, remote is `github.com/sche004-cyber/Uri` | MET |
| P2 | Remote `integration/git-sync-20261008` is an ancestor of the candidate (fast-forward only, no force) | MET |
| P3 | Seven `accepted/*` tags resolve locally to the documented commits; no `donor/*` tag published | MET |
| P4 | Frozen Phase 1 (121 files) and accepted Phase 2 OQ `-g` (154 tree files) byte-identical at the tip | MET |
| P5 | No secrets, credentials or donor content in the published range | MET |
| P6 | Independent review of the repair applied after Codex review round 5 | DONE — one finding (section 7) |
| P7 | Fresh clone from GitHub reproduces tip, tags, frozen bytes and evidence | MET |
| P8 | No other remote branch changed; no `master`/`main` change | MET |
| P9 | This receipt is itself in a verified remote commit | see section 11 |

## 1. Publication date and repository

- Date: 2026-10-08
- Repository: `https://github.com/sche004-cyber/Uri.git`
- Pushed from: `C:\Users\cheta\Development\uri-canonical-candidate`, branch `canonical/candidate-20261008`

## 2. Local source commit and remote commit

| Item | Value |
|---|---|
| Remote branch tip before push | `f8de153b7baac2ddd22fbe0646da5356dd9be13b` (ancestor of candidate; 29 commits behind) |
| Local candidate tip | `90f37142ab0e689a65ba9182d87d9178025d41d8` |
| Remote branch tip after push | `90f37142ab0e689a65ba9182d87d9178025d41d8` (`f8de153..90f3714`, normal fast-forward) |
| Tree of `90f3714` | `311f25d492f0283dbebd22768fa5aa339811552f` (local and fresh clone equal) |

The receipt commit that adds this file is a further ordinary fast-forward on top of `90f3714`; its SHA is recorded
outside this file (a commit cannot contain its own hash) in the session's final report.

## 3. Published references

Branch: `refs/heads/integration/git-sync-20261008`.

Tags (all new on GitHub; GitHub had no tags before this push):

| Tag | Tag object | Target commit | Manifest commit |
|---|---|---|---|
| `accepted/phase1-core-freeze-31a34dcb` | `bb429f8` (annotated) | `925ad45cec887ca33f5d6b12b2247508a18ac0b7` | `925ad45` |
| `accepted/runtime-v1-freeze-20261007` | `cb1c55a` (annotated) | `f791d65ca69ec1614dafd879f2fb74d56664efd1` | `f791d65` |
| `accepted/phase2-ops-r6-9a0be52c` | `0c557e6` (annotated) | `02fa0e1564a90bbf9c32e6ce3e1047096d113e51` | `02fa0e1` |
| `accepted/phase2-closure-f-fcd0d72e` | `da35163` (annotated) | `b4a59773604f10bd87af08ef83710f3770793f92` | `b4a5977` |
| `accepted/phase2-oq-g-0b49d86d` | lightweight | `6dea2665f60e3f0265083b326ba0eeee3c3b0555` | `6dea266` |
| `accepted/m36-m38-closed-frozen-bd7c450` | `00cc1be` (annotated) | `bd7c45068ed2f75cb68c9ea60f803e61a36dd7f2` | name |
| `accepted/dynamic-planning-slice1-565eae8` | `4d05cf8` (annotated) | `565eae8be2e3896e1d8615ccf4e610e014b87a90` | name |

The first five targets are ancestors of `90f3714`. `bd7c450` and `565eae8` are not; they were already on GitHub
before this push (reachable from `origin/claude/dynamic-planning-slice1-2eemmh` and others), so the tags add no new
history. `donor/desktop-mainline-eb73693` and `donor/dictation-f1e13e9` were not pushed; GitHub has zero
`donor/*` tags, and neither donor commit is in the history of `90f3714`.

## 4. Fresh-clone verification

Clone: `git -c core.longpaths=true clone --branch integration/git-sync-20261008` into
`C:\Users\cheta\Development\uri-verify-clone-20261008`.

- HEAD `90f37142ab0e…` equals the local candidate; `git status --porcelain` empty; `git fsck --connectivity-only` exit 0.
- All seven tags in the clone resolve to the commits in section 3 (7/7 OK).
- `tests/consolidation/test_runtime_authority_check.py`: 66 passed (same as the local candidate).
- Evidence present: `docs/evidence/consolidation/chain_cons2/` (31 entries),
  `docs/evidence/consolidation/inference_repro_20261008/runtime_hashes.json`,
  `docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json`, all consolidation governance documents.
  Working-copy bytes differ from the candidate only by CRLF, because the clone inherits the system
  `core.autocrlf=true`; the tree hashes are identical, so Git content is identical.
- A first clone into a deep scratch path without `core.longpaths` failed checkout (2,916 files not written). This is
  a Windows path-length limit of that location, not a repository defect; the runbook already sets `core.longpaths`.

Runtime materialization (runbook section 1, from GitHub, into the temporary directory
`C:\Users\cheta\Development\uri-verify-runtime-20261008`, not the live runtime path):

- ancestor guard `git merge-base --is-ancestor 759d0d4 FETCH_HEAD`: exit 0;
- 273 overlay paths updated from `759d0d4`; HEAD stays `e8e3b65259c45fc823addc3ef8969425a265bd1b`.

## 5. Frozen-file integrity

| Check | Result |
|---|---|
| Phase 1 zip `final-closure-20261005-phase1.zip` (local disk copy in `uri-canonical-runtime-candidate\work\c1\checkpoints\`) | SHA-256 `31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7` — matches pin |
| 121 frozen Phase 1 files vs blobs at `90f3714` (candidate and fresh clone) | 121/121 identical (zip members `GIT_DIFF.patch`, `GIT_HEAD.txt`, `GIT_STATUS.txt` are checkpoint metadata, not tree files) |
| Same 121 files vs `925ad45` at the tip (`git diff 925ad45 90f3714 -- <files>`) | empty |
| 121 frozen files on the materialized runtime disk (`git hash-object` vs `925ad45` blobs) | 121/121 identical |
| Phase 2 OQ zip `docs/evidence/phase2/phase2oq-candidate-20261008-g.zip` | SHA-256 `0b49d86d89b26d3332fcbfbc9b4b7b981cdc1075d5dc295588a5cef92a82c4cd` — matches pin |
| 481 OQ `MANIFEST.json` entries vs `90f3714` (tree + evidence under `docs/evidence/phase2/`) | 478 identical; 3 = documented post-acceptance records (`PHASE2OQ_REPORT.md`, `PHASE2CLOSE_CLOSURE_CHECKLIST.md`, `URI_DEVELOPMENT_TODO.md`, identical at `6dea266`); 0 mismatches |
| 154 OQ tree files on the materialized runtime disk | 151 identical + the same 3 post-acceptance records; 0 mismatches |
| Code paths changed after `6dea266` up to `90f3714` (outside `docs/`, `model_lab/evidence/`) | none |

## 6. Security and secret scan

Scope: the 29 commits `f8de153..90f3714` (the only new commits; the tags add none) and all 27 evidence zips.

- Added lines scanned for Anthropic/OpenAI keys, AWS keys, GitHub tokens/PATs, Slack tokens, Google API keys,
  private-key blocks and `api_key/password/secret/bearer = <value>` patterns: 0 hits.
- Every member of every `docs/evidence/phase2/*.zip` scanned for the same patterns plus `access_token`/
  `refresh_token` JSON values, and for `.env`, `auth.json`, credentials, `id_rsa`, `.pem`, `.key` file names: 0 hits.
- New path names scanned for `.env`, secret, credential, token, key files, `donor`, `quarantine`: only
  `URI_CLEANUP_AND_QUARANTINE_MANIFEST.md` (a governance document) matched.
- Largest new blobs are the Phase 2 OQ evidence zips (≤ 2.1 MB); no model weights, executables or databases.
- All 29 commits have the single author identity of this repository.

## 7. Independent review of the final repair

Reviewed state: `7b320be..90f3714` (Codex round 5 reviewed `7b320be`). Two files changed:
`URI_CONSOLIDATION_FINAL_AUDIT_20261008.md` (review history, publication status) and
`URI_RUNTIME_BUILD_AND_ROLLBACK_RUNBOOK.md` (verification step 3).

- Audit report changes: consistent with the repository (round table matches commit history; section 6 correctly
  said NOT PUBLISHED at the time; owner commands in section 6 are exactly the commands executed here). No
  overclaim found. Its section 6 status is superseded by this receipt; the audit report is left unchanged as history.
- Runbook claim "Git holds those files (not the zip) at `925ad45`": verified — `git ls-tree` of the tip has no
  Phase 1 zip, and `925ad45` changes exactly 121 files.
- **Finding RCPT-1 (Medium, documentation; does not affect accepted bytes).** Runbook step 3 says
  `git diff --stat 925ad45 -- $(git diff --name-only 925ad45^ 925ad45)` "must be empty for the overlay". On the
  materialized checkout it is not empty: it lists 110 files as deleted (19,804 deletions), because 110 of the 121
  frozen files are untracked at `e8e3b65` (they exist only as overlay files after `git reset`), and `git diff
  <commit>` ignores untracked files. All 121 files are on disk and byte-identical to `925ad45`. A correct check is:

  ```powershell
  $f = git diff --name-only 925ad45^ 925ad45
  $bad = $f | Where-Object { (git hash-object -- $_) -ne (git rev-parse "925ad45:$_") }
  if ($bad) { throw "frozen mismatch: $bad" }   # 0 mismatches expected
  ```

  The runbook was not edited in this session (publication scope only); the correction is recorded here for the
  owner to apply in a later reviewed change.

## 8. Remaining limitations

- RCPT-1 above (runbook step 3 command is unusable as written).
- `accepted/phase2-oq-g-0b49d86d` is a lightweight tag; the other six are annotated. Both resolve correctly.
- GitHub has no `master` or `main` branch, before or after this push; the remote default `HEAD` points at
  `claude/edge-harness-minimum-0oj7fe` (`610c8f8`). Unchanged by this session; a default-branch decision stays
  with the owner (`URI_CANONICAL_BRANCH_DECISION.md`).
- No Codex review of this receipt or of RCPT-1 (the `codex` MCP server failed to connect in this session).
- Limitations listed in `URI_CONSOLIDATION_FINAL_AUDIT_20261008.md` section 7 still apply (venv clean install,
  L/RH suites not rerun, Runtime v1 never Codex-audited, no physical acceptance, C7 gate 5 `/ask` NOT MET).

## 9. Actions explicitly not performed

No force push; no history rewrite; no branch or tag deletion; no `donor/*` tag push; no merge into or creation of
`master`/`main`; no change to frozen Phase 1 or accepted Phase 2 files; no change to the legacy `\URIServer` task,
startup tasks, shortcuts, ports or runtime configuration; no activation of the new Core, Supervisor or Brain; no
cutover; no new milestone. The two temporary verification directories were created under
`C:\Users\cheta\Development\` and are not runtime locations.

Remote branch audit: all 40 `refs/heads/*` on GitHub after the push equal their pre-push values except
`integration/git-sync-20261008` (`f8de153` → `90f3714`, then the receipt commit).

## 10. Final verdict

**PUBLISHED WITH FINDINGS.** The accepted candidate `90f3714` and all seven accepted tags are on GitHub without
history rewrite, and a fresh clone reproduces the tip, tags, frozen Phase 1 bytes, accepted Phase 2 OQ bytes and
evidence. The one finding (RCPT-1) is a defective verification command in the runbook; it does not change any
published byte.

## 11. Receipt commit

This file is committed as one ordinary fast-forward commit on `integration/git-sync-20261008` (parent `90f3714`)
and re-verified on GitHub after the push; the resulting SHA is reported in the session's final report.
