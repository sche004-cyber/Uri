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
    "uri_core/core/model_reasoning_adapter.py": "a42f3d247cf0bad95943e2cc914c7f9a5a426217",
    "uri_core/core/decision_engine.py": "e02c9a533cb95a09cd41ae8729e3080c1ac42823",
    "uri_core/core/capability_feasibility.py": "5159100a4c4ace884decfd135196220611066d86",
    "uri_core/core/canonical_execution.py": "24e8fd7fa659be7cc5857e76224944313a4f71f8",
    "uri_core/core/tool_schema.py": "9c0957428d1a4473c4e25d68de1fb23fcb70ca39",
    "uri_core/tools/google_workspace_create.py": "c99f7d26bb7df2bd90c979be41e07b70af43ce68",
    "uri_core/app/server.py": "344a59b3a3d956d652ee1d2dea9818cd3023ade9",
    "uri_core/capabilities/gmail/capability.py": "c99b45a719a7e791dc854e991e5af34bd64fc7e2",
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
