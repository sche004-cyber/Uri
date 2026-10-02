"""INT-ARN-1 Slice C entry-boundary tests; no provider or network access."""

from __future__ import annotations

import os
import json
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from uri_core.app import server
from uri_core.capabilities import Action, Capability, MultiActionCapabilityRegistry
from uri_core.capabilities.executor import MultiActionExecutor
from uri_core.capabilities.wrong_binding import WrongBindingImpact
from uri_core.core.approval_store import ApprovalStore
from uri_core.core.approval_gate import ApprovalGate
from uri_core.core.decision_engine import DecisionOutcome
from uri_core.core.file_store import FileStore
from uri_core.core.multi_action_dispatch import MultiActionDispatch
from uri_core.core.principal_context import PrincipalContext

USER_ID = "11111111-1111-4111-8111-111111111111"


class SliceCAskTests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.tmp = self.stack.enter_context(tempfile.TemporaryDirectory())
        self.stack.enter_context(patch.dict(os.environ, {
            "URI_INT_ARN_1_ENABLED": "1", "URI_ENABLE_DECISION_ENGINE_LIVE": "1",
            "URI_ENABLE_NATIVE_TOOL_LOOP": "0", "URI_ENABLE_APPROVAL_RESUMPTION": "0",
        }))
        self.stack.enter_context(patch.object(server, "_USER_STATE_ROOT", self.tmp))
        self.file_store = FileStore(str(Path(self.tmp) / USER_ID / "uploads"))
        self.first = self.file_store.save(filename="alpha.pdf", content=b"alpha", session_id="s1")
        self.second = self.file_store.save(filename="beta.pdf", content=b"beta", session_id="s1")
        self.calls = []
        self.drift_second = False

        def run_action(**inputs):
            self.calls.append(inputs)
            if self.drift_second and len(self.calls) == 1:
                Path(self.file_store.path_for(self.second.file_id)).write_bytes(b"evil")
            return {"status": "success", "file_id": inputs.get("file_id")}

        self.action = Action(
            "open", "Open a file", parameters={"file_id": {"type": "string", "required": True}},
            handler=run_action, wrong_binding_impact=WrongBindingImpact.CONSEQUENTIAL,
        )
        capability = Capability("Demo", "Demo", "test", actions={"open": self.action})
        dispatch = MultiActionDispatch(
            registry=MultiActionCapabilityRegistry([capability]), granted_permissions=set(),
        )
        approval_store = ApprovalStore(str(Path(self.tmp) / USER_ID / "approvals.json"))
        gate = SimpleNamespace(file_store=self.file_store, approval_store=approval_store)
        self.orchestrator = SimpleNamespace(
            multi_action_dispatch=dispatch, approval_gate=gate,
            principal=PrincipalContext(USER_ID, "user", None),
            _draft_narrative_safely=lambda **kwargs: None,
            _persist_session=lambda session_id: None,
            _record_conversation_turn_safely=lambda **kwargs: None,
            process_user_input=Mock(return_value={"status": "legacy", "session_id": "s1"}),
            conversation_history=SimpleNamespace(annotate_latest_turn=lambda *args, **kwargs: None),
        )
        self.context = SimpleNamespace(orchestrator=self.orchestrator, file_store=self.file_store)
        self.principal = self.orchestrator.principal
        self.stack.enter_context(patch.object(server, "_resolve_ask_context",
                                              return_value=(self.context, self.principal, None)))
        self.stack.enter_context(patch.object(server, "_resolve_context", return_value=self.context))
        self.stack.enter_context(patch.object(server, "_serving_model_for_turn", return_value={
            "provider_id": None, "model": None, "prompt_tokens": None,
            "eval_tokens": None, "duration_seconds": None,
        }))
        self.stack.enter_context(patch.object(server, "_turn_model_calls", return_value=None))
        self.edge = self.stack.enter_context(patch("uri_desktop_seams.harness_first.seam.try_harness_first", return_value=None))
        self.stack.enter_context(patch("uri_core.core.native_tool_loop.native_tool_loop_enabled", return_value=False))
        self.stack.enter_context(patch("uri_core.core.canonical_execution.workflow_continuation_mode_enabled", return_value=False))
        self.stack.enter_context(patch("uri_core.core.canonical_execution.canonical_killswitch_enabled", return_value=False))
        self.stack.enter_context(patch("uri_core.core.approval_resumption.approval_resumption_enabled", return_value=False))
        self.stack.enter_context(patch("uri_core.core.lifecycle_intent_interpreter.lifecycle_intent_seam_enabled", return_value=False))
        self.stack.enter_context(patch("uri_core.core.decision_engine.candidate_recall_at_k", return_value=None))
        self.stack.enter_context(patch("uri_core.core.decision_gates.evaluate_gates",
                                      return_value=SimpleNamespace(outcome="READY", reasons=())))

        class Directory:
            def describe(self, capability_id):
                return {"action_schemas": {"open": {"parameters": {"file_id": {"type": "string"}}}}}

            def summaries(self):
                return [{"capability_id": "Demo"}]

        self.stack.enter_context(patch("uri_core.core.canonical_execution.build_turn_state_and_directory",
            side_effect=lambda **kwargs: (SimpleNamespace(data={"turn": {"user_text": kwargs["user_text"]}}), Directory())))
        self.decision = self.stack.enter_context(patch("uri_core.core.canonical_execution.propose_decision",
                                                      side_effect=self._brain))
        server.app.dependency_overrides[server._resolve_authenticated_user_id] = lambda: USER_ID
        self.addCleanup(server.app.dependency_overrides.pop, server._resolve_authenticated_user_id, None)
        self.client = TestClient(server.app)

    def _brain(self, **kwargs):
        text = kwargs["turn_state_data"]["turn"]["user_text"]
        span = "that document"
        start = text.index(span)
        return DecisionOutcome("ok", {
            "goal": text, "mode": "single_action", "capability": "Demo",
            "actions": [{"name": "open", "inputs": {}}],
            "clarification": None, "unsupported_reason": None,
            "requires_approval": False, "confidence": "high", "reason": "Open file",
            "reference_slots": [{
                "span": {"start": start, "end": start + len(span), "text": span},
                "ref_key": "r1", "target": {"capability_id": "Demo", "action_name": "open",
                                            "argument_name": "file_id"},
                "relation": "direct", "source_class": "file",
            }],
        })

    def test_pending_then_selection_dispatches_once_with_binding_at_executor(self):
        original = MultiActionExecutor.execute
        seen = []

        def inspect(executor, capability, action, inputs, **kwargs):
            seen.append((capability, action, dict(inputs), kwargs.get("reference_bindings")))
            return original(executor, capability, action, inputs, **kwargs)

        with patch.object(MultiActionExecutor, "execute", inspect):
            first = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"})
            self.assertEqual(first.status_code, 200)
            card = first.json()["clarification"]
            self.assertEqual(first.json()["execution"]["status"], "not_executed")
            self.assertEqual(seen, [])
            chosen = card["options"][0]
            second = self.client.post("/ask", json={"session_id": "s1", "text": "",
                "clarification_response": {"ambiguity_id": card["ambiguity_id"],
                    "response_kind": "CANDIDATE", "candidate_id": chosen["candidate_id"],
                    "candidate_set_fingerprint": card["candidate_set_fingerprint"]}})
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["execution"]["status"], "success")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0][0:2], ("Demo", "open"))
        self.assertEqual(seen[0][2]["file_id"], chosen["candidate_id"].split(":")[-1])
        self.assertEqual(seen[0][3][0].candidate_id, chosen["candidate_id"])
        self.assertEqual(len(self.calls), 1)
        self.orchestrator.process_user_input.assert_not_called()

    def test_invalid_selection_never_dispatches(self):
        first = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"})
        card = first.json()["clarification"]
        result = self.client.post("/ask", json={"session_id": "s1", "text": "",
            "clarification_response": {"ambiguity_id": card["ambiguity_id"],
                "response_kind": "CANDIDATE", "candidate_id": "fabricated",
                "candidate_set_fingerprint": card["candidate_set_fingerprint"]}})
        self.assertEqual(result.json()["execution"]["status"], "not_executed")
        self.assertEqual(self.calls, [])
        self.orchestrator.process_user_input.assert_not_called()

    def test_malformed_slot_and_engine_failure_never_reach_legacy(self):
        original = self.decision.side_effect
        def malformed(**kwargs):
            decision = original(**kwargs)
            decision.contract["reference_slots"][0]["span"]["start"] = 999
            return decision
        self.decision.side_effect = malformed
        result = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"})
        self.assertEqual(result.json()["execution"]["status"], "not_executed")
        self.assertEqual(self.calls, [])
        self.orchestrator.process_user_input.assert_not_called()

    def test_reference_telemetry_has_stages_without_raw_turn_or_labels(self):
        self._pending_card()
        telemetry = Path(self.tmp) / USER_ID / "reference_clarification" / "telemetry.jsonl"
        self.assertTrue(telemetry.exists())
        events = [json.loads(line) for line in telemetry.read_text(encoding="utf-8").splitlines()]
        self.assertTrue(any(event.get("event") == "int_arn_1" and
                            event.get("outcome") == "clarification" for event in events))
        serialized = telemetry.read_text(encoding="utf-8")
        for forbidden in ("that document", "alpha.pdf", "beta.pdf"):
            self.assertNotIn(forbidden, serialized)

    def _pending_card(self):
        response = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"})
        self.assertEqual(response.status_code, 200)
        return response.json()["clarification"]

    def test_flag_off_preserves_existing_response_bytes(self):
        stable = {"status": "success", "session_id": "s1", "execution": {"status": "success"},
                  "response": {"message": "done"}}
        with patch.object(server.time, "time", return_value=100.0), patch(
            "uri_core.core.canonical_execution._execute_canonical", return_value=stable
        ):
            with patch.dict(os.environ, {"URI_INT_ARN_1_ENABLED": "0"}):
                disabled = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"}).content
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("URI_INT_ARN_1_ENABLED", None)
                unset = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"}).content
        self.assertEqual(disabled, unset)

    def test_pending_excludes_lifecycle_enable_disable_connect_disconnect_remove(self):
        self._pending_card()
        for operation in ("enable", "disable", "connect", "disconnect", "remove"):
            with self.subTest(operation=operation), patch(
                "uri_core.core.lifecycle_intent_interpreter.lifecycle_intent_seam_enabled", return_value=True,
            ), patch("uri_core.core.lifecycle_intent_interpreter.interpret",
                     return_value={"operation": operation, "target_id": "example"}) as interpret, patch(
                "uri_core.external.lifecycle_intent.execute_lifecycle_intent"
            ) as execute:
                result = self.client.post("/ask", json={"session_id": "s1", "text": f"{operation} example"})
                self.assertEqual(result.json()["execution"]["status"], "not_executed")
                interpret.assert_not_called()
                execute.assert_not_called()

    def test_pending_excludes_edge_and_social_control_still_uses_edge(self):
        self._pending_card()
        self.edge.reset_mock()
        response = self.client.post("/ask", json={"session_id": "s1", "text": "hello"})
        self.assertIn("clarification", response.json())
        self.edge.assert_not_called()
        # A different session has no pending round and retains Edge eligibility.
        self.edge.return_value = {"status": "success", "session_id": "s2",
                                  "execution": {"status": "not_applicable"},
                                  "response": {"message": "hello"}}
        control = self.client.post("/ask", json={"session_id": "s2", "text": "hello"})
        self.assertEqual(control.json()["status"], "success")
        self.edge.assert_called_once()

    def test_pending_excludes_early_workflow_continuation_and_native(self):
        self._pending_card()
        self.orchestrator.session_manager = SimpleNamespace(get_session=lambda _: SimpleNamespace(
            active_workflow=object(), active_workflow_status="waiting_for_input"))
        with patch("uri_core.core.canonical_execution.workflow_continuation_mode_enabled", return_value=True), patch(
            "uri_core.core.canonical_execution.run_canonical_for_ask"
        ) as canonical, patch("uri_core.core.native_tool_loop.native_tool_loop_enabled", return_value=True), patch(
            "uri_core.core.native_tool_loop.run_native_tool_loop"
        ) as native:
            response = self.client.post("/ask", json={"session_id": "s1", "text": "continue"})
        self.assertEqual(response.json()["execution"]["status"], "not_executed")
        canonical.assert_not_called()
        native.assert_not_called()

    def test_pending_excludes_legacy_fallback_multi_direct_and_workflow(self):
        self._pending_card()
        for text in ("run a direct tool", "run a multi action", "continue a workflow"):
            with self.subTest(text=text):
                self.client.post("/ask", json={"session_id": "s1", "text": text})
        self.orchestrator.process_user_input.assert_not_called()

    def test_stream_typed_response_and_pending_delegate_to_ask(self):
        card = self._pending_card()
        with patch("uri_core.core.native_tool_loop.native_tool_loop_enabled", return_value=True), patch(
            "uri_core.core.stream_tool_loop.stream_first_turn"
        ) as stream:
            pending = self.client.post("/ask/stream", json={"session_id": "s1", "text": "hello"})
            typed = self.client.post("/ask/stream", json={"session_id": "s1", "text": "",
                "clarification_response": {"ambiguity_id": card["ambiguity_id"],
                    "response_kind": "CANDIDATE", "candidate_id": "invalid",
                    "candidate_set_fingerprint": card["candidate_set_fingerprint"]}})
        self.assertIn("event: message", pending.text)
        self.assertIn("clarification", pending.text)
        self.assertIn("event: message", typed.text)
        stream.assert_not_called()

    def test_canonical_legacy_slot_fails_closed_and_no_slot_control(self):
        from uri_core.core.canonical_execution import _execute_canonical
        legacy_gate = SimpleNamespace(execute_tool=Mock(return_value={"status": "success"}))
        self.orchestrator.approval_gate = legacy_gate
        contract = {"capability": "legacy_tool", "actions": [{"name": "legacy_tool", "inputs": {}}],
                    "reference_slots": [{"ref_key": "r1", "target": {
                        "capability_id": "legacy_tool", "action_name": "legacy_tool", "argument_name": "file_id"}}]}
        blocked = _execute_canonical(contract, orchestrator=self.orchestrator,
            session_id="s1", user_text="that document", principal=self.principal)
        self.assertEqual(blocked["execution"]["status"], "not_executed")
        legacy_gate.execute_tool.assert_not_called()
        _execute_canonical({**contract, "reference_slots": []}, orchestrator=self.orchestrator,
            session_id="s1", user_text="ordinary request", principal=self.principal)
        legacy_gate.execute_tool.assert_called_once()

    def test_ready_web_fetch_prefix_suppressed_for_unresolved_slot(self):
        self._assert_prefix_suppressed("web_search", "search")

    def test_ready_gmail_prefix_suppressed_for_unresolved_slot(self):
        self._assert_prefix_suppressed("Gmail", "search_messages")

    def _assert_prefix_suppressed(self, capability, action):
        original = self.decision.side_effect
        def brain(**kwargs):
            decision = original(**kwargs)
            decision.contract["mode"] = "multi_action"
            decision.contract["actions"].insert(0, {"capability": capability, "name": action, "inputs": {}})
            return decision
        self.decision.side_effect = brain
        with patch("uri_core.core.canonical_execution._ready_read_prefix") as prefix:
            response = self.client.post("/ask", json={"session_id": "s1", "text": "open that document"})
        self.assertIn("clarification", response.json())
        prefix.assert_not_called()
        self.assertEqual(self.calls, [])

    def test_native_single_and_chain_slot_proposals_fail_closed(self):
        from uri_core.core.native_tool_loop import _execute_one_branch, execute_translated_batch
        with patch("uri_core.core.native_tool_loop._execute_canonical") as execute:
            single = _execute_one_branch(
                capability_id="Demo", action_name="open", inputs={"reference_slots": [{}]},
                orchestrator=self.orchestrator, session_id="s1", user_text="open that document",
                principal=self.principal, directory=None, turn_state_data={}, tool_call_id="c1",
                executed_signatures=set(), effect_type_is_read_only=True,
            )
            chain = execute_translated_batch(
                {"capability": "Demo", "actions": [{"name": "open", "inputs": {},
                    "reference_slots": [{}]}]}, results_meta=[{"tool_call_id": "c2"}],
                orchestrator=self.orchestrator, session_id="s1", user_text="open that document",
                principal=self.principal, directory=None, turn_state_data={},
                capability_registry=None, executed_signatures=set(),
            )
        self.assertEqual(single["gate_outcome"], "REFERENCE_UNRESOLVED")
        self.assertEqual(chain[0]["gate_outcome"], "REFERENCE_UNRESOLVED")
        execute.assert_not_called()

    def _brain_chain(self, **kwargs):
        text = kwargs["turn_state_data"]["turn"]["user_text"]
        slots = []
        for index, name in enumerate(("alpha.pdf", "beta.pdf"), 1):
            start = text.index(name)
            slots.append({"span": {"start": start, "end": start + len(name), "text": name},
                          "ref_key": f"r{index}", "target": {
                              "capability_id": "Demo", "action_name": "open", "argument_name": "file_id"},
                          "relation": "direct", "source_class": "file"})
        return DecisionOutcome("ok", {
            "goal": text, "mode": "multi_action", "capability": "Demo",
            "actions": [{"name": "open", "inputs": {}}, {"name": "open", "inputs": {}}],
            "clarification": None, "unsupported_reason": None, "requires_approval": False,
            "confidence": "high", "reason": "Open both files", "reference_slots": slots,
        })

    def test_canonical_chain_transports_each_binding_to_executor(self):
        self.decision.side_effect = self._brain_chain
        original = MultiActionExecutor.execute
        observed = []
        def inspect(executor, capability, action, inputs, **kwargs):
            observed.append((inputs["file_id"], kwargs.get("reference_bindings")))
            return original(executor, capability, action, inputs, **kwargs)
        with patch.object(MultiActionExecutor, "execute", inspect):
            response = self.client.post("/ask", json={"session_id": "s1",
                "text": "open alpha.pdf and beta.pdf"})
        self.assertEqual(response.json()["execution"]["status"], "success")
        self.assertEqual([item[0] for item in observed], [self.first.file_id, self.second.file_id])
        self.assertEqual([item[1][0].ref_key for item in observed], ["r1", "r2"])
        self.assertEqual(len(self.calls), 2)

    def test_canonical_chain_stops_before_second_step_on_source_drift(self):
        self.decision.side_effect = self._brain_chain
        self.drift_second = True
        original = MultiActionExecutor.execute
        observed = []
        def inspect(executor, capability, action, inputs, **kwargs):
            observed.append((inputs["file_id"], kwargs.get("reference_bindings")))
            return original(executor, capability, action, inputs, **kwargs)
        with patch.object(MultiActionExecutor, "execute", inspect):
            response = self.client.post("/ask", json={"session_id": "s1",
                "text": "open alpha.pdf and beta.pdf"})
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(response.json()["execution"]["result"]["halted_at"], "1")

    def _confirmed_identity(self):
        from uri_desktop_seams.reference_clarification.service import (
            ApprovalBindingIdentity, SlotBindingIdentity,
        )
        from uri_desktop_seams.reference_clarification.store import ClarificationJournal
        card = self._pending_card()
        chosen = card["options"][0]
        response = self.client.post("/ask", json={"session_id": "s1", "text": "",
            "clarification_response": {"ambiguity_id": card["ambiguity_id"],
                "response_kind": "CANDIDATE", "candidate_id": chosen["candidate_id"],
                "candidate_set_fingerprint": card["candidate_set_fingerprint"]}})
        self.assertEqual(response.json()["execution"]["status"], "success")
        with ClarificationJournal(root=self.tmp).transaction(USER_ID, "s1") as journal:
            binding_id = next(iter(journal.store.bindings))
            binding = journal.store.bindings[binding_id]
            candidate = next(item for item in journal.sources[binding_id]
                             if item.id == chosen["candidate_id"])
            expiry = journal.binding_expires[binding_id]
        self.calls.clear()
        slot = SlotBindingIdentity(
            "Demo", "open", "file_id", "r1", candidate.id, candidate.source_class,
            candidate.locator, candidate.version, binding.state,
            WrongBindingImpact.CONSEQUENTIAL, USER_ID, "s1", binding_id, expiry,
        )
        return ApprovalBindingIdentity(1, True, (slot,), (("Demo", "open", "file_id", "r1"),)), candidate

    def test_approve_registered_record_rechecks_and_dispatches_with_binding(self):
        identity, candidate = self._confirmed_identity()
        record = self.orchestrator.approval_gate.approval_store.propose(
            "Demo", {"file_id": candidate.source_id}, session_id="s1", action_name="open",
            binding_identity=identity, requires_reference_binding=True,
        )
        original = MultiActionExecutor.execute
        observed = []
        def inspect(executor, capability, action, inputs, **kwargs):
            observed.append(kwargs.get("reference_bindings"))
            return original(executor, capability, action, inputs, **kwargs)
        with patch.object(MultiActionExecutor, "execute", inspect):
            first = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
            second = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
        self.assertEqual(first.json()["execution"]["status"], "success", first.json())
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][0].candidate_id, candidate.id)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(second.json()["status"], "error")

    def test_approve_registered_drift_leaves_record_unconsumed(self):
        identity, candidate = self._confirmed_identity()
        record = self.orchestrator.approval_gate.approval_store.propose(
            "Demo", {"file_id": candidate.source_id}, session_id="s1", action_name="open",
            binding_identity=identity, requires_reference_binding=True,
        )
        Path(self.file_store.path_for(candidate.source_id)).write_bytes(b"changed")
        result = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
        self.assertEqual(result.json()["status"], "error")
        self.assertIsNone(self.orchestrator.approval_gate.approval_store.get(record.action_id).consumed_at)
        self.assertEqual(self.calls, [])

    def test_natural_language_approval_drift_is_unconsumed(self):
        identity, candidate = self._confirmed_identity()
        record = self.orchestrator.approval_gate.approval_store.propose(
            "Demo", {"file_id": candidate.source_id}, session_id="s1", action_name="open",
            binding_identity=identity, requires_reference_binding=True,
        )
        Path(self.file_store.path_for(candidate.source_id)).write_bytes(b"changed")
        with patch("uri_core.core.approval_resumption.approval_resumption_enabled", return_value=True):
            result = self.client.post("/ask", json={"session_id": "s1", "text": "yes"})
        self.assertEqual(result.json()["status"], "error")
        self.assertIsNone(self.orchestrator.approval_gate.approval_store.get(record.action_id).consumed_at)
        self.assertEqual(self.calls, [])

    def test_natural_language_approval_valid_executes_once(self):
        identity, candidate = self._confirmed_identity()
        record = self.orchestrator.approval_gate.approval_store.propose(
            "Demo", {"file_id": candidate.source_id}, session_id="s1", action_name="open",
            binding_identity=identity, requires_reference_binding=True,
        )
        with patch("uri_core.core.approval_resumption.approval_resumption_enabled", return_value=True):
            response = self.client.post("/ask", json={"session_id": "s1", "text": "yes"})
        self.assertEqual(response.json()["execution"]["status"], "success")
        self.assertEqual(len(self.calls), 1)
        self.assertIsNotNone(self.orchestrator.approval_gate.approval_store.get(record.action_id).consumed_at)

    def test_approve_legacy_binding_drift_leaves_it_unconsumed(self):
        from uri_desktop_seams.reference_clarification.service import (
            ApprovalBindingIdentity, SlotBindingIdentity,
        )
        identity, candidate = self._confirmed_identity()
        legacy_action = Action(
            "Legacy", "legacy", parameters={"file_id": {"type": "string", "required": True}},
            handler=lambda **_: {"status": "success"},
            wrong_binding_impact=WrongBindingImpact.CONSEQUENTIAL,
        )
        self.orchestrator.multi_action_dispatch.registry.register(
            Capability("Legacy", "Legacy", "test", actions={"Legacy": legacy_action}))
        gate = ApprovalGate(SimpleNamespace(execute_tool=Mock()),
                            approval_store=self.orchestrator.approval_gate.approval_store,
                            file_store=self.file_store)
        self.orchestrator.approval_gate = gate
        slot = identity.slots[0]
        slot = SlotBindingIdentity("Legacy", "Legacy", slot.argument_name, slot.ref_key,
            slot.candidate_id, slot.source_class, slot.locator, slot.source_version,
            slot.state, slot.wrong_binding_impact, slot.user_id, slot.session_id,
            slot.round_id, slot.expires_at)
        legacy_identity = ApprovalBindingIdentity(1, True, (slot,),
            (("Legacy", "Legacy", "file_id", "r1"),))
        record = gate.approval_store.propose("Legacy", {"file_id": candidate.source_id},
            session_id="s1", binding_identity=legacy_identity, requires_reference_binding=True)
        Path(self.file_store.path_for(candidate.source_id)).write_bytes(b"changed")
        result = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
        self.assertEqual(result.json()["status"], "error")
        self.assertIsNone(gate.approval_store.get(record.action_id).consumed_at)
        gate.dispatcher.execute_tool.assert_not_called()

    def test_missing_required_approval_identity_fails_closed(self):
        identity, candidate = self._confirmed_identity()
        store = self.orchestrator.approval_gate.approval_store
        record = store.propose("Demo", {"file_id": candidate.source_id}, session_id="s1",
            action_name="open", binding_identity=identity, requires_reference_binding=True)
        path = Path(store.storage_path)
        contents = json.loads(path.read_text(encoding="utf-8"))
        contents["actions"][-1]["binding_identity"] = None
        path.write_text(json.dumps(contents), encoding="utf-8")
        result = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
        self.assertEqual(result.json()["status"], "error")
        self.assertIsNone(store.get(record.action_id).consumed_at)
        self.assertEqual(self.calls, [])

    def test_approve_legacy_no_reference_keeps_prior_path(self):
        dispatcher = SimpleNamespace(execute_tool=Mock(return_value={"status": "success"}))
        gate = ApprovalGate(dispatcher, approval_store=self.orchestrator.approval_gate.approval_store)
        self.orchestrator.approval_gate = gate
        self.context.profile_store = SimpleNamespace(load_or_create=lambda: None)
        self.context.memory_store = SimpleNamespace(list_all=lambda: [])
        self.orchestrator.decide_action = lambda **kwargs: gate.decide(
            kwargs["action_id"], approved=kwargs["approved"], session_id=kwargs["session_id"])
        record = gate.approval_store.propose("legacy_tool", {"request_text": "ordinary"}, session_id="s1")
        result = self.client.post("/approve", json={"session_id": "s1", "action_id": record.action_id})
        self.assertEqual(result.json()["status"], "success")
        dispatcher.execute_tool.assert_called_once()


if __name__ == "__main__":
    unittest.main()
