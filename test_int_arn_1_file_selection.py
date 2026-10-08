"""INT-ARN-1 optional file selection at the two legacy tool boundaries."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from uri_core.core.file_store import FileStore
from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
from uri_core.core.capability_registry import CapabilityRegistry
from uri_core.tools.read_attached_file import ReadAttachedFileTool
from uri_core.tools.convert_document import ConvertDocumentTool


class FileSelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = FileStore(str(Path(self.tmp.name) / "user-a"))
        self.first = self.store.save(filename="first.txt", content=b"first", session_id="s1")
        self.second = self.store.save(filename="second.txt", content=b"second", session_id="s1")
        self.other_session = self.store.save(filename="private.txt", content=b"private", session_id="s2")
        self.other_user_store = FileStore(str(Path(self.tmp.name) / "user-b"))
        self.other_user = self.other_user_store.save(
            filename="foreign.txt", content=b"foreign", session_id="s1")

    def test_read_defaults_and_selects_one(self):
        seen = []
        with patch("uri_core.tools.read_attached_file.extract_file_text",
                   side_effect=lambda path: seen.append(path) or {"status": "success", "text": "ok"}):
            default = ReadAttachedFileTool(self.store).execute(session_id="s1", file_id="")
            self.assertEqual([d["filename"] for d in default["documents"]],
                             ["second.txt", "first.txt"])
            seen.clear()
            selected = ReadAttachedFileTool(self.store).execute(session_id="s1", file_id=self.first.file_id)
        self.assertEqual([d["filename"] for d in selected["documents"]], ["first.txt"])
        self.assertEqual(seen, [self.store.path_for(self.first.file_id)])

    def test_read_rejects_foreign_unknown_and_path(self):
        tool = ReadAttachedFileTool(self.store)
        for file_id in (self.other_session.file_id, self.other_user.file_id,
                        "missing", "../private.txt"):
            with self.subTest(file_id=file_id):
                result = tool.execute(session_id="s1", file_id=file_id)
                self.assertEqual(result["status"], "invalid_attachment_context")

    def test_convert_defaults_and_selects_one(self):
        first = self.store.save(filename="first.pdf", content=b"pdf one", session_id="s1")
        second = self.store.save(filename="second.pdf", content=b"pdf two", session_id="s1")
        seen = []

        def fake_layout(source, destination):
            seen.append(source)
            Path(destination).write_bytes(b"docx")
            return {"status": "success"}

        with patch("uri_core.tools.convert_document.convert_pdf_to_docx_preserving_layout",
                   side_effect=fake_layout):
            default = ConvertDocumentTool(self.store).convert(
                session_id="s1", request_text="convert to word", file_id="")
            selected = ConvertDocumentTool(self.store).convert(
                session_id="s1", request_text="convert to word", file_id=first.file_id)
        self.assertEqual(default["source_filename"], "second.pdf")
        self.assertEqual(selected["source_filename"], "first.pdf")
        self.assertEqual(seen, [self.store.path_for(second.file_id), self.store.path_for(first.file_id)])

    def test_convert_rejects_foreign_unknown_path_and_non_pdf(self):
        tool = ConvertDocumentTool(self.store)
        for file_id in (self.other_session.file_id, self.other_user.file_id,
                        "missing", "../private.txt"):
            with self.subTest(file_id=file_id):
                result = tool.convert(session_id="s1", request_text="convert to word", file_id=file_id)
                self.assertEqual(result["status"], "invalid_attachment_context")
        self.assertEqual(tool.convert(session_id="s1", request_text="convert to word",
                                      file_id=self.first.file_id)["status"], "input_required")


class FileSelectionSchemaTests(unittest.TestCase):
    def test_action_and_native_schemas_advertise_optional_file_id(self):
        for name in ("read_attached_file", "convert_document"):
            descriptor = CapabilityRegistry().describe_status(name)
            self.assertIn("file_id", descriptor.interface["parameters"])
            self.assertIn("file_id", LEGACY_TOOL_PARAMETERS[name]["properties"])
            self.assertNotIn("file_id", LEGACY_TOOL_PARAMETERS[name]["required"])

    def test_canonical_file_id_requires_uri_binding(self):
        from types import SimpleNamespace

        from uri_core.capabilities.wrong_binding import WrongBindingImpact
        from uri_core.core.canonical_execution import _execute_legacy_capability
        from uri_desktop_seams.reference_clarification.service import (
            ApprovalBindingIdentity, BindingState, SlotBindingIdentity,
        )

        calls = []

        class Gate:
            def execute_tool(self, capability, **kwargs):
                calls.append((capability, kwargs))
                return {"status": "success", "data": {"status": "success"}}

        principal = SimpleNamespace(user_id="user-1")
        orchestrator = SimpleNamespace(approval_gate=Gate())
        action = {"name": "read_attached_file", "inputs": {"file_id": "model-id"}}
        contract = {"capability": "read_attached_file", "actions": [action]}
        _execute_legacy_capability(contract, orchestrator=orchestrator, session_id="s1",
                                   user_text="read this", principal=principal)
        self.assertNotIn("file_id", calls[0][1])

        slot = SlotBindingIdentity(
            "read_attached_file", "read_attached_file", "file_id", "r1",
            "file:user-1:validated-id", "file", "validated-id", "version",
            BindingState.CONFIRMED, WrongBindingImpact.CONSEQUENTIAL,
            "user-1", "s1", "round-1", "2099-01-01T00:00:00+00:00",
        )
        bound_action = {**action, "_binding_identity": ApprovalBindingIdentity(
            1, True, (slot,), (("read_attached_file", "read_attached_file", "file_id", "r1"),)),
            "_reference_rechecks": [lambda: True]}
        _execute_legacy_capability(
            {"capability": "read_attached_file", "actions": [bound_action]},
            orchestrator=orchestrator, session_id="s1", user_text="read this",
            principal=principal,
        )
        self.assertEqual(calls[1][1]["file_id"], "validated-id")


if __name__ == "__main__":
    unittest.main()
