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
    "uri_core/core/capability_registry.py": "f93fdbb4e44135fd351f9938acf19c04a978a24f",
    "uri_core/tools/generate_document.py": "ee34797dd73751be2e66d392e62d634c9f371f9f",
    "uri_core/services/office_document_writer.py": "7c346c63aa000f24a948f71485bb7296ba6a9e7d",
    "uri_core/core/response_drafting.py": "2c258958b3a8e5403b5410675dd59dc0fcf085f0",
    "uri_core/core/model_reasoning_adapter.py": "6881e2b382b03d8cffd49b11f352600b12485e8e",
    "uri_core/core/decision_engine.py": "be75c89874245886eda93d87912ad1b36521e1b0",
    "uri_core/core/capability_feasibility.py": "dc4d118b498d7d40d457b1e56cca154720daace8",
    "uri_core/core/canonical_execution.py": "bb572c59a2ec75a11f4ebf7ab3a0667e4539fb09",
    "uri_core/core/tool_schema.py": "6af67ef7e8074d33d31a887a829774dae668f104",
    "uri_core/tools/google_workspace_create.py": "c99f7d26bb7df2bd90c979be41e07b70af43ce68",
    "uri_core/app/server.py": "344a59b3a3d956d652ee1d2dea9818cd3023ade9",
    "uri_core/capabilities/gmail/capability.py": "68e9b39b886b11cfdee3c2650476c5edb0b1e709",
    "uri_core/services/gmail_service.py": "3829624e12dc3a6fe91da9bf0e4c45b082e374e9",
    "uri_core/services/google_errors.py": "0dd06f6344c14e6039a21e45e358fda088f22082",
    "uri_core/tools/drive_search.py": "983f969690b7c938c021befa886c1fbf75d2d4b5",
    "uri_core/tools/drive_upload.py": "958cde8e4be450fe9568f161f109ac9301995b04",
    "uri_core/core/response_validation.py": "35d1a790f187f4f487bc91483a553670b87ebade",
    "uri_ui/lib/models/uri_turn.dart": "ed841e094f78e628e880949fab4e9026f539dcb8",
    "uri_ui/lib/screens/connections/connections_screen.dart": "57a1cda03ba2fbcb25b56b0bd7af432824244864",
    "uri_ui/lib/screens/connections/google_setup_card.dart": "f018f9a124382ccf255bb808e001482dcace376a",
    "uri_ui/lib/services/app_state.dart": "233dce56cc9f6db71785940ea3ac54c05bfda367",
    "uri_ui/lib/services/http_uri_client.dart": "e8d908777193b65fa79f7d7f2e55f3c8459a1900",
    "uri_ui/lib/services/mock_uri_client.dart": "9f2faa339cd1a31dfb412619e4ae8e22ed68b679",
    "uri_ui/lib/services/uri_client.dart": "59d9a044f8041bf36ca7383004224fc9df0bb018",
    "uri_ui/test/google_setup_card_test.dart": "d42c1a0d50e0276306e99fe6c2c3d22ee87aba1b",
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
