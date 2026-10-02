"""Exact-file frozen-scope allowlist for the desktop recovery / Edge-first work.

Authority: User (Chetan), 2026-10-01 18:21 UTC ("APPROVED - Narrow Desktop
Allowlist Amendment") and 18:24 UTC in the desktop-recovery thread ("Approved:
edit the allowlisted uri_core/uri_ui files and the three frozen-scope guard
tests for the desktop Edge-first work"). Record and per-file justification:
docs/plans/DESKTOP_RECOVERY_ALLOWLIST.md.

Each entry is an exact path pinned to one git blob id (what `git hash-object`
computes, so a CRLF checkout of the same content matches). A path not listed,
or a listed path whose content differs from its pin, is NOT authorized and the
frozen-scope guards keep reporting it. This module's own content is pinned by
blob in tests/test_m37_edge_resolution.py and tests/test_m39_boundaries.py.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

DESKTOP_RECOVERY_FILES = {
    "uri_core/app/server.py": "5e71b77fedb2601fc0889ffa836d4fb1519459d9",
    "uri_core/core/response_validation.py": "35d1a790f187f4f487bc91483a553670b87ebade",
    "uri_ui/lib/models/uri_turn.dart": "ed841e094f78e628e880949fab4e9026f539dcb8",
    "uri_ui/lib/services/http_uri_client.dart": "72a91d386cb52840cde8e73e8ed6d57987326fb1",
    "uri_ui/lib/widgets/turn_card.dart": "f0a212a47d9392e7da5610eca11dc8ed4e7e19c7",
    "uri_ui/test/chat_lifecycle_test.dart": "e372b0a8edd41d862402d5c8f1d6a69e0ff9b2ad",
    "uri_ui/test/desktop_recovery_failure_reason_test.dart": "2e927dd214a761d53c628c706282a7805fb3dc74",
}


def is_desktop_recovery_edit(root: Path, path: str) -> bool:
    """True only for a listed path whose working-tree content matches its pin."""
    expected = DESKTOP_RECOVERY_FILES.get(path)
    if expected is None or ".." in path.split("/") or not (Path(root) / path).is_file():
        return False
    blob = subprocess.check_output(["git", "hash-object", "--", path], cwd=root, text=True).strip()
    return blob == expected
