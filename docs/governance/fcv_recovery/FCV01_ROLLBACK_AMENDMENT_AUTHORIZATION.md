# FCV-01: owner-authorized amendment to the frozen offline rollback

**Decision:** OWNER-FCV01-20261014. The owner chose "Authorize amendment" on 2026-10-14 at 23:47 +05:30, in the FCV recovery milestone.

**File:** `scripts/phase1_offline_rollback.py` is one of the 121 frozen Phase 1 files.

| | SHA-256 |
|---|---|
| Frozen (tag `accepted/phase1-core-freeze-31a34dcb`) | `d0a369b01926cc433ef2415ed97753673d40c94b954df65192d8977b58f65ba0` |
| Authorized amendment | `50f8540da21f0a3f812bf5e807129ef7eb6f805767c91c980b28c4b67498d70e` |

## Why

C7 gate 8 (`docs/plans/C7_CUTOVER_REQUIREMENTS.md`) requires an offline rollback rehearsal from the exact frozen checkpoint: `final-closure-20261005-phase1.zip`, SHA-256 `31a34dcb…98cf7`. The frozen tool refused that archive with `SOURCE_ONLY_ARCHIVE_REQUIRED`, because the archive also holds:

- the five frozen C6 Dart sources;
- three Git provenance members.

A derived Python-only archive was rejected for two reasons:

1. It is not the exact archive.
2. It drops 5 of the 121 frozen files.

## What changes, exactly

- **The five frozen C6 Dart files.** These exact paths are restorable source:
  - `uri_ui/lib/screens/settings/paired_runtime_screen.dart`
  - `uri_ui/lib/screens/settings/settings_shell.dart`
  - `uri_ui/lib/services/paired_runtime.dart`
  - `uri_ui/test/paired_runtime_live_test.dart`
  - `uri_ui/test/paired_runtime_screen_test.dart`

  Any other `uri_ui` path, `.dart` file or case variant is still refused.
- **The three Git provenance members.** `GIT_HEAD.txt`, `GIT_STATUS.txt` and `GIT_DIFF.patch` at the archive root are checkpoint metadata, under these rules:
  - All three must be present, or none.
  - `GIT_HEAD.txt` must be exactly the accepted base commit followed by a newline.
  - They are verified and their hashes are recorded in the rollback evidence. They are never written into the restored tree.

## What does not change

No existing check is relaxed:

- the archive hash;
- the checkpoint scope;
- the size, member-count and expansion limits;
- traversal, symlink, Windows-alias and duplicate refusal;
- the fresh destination and its ACL;
- catalogue authority;
- the compile check;
- the final re-hash of the restored tree.

## Known consequences

- A rollback to the frozen checkpoint restores the pre-security `uri_core/tools/fetch_url.py` and `uri_core/app/server.py`, because that is what the checkpoint holds (finding FCV-11). Any use of a restored tree beyond rehearsal must re-apply `docs/governance/windows_restoration/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch`.
- The historical runtime materialization (e8e3b65 plus overlay) keeps the original frozen rollback script. That script is not used to serve requests. The rehearsal runs from the source candidate.

No canonical integration, deployment or cutover is authorized by this record.
