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
    "uri_core/core/approval_gate.py": "ea9cc67fa0413466abfc75229119641764dc7e6a",
    "uri_core/core/approval_store.py": "6af7c06d6906c9879f140c0fc059cf3663ef552c",
    "uri_core/core/native_tool_loop.py": "67abf3b604d49569477c9c267e0eb1bdae99c8ca",
    "uri_core/core/approval_resumption.py": "18fcea6a5a447bede3ac89bfa75917ff1eea1b69",
    "uri_core/core/multi_action_dispatch.py": "292b4367916df9b7f3dd4d75125214066268fac1",
    "uri_core/core/capability_registry.py": "f93fdbb4e44135fd351f9938acf19c04a978a24f",
    "uri_core/tools/generate_document.py": "2b7c44cb810ffc12d04f569f1e780b87749a307d",
    "uri_core/services/office_document_writer.py": "30d04e0cce971db9cee6ecc4cb2c930f976f76ec",
    "uri_core/core/response_drafting.py": "2c258958b3a8e5403b5410675dd59dc0fcf085f0",
    "uri_core/core/model_reasoning_adapter.py": "6881e2b382b03d8cffd49b11f352600b12485e8e",
    "uri_core/core/decision_engine.py": "e833ce43a3f91efb2c60fafa6dadbb5e77677a2b",
    "uri_core/core/capability_feasibility.py": "dc4d118b498d7d40d457b1e56cca154720daace8",
    "uri_core/core/canonical_execution.py": "0f56b47689e9e5ce00d0a67e7a2c4ce5be440b33",
    "uri_core/core/tool_schema.py": "406eaf9d158a7aa0c71db7d004f31a948a115d25",
    "uri_core/tools/google_workspace_create.py": "c99f7d26bb7df2bd90c979be41e07b70af43ce68",
    "uri_core/app/server.py": "f0749d222e9f4c057bfda318818caf0729a5ac7e",
    "uri_core/capabilities/gmail/capability.py": "68e9b39b886b11cfdee3c2650476c5edb0b1e709",
    "uri_core/services/gmail_service.py": "3829624e12dc3a6fe91da9bf0e4c45b082e374e9",
    "uri_core/services/google_errors.py": "0dd06f6344c14e6039a21e45e358fda088f22082",
    "uri_core/tools/drive_search.py": "983f969690b7c938c021befa886c1fbf75d2d4b5",
    "uri_core/tools/drive_upload.py": "958cde8e4be450fe9568f161f109ac9301995b04",
    "uri_core/core/response_validation.py": "35d1a790f187f4f487bc91483a553670b87ebade",
    "uri_ui/lib/models/uri_turn.dart": "1ce102e14ccdd2fe3e3c948abc9476e41ce3dbe8",
    "uri_ui/lib/screens/connections/connections_screen.dart": "57a1cda03ba2fbcb25b56b0bd7af432824244864",
    "uri_ui/lib/screens/connections/google_setup_card.dart": "f018f9a124382ccf255bb808e001482dcace376a",
    "uri_ui/lib/services/app_state.dart": "8567e64e891f3d02c46355f67e81311866d08c57",
    "uri_ui/lib/services/http_uri_client.dart": "db2bbdf4c32dbe76ae91d2d69c276732af3304ce",
    "uri_ui/lib/services/mock_uri_client.dart": "c2bfdad1120c5fd332cdb3c4b2df4be88d118c7b",
    "uri_ui/lib/services/uri_client.dart": "59ffc33dfbad6e84895f4639091eea4b4f945739",
    "uri_ui/test/google_setup_card_test.dart": "d42c1a0d50e0276306e99fe6c2c3d22ee87aba1b",
    "uri_ui/lib/screens/ask/ask_uri_screen.dart": "37b286ef8eca182e3e2f0e17f3f33048c83e09e7",
    "uri_ui/lib/widgets/clarification_card.dart": "fce4985826d8ae8eb9f5e0d185b4c4dd9c47be54",
    "uri_ui/lib/models/clarification.dart": "41dc43cdcf78d1998b1afd27425efa36047bbf9e",
    "uri_ui/lib/widgets/status_pill.dart": "258bd1f582f479d9d0e71f20647c73de8cecdae5",
    "uri_ui/test/int_arn_1_clarification_test.dart": "4cab50c70a441e507a70ccc0947f9eca7b3e4ee7",
    "uri_ui/lib/widgets/turn_card.dart": "f3b1a17dbf10e4432146a46c6dcefc37ffd0aee4",
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
