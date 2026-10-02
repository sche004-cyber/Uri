"""M30.6: Controlled canonical execution - the FIRST milestone in this
sequence where the Brain Decision Contract + deterministic gate
pipeline (M30.3-M30.5D) is allowed to control real execution, for a
small, explicitly allowlisted set of capabilities only.

Governing constraints, enforced structurally by this module (not by
convention):

    - Default OFF (`URI_ENABLE_DECISION_ENGINE_LIVE` unset). When off,
      `run_canonical_for_ask()` is never reached from server.py at all
      (mirrors `URI_ENABLE_DECISION_ENGINE_SHADOW`'s own gating).
    - Allowlist-only: `CANONICAL_EXECUTION_ALLOWLIST` names the exact
      two capabilities the accepted migration plan's Phase C names
      (`URI_CANONICAL_AGENT_LOOP_MIGRATION_PLAN.md` §4) - Gmail
      (multi-action) and `remember_fact` (legacy). Nothing else can
      ever reach real execution through this module, regardless of
      what the model proposes.
    - Execution is allowed ONLY when the deterministic gate (M30.5's
      `decision_gates.evaluate_gates()`, reused unchanged) returns
      READY. Every other outcome (MISSING_PARAMETER, DISCONNECTED,
      UNAVAILABLE, PERMISSION_DENIED, APPROVAL_REQUIRED, UNSUPPORTED,
      INVALID_PROPOSAL, DEGRADED) falls back to the existing legacy
      `/ask` result untouched - this module never executes on any of
      them, and never invents a deterministic handling path of its own
      for a protected action; approval-required cases flow through the
      existing ApprovalGate/ApprovalStore pending-decision mechanism.
      (M32.1 correction: prior to M32.1 this was true only for the
      legacy `remember_fact` path - a Gmail APPROVAL_REQUIRED outcome
      had no durable ApprovalStore record at all, so it could never be
      resumed on a later turn. M32.1's `_propose_durable_gmail_approval()`
      bridges the Gmail single-action branch to a real, durable
      `ApprovalStore.propose()` call, making this claim true for both
      paths. The multi-step Gmail chain branch is still out of scope -
      see `approval_resumption.py`'s module docstring.)
    - No new invocation mechanics: Gmail actions execute through
      `MultiActionDispatch.dispatch_explicit()`/`dispatch_chain_explicit()`
      (M30.6, `multi_action_dispatch.py`) - thin wrappers around the
      SAME `MultiActionExecutor.execute()`/`execute_chain()` the legacy
      `dispatch()` path already used, with the Brain Decision
      Contract's explicit `capability`/`actions` fields replacing
      `dispatch()`'s own undocumented model-proposal-shape trigger
      (exactly the migration the accepted plan's §1 MultiActionDispatch
      row describes). `remember_fact` executes through the existing,
      unchanged `ApprovalGate.execute_tool()` boundary - the same one
      every legacy capability already uses.
    - Body -> Brain feedback: real execution evidence is packaged into
      the same `{"plan", "execution", "response"}` envelope shape
      `orchestrator.py`'s own legacy branches already build, then
      handed to the orchestrator's own existing, unchanged
      `_draft_narrative_safely()` - which only ever drafts from
      already-decided `execution`/`response` fields and independently
      validates claim-consistency (see that method's own docstring) -
      so a narrative can never claim more than the real evidence
      supports, without a second, new drafting/validation mechanism.
"""

from __future__ import annotations

import os
import time
import json
import re
import threading
from dataclasses import asdict
from uuid import uuid4
from typing import Any, Dict, List, Optional, Sequence

from uri_core.core.decision_engine import (
    DEFAULT_SHADOW_LOG_PATH,
    build_turn_state_and_directory,
    propose_decision,
    record_shadow_trace,
)

LIVE_ENV_VAR = "URI_ENABLE_DECISION_ENGINE_LIVE"
WORKFLOW_CONTINUATION_ENV_VAR = "URI_ENABLE_WORKFLOW_CONTINUATION_MODE"
ALLOWLIST_ENV_VAR = "URI_CANONICAL_EXECUTION_ALLOWLIST"
_REFERENCE_RENDER_SLOTS = threading.BoundedSemaphore(2)
_UNRECORDED_REFERENCE_EXECUTIONS: set[tuple[str, str, str]] = set()


def reference_execution_record_failed(user_id: str, session_id: str, binding_id: str) -> bool:
    """Prevent a Change from replaying an action whose applied state was not saved."""
    return (user_id, session_id, binding_id) in _UNRECORDED_REFERENCE_EXECUTIONS

DEFAULT_TELEMETRY_LOG_PATH = os.path.join(
    os.path.dirname(DEFAULT_SHADOW_LOG_PATH) or ".", "canonical_execution_log.jsonl"
)


def _record_reference_stage(*, path: str, session_id: str, stage: str,
                            outcome: str, started: float, source_class: str = "",
                            candidate_count: int = 0, binding_state: str = "",
                            reason: str = "") -> None:
    """Structured reference telemetry; no turn text, labels, or source content."""
    code = reason if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", reason or "") else "OTHER"
    record_shadow_trace({
        "event": "int_arn_1", "stage": stage, "session_id": session_id,
        "outcome": outcome, "source_class": source_class,
        "candidate_count": candidate_count, "binding_state": binding_state,
        "reason_code": code, "duration_ms": round((time.monotonic() - started) * 1000, 2),
    }, path=path)

# M30.8: canonical is the normal authority for every capability exposed by
# the Directory.  ``None`` deliberately means "no restriction".  Operators
# can replace this value with a (possibly empty) frozenset as an emergency
# rollback lever; server.py then uses legacy-first dispatch for that process.
# Keeping the value mutable is intentional: it is an operational kill switch,
# not a second capability registry.
CANONICAL_EXECUTION_ALLOWLIST: Optional[frozenset[str]] = None


def reference_clarification_enabled() -> bool:
    return os.environ.get("URI_INT_ARN_1_ENABLED") == "1"


def _reference_block(session_id: Optional[str], reason: str = "REFERENCE_UNRESOLVED") -> Dict[str, Any]:
    return {
        "status": "awaiting_user_response", "session_id": session_id,
        "execution": {"status": "not_executed", "reason": reason},
        "response": {"message": "I need to clarify the reference before proceeding. Please retry the request."},
        "narrative": None,
    }


def _reference_wire(outcome: Any) -> Dict[str, Any]:
    from uri_v1.turn.rar_clarification_contract import ESCAPE_LABEL
    contract, render = outcome.contract, outcome.render
    labels = dict(render.labels) if render is not None else {}
    return {
        "ambiguity_id": contract.ambiguity_id,
        "trace_id": contract.turn_id,
        "kind": contract.kind.value,
        "question": render.question if render is not None else "Which item did you mean?",
        "options": [
            {"option_key": item.option_key, "candidate_id": item.candidate_id,
             "label": labels.get(item.option_key, item.display_facts[0].value if item.display_facts else item.candidate_id),
             "rank": item.rank}
            for item in contract.candidates
        ],
        "attribute_axis": contract.attribute_axis,
        "attribute_filters": [
            {"option_key": item.option_key, "axis": item.axis, "value": item.value,
             "label": labels.get(item.option_key, item.value),
             "member_count": len(item.member_candidate_ids)}
            for item in contract.attribute_options
        ],
        "overflow_count": contract.overflow_count,
        "escape_label": ESCAPE_LABEL,
        "candidate_set_fingerprint": contract.candidate_set_fingerprint,
        "expires_at": contract.expires_at,
    }


def _reference_render_draft(contract: Any, principal: Any) -> Any:
    """One small Brain call for wording; the frozen validator owns the result."""
    from uri_core.config.model_roles import ROLE_REASONING
    from uri_core.core.model_router import get_router
    from uri_v1.reference_clarification.render_contracts import make_render_request

    try:
        budget = int(os.environ.get("URI_INT_ARN_1_RENDER_BUDGET_MS", "800"))
    except ValueError:
        budget = 0
    if budget <= 0:
        return None
    request = make_render_request(contract)
    facts = {key: dict(values) for key, values in request.slots}
    # A daemon worker lets the request return at the deadline even when a
    # provider ignores transport timeouts. Bound outstanding slow calls too.
    if not _REFERENCE_RENDER_SLOTS.acquire(blocking=False):
        return None
    done = threading.Event()
    result = {}

    def render():
        try:
            response = get_router().attempt(
                ROLE_REASONING, principal,
                system=("Write a concise clarification question and labels using only these facts. "
                        "Return JSON with question and labels keyed by the supplied option keys. "
                        "Do not add options, IDs, authority, or claims."),
                user=json.dumps({"kind": request.kind.value, "reference": request.reference,
                                 "facts": facts, "overflow": request.overflow}, ensure_ascii=False),
                temperature=0, max_tokens=160,
            )
            result["content"] = response.content
        except Exception:
            pass
        finally:
            _REFERENCE_RENDER_SLOTS.release()
            done.set()

    threading.Thread(target=render, daemon=True, name="uri-reference-render").start()
    return result.get("content") if done.wait(budget / 1000) else None


def _reference_record_dispatch(contract: Dict[str, Any], envelope: Dict[str, Any],
                               principal: Any, session_id: str, journal_root: Optional[str],
                               telemetry_path: Optional[str] = None) -> bool:
    """Persist the frozen binding transition after a bound action actually ran."""
    from uri_desktop_seams.reference_clarification.store import ClarificationJournal
    from uri_v1.reference_clarification.binding import BindingService
    from uri_v1.turn.rar_clarification_contract import BindingState

    execution = envelope.get("execution") or {}
    status = execution.get("status")
    if status not in {"success", "ok", "halted"}:
        return True
    actions = contract.get("actions") or []
    steps = (execution.get("result") or {}).get("steps")
    ids = set()
    for index, action in enumerate(actions):
        if not isinstance(action, dict):
            continue
        if isinstance(steps, dict):
            step = steps.get(str(action.get("id", index)))
            if not isinstance(step, dict) or step.get("status") not in {"success", "ok"}:
                continue
        ids.update(slot.round_id for slot in action.get("_binding_slots", ()))
    if not ids:
        return True
    def failed() -> bool:
        for binding_id in ids:
            _UNRECORDED_REFERENCE_EXECUTIONS.add((principal.user_id, session_id, binding_id))
        try:
            from uri_core.core.portable_paths import user_scoped_path
            path = telemetry_path or user_scoped_path(
                principal.user_id, "reference_clarification/telemetry.jsonl",
                root=journal_root or "uri_workspace/users")
            _record_reference_stage(path=path, session_id=session_id, stage="dispatch",
                                    outcome=status, started=time.monotonic(),
                                    reason="EXECUTION_RECORD_UNAVAILABLE")
        except Exception:
            pass
        return False
    try:
        journal_store = ClarificationJournal(**({"root": journal_root} if journal_root is not None else {}))
        with journal_store.transaction(principal.user_id, session_id) as journal:
            service = BindingService(journal.store)
            for binding_id in ids:
                binding = journal.store.bindings.get(binding_id)
                if binding is None or binding.session_id != session_id:
                    return failed()
                if binding.state in (BindingState.TENTATIVE, BindingState.CONFIRMED):
                    service.record_execution(binding_id, applied_result_exists=True)
        return True
    except (ValueError, KeyError, OSError):
        return failed()


def _reference_evidence(slot: Any, *, orchestrator: Any, principal: Any,
                        session_id: str, attachments: Optional[List[Dict[str, Any]]]) -> Any:
    from datetime import datetime, timezone
    from uri_desktop_seams.reference_clarification.evidence import (
        AuthorizedReadBatch, produce_evidence,
    )
    file_store = getattr(getattr(orchestrator, "approval_gate", None), "file_store", None)
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    gmail = drive = None
    if slot.source_class in {"any", "gmail"} and dispatch is not None:
        capability = dispatch.registry.get_capability("Gmail")
        if capability is not None and dispatch._action_permitted("Gmail", "search_messages", principal):
            result = capability.search_messages(slot.expression, max_results=16)
            def read_gmail(source_id):
                current = capability.read_message(source_id)
                return current.get("message") if current.get("status") == "success" else None
            gmail = AuthorizedReadBatch(
                "gmail", principal.user_id, datetime.now(timezone.utc).isoformat(), result,
                read_current=read_gmail,
                can_read=lambda source_id: dispatch._action_permitted("Gmail", "read_message", principal),
                complete=not result.get("truncated", True),
            )
    if slot.source_class in {"any", "drive"}:
        from uri_core.core.capability_resolver import CapabilityResolver
        if CapabilityResolver.is_allowed("drive_search", principal=principal):
            from uri_core.services.drive_service import DriveService
            service = DriveService(user_id=principal.user_id)
            result = service.search_drive(slot.expression, limit=16)
            if result.get("success"):
                def read_drive(source_id):
                    try:
                        return service.service.files().get(
                            fileId=source_id, fields="id,name,mimeType,modifiedTime,version"
                        ).execute()
                    except Exception:
                        return None
                listed = result.get("files", [])
                refreshed = [read_drive(item.get("id")) for item in listed if isinstance(item, dict)]
                refresh_valid = len(refreshed) == len(listed) and all(item is not None for item in refreshed)
                if not refresh_valid:
                    refreshed = []
                drive = AuthorizedReadBatch(
                    "drive", principal.user_id, datetime.now(timezone.utc).isoformat(),
                    {"status": "success" if refresh_valid else "unavailable", "files": refreshed},
                    read_current=read_drive,
                    can_read=lambda source_id: CapabilityResolver.is_allowed(
                        "drive_search", principal=principal),
                    complete=len(listed) < 16 and refresh_valid,
                )
    return produce_evidence(
        slot, principal_id=principal.user_id, session_id=session_id,
        file_store=file_store, file_store_user_id=principal.user_id if file_store is not None else None,
        current_attachment_handles=tuple(item["file_id"] for item in (attachments or [])
                                         if isinstance(item, dict) and isinstance(item.get("file_id"), str)),
        gmail=gmail, drive=drive,
    )


def _reference_prepare(contract: Dict[str, Any], *, user_text: str, session_id: str,
                       orchestrator: Any, principal: Any, directory: Any,
                       attachments: Optional[List[Dict[str, Any]]],
                       resumed: Optional[Dict[str, Any]] = None,
                       journal_root: Optional[str] = None,
                       telemetry_path: str = DEFAULT_TELEMETRY_LOG_PATH) -> tuple[Dict[str, Any], Optional[Dict[str, Any]]]:
    """Validate Brain slots, ground them, and attach verified per-action transport."""
    from uri_desktop_seams.reference_clarification.proposal import validate_reference_slots
    from uri_desktop_seams.reference_clarification.service import (
        ApprovalBindingIdentity, ReferenceClarificationService, SlotBindingIdentity,
    )
    from uri_desktop_seams.reference_clarification.store import ClarificationJournal
    from uri_core.capabilities.wrong_binding import (
        ReferenceBinding, ReferenceBindingStatus, effective_wrong_binding_impact,
    )
    from uri_v1.turn.rar_clarification_contract import BindingState

    if "reference_slots" not in contract:
        if resumed is not None:
            return contract, _reference_block(session_id, "RESUMED_SLOT_MISSING")
        return contract, None
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    registry = getattr(dispatch, "registry", None)
    argument_map = {}
    for item in contract.get("actions") or []:
        if not isinstance(item, dict):
            continue
        cap_id = item.get("capability") or contract.get("capability")
        action = registry.get_capability(cap_id).get_action(item.get("name")) if registry and registry.get_capability(cap_id) else None
        parameters = getattr(getattr(action, "parameters", None), "parameters", {}) if action else {}
        argument_map[(cap_id, item.get("name"))] = frozenset(parameters)
    slots = validate_reference_slots(contract, user_text, argument_map)
    if not slots:
        return contract, None
    if principal is None or not principal.user_id or not session_id or registry is None:
        return contract, _reference_block(session_id, "REFERENCE_AUTHORITY_UNAVAILABLE")
    service = ReferenceClarificationService(journal=ClarificationJournal(
        **({"root": journal_root} if journal_root is not None else {})))
    actions = [dict(item) for item in contract.get("actions") or []]
    resumed_used = False
    for slot in slots:
        stage_started = time.monotonic()
        capability = registry.get_capability(slot.capability_id)
        action = capability.get_action(slot.action_name) if capability else None
        if action is None or not getattr(dispatch, "_action_permitted", lambda *_: False)(slot.capability_id, slot.action_name, principal):
            return contract, _reference_block(session_id, "REFERENCE_ACTION_UNAVAILABLE")
        impact, declared = effective_wrong_binding_impact(action)
        envelope = _reference_evidence(slot, orchestrator=orchestrator, principal=principal,
                                       session_id=session_id, attachments=attachments)
        if envelope.abstained:
            _record_reference_stage(path=telemetry_path, session_id=session_id, stage="evidence",
                outcome="abstained", started=stage_started, source_class=slot.source_class,
                reason=envelope.abstain_reason or "SOURCE_UNAVAILABLE")
            return contract, _reference_block(session_id, envelope.abstain_reason or "SOURCE_UNAVAILABLE")
        if resumed and not resumed_used and resumed.get("slot") == asdict(slot):
            binding_id = resumed.get("binding_id")
            with service.journal.transaction(principal.user_id, session_id) as journal:
                if not isinstance(binding_id, str) or not service._verified_binding(journal, binding_id, envelope):
                    return contract, _reference_block(session_id, "REFERENCE_STALE")
                binding_record = journal.store.bindings[binding_id]
            candidate_id, state = binding_record.candidate_id, binding_record.state
            resumed_used = True
        else:
            outcome = service.resolve(user_id=principal.user_id, session_id=session_id,
                                      turn_id=uuid4().hex, envelope=envelope,
                                      wrong_binding_impact=impact,
                                      render_draft=lambda round_contract: _reference_render_draft(round_contract, principal))
            if outcome.contract is not None:
                _record_reference_stage(path=telemetry_path, session_id=session_id, stage="resolution",
                    outcome="clarification", started=stage_started, source_class=slot.source_class,
                    candidate_count=len(envelope.inventory), binding_state=outcome.state.value)
                with service.journal.transaction(principal.user_id, session_id) as journal:
                    journal.origins["request:" + outcome.contract.ambiguity_id] = json.dumps({
                        "text": user_text, "slot": asdict(slot), "attachments": attachments or [],
                        "capability_id": slot.capability_id, "action_name": slot.action_name,
                    }, ensure_ascii=False)
                blocked = _reference_block(session_id)
                blocked["clarification"] = _reference_wire(outcome)
                blocked["response"] = {"message": blocked["clarification"]["question"]}
                return contract, blocked
            if outcome.status != "BOUND" or not outcome.binding_id or not outcome.candidate_id:
                _record_reference_stage(path=telemetry_path, session_id=session_id, stage="resolution",
                    outcome="retry", started=stage_started, source_class=slot.source_class,
                    candidate_count=len(envelope.inventory), reason="REFERENCE_UNRESOLVED")
                return contract, _reference_block(session_id, outcome.reason or "REFERENCE_UNRESOLVED")
            candidate_id, state, binding_id = outcome.candidate_id, outcome.state, outcome.binding_id
        _record_reference_stage(path=telemetry_path, session_id=session_id, stage="resolution",
            outcome="bound", started=stage_started, source_class=slot.source_class,
            candidate_count=len(envelope.inventory), binding_state=state.value)
        candidate = next((item for item in envelope.inventory if item.id == candidate_id), None)
        if candidate is None or state not in (BindingState.CONFIRMED, BindingState.TENTATIVE):
            return contract, _reference_block(session_id, "REFERENCE_STALE")
        target = next((item for item in actions if item.get("name") == slot.action_name
                       and (item.get("capability") or contract.get("capability")) == slot.capability_id
                       and not any(bound.argument_name == slot.argument_name
                                   for bound in item.get("_binding_slots", ()))), None)
        if target is None:
            return contract, _reference_block(session_id, "REFERENCE_ACTION_CHANGED")
        target["inputs"] = {**(target.get("inputs") or {}), slot.argument_name: candidate.source_id}
        target.setdefault("reference_bindings", []).append(ReferenceBinding(
            slot.ref_key, candidate.id,
            ReferenceBindingStatus.CONFIRMED if state == BindingState.CONFIRMED else ReferenceBindingStatus.TENTATIVE))
        with service.journal.transaction(principal.user_id, session_id) as journal:
            expires_at = journal.binding_expires.get(binding_id)
        if not expires_at:
            return contract, _reference_block(session_id, "REFERENCE_EXPIRED")
        target.setdefault("_binding_slots", []).append(SlotBindingIdentity(
            slot.capability_id, slot.action_name, slot.argument_name, slot.ref_key,
            candidate.id, candidate.source_class, candidate.locator, candidate.version,
            state, impact, principal.user_id, session_id, binding_id, expires_at))
        if state == BindingState.TENTATIVE:
            contract.setdefault("_tentative_bindings", []).append({
                "label": candidate.title, "candidate_id": candidate.id,
                "binding_id": binding_id,
            })
            with service.journal.transaction(principal.user_id, session_id) as journal:
                journal.origins["binding:" + binding_id] = json.dumps({
                    "text": user_text, "slot": asdict(slot), "attachments": attachments or [],
                }, ensure_ascii=False)
        def recheck(slot=slot, binding_id=binding_id, candidate_id=candidate.id,
                    expected_impact=impact):
            live_capability = registry.get_capability(slot.capability_id)
            live_action = live_capability.get_action(slot.action_name) if live_capability else None
            current_impact, current_declared = effective_wrong_binding_impact(live_action)
            if (live_action is None or current_impact != expected_impact
                    or not dispatch._action_permitted(slot.capability_id, slot.action_name, principal)):
                return False
            current = _reference_evidence(slot, orchestrator=orchestrator, principal=principal,
                                          session_id=session_id, attachments=attachments)
            with service.journal.transaction(principal.user_id, session_id) as journal:
                binding = journal.store.bindings.get(binding_id)
                return (binding is not None and binding.candidate_id == candidate_id
                        and service._verified_binding(journal, binding_id, current))
        target.setdefault("_reference_rechecks", []).append(recheck)
    if resumed and not resumed_used:
        return contract, _reference_block(session_id, "RESUMED_SLOT_CHANGED")
    for item in actions:
        if item.get("_binding_slots"):
            identities = tuple(item["_binding_slots"])
            item["_binding_identity"] = ApprovalBindingIdentity(1, True, identities,
                tuple((slot.capability_id, slot.action_name, slot.argument_name, slot.ref_key)
                      for slot in identities))
    return {**contract, "actions": actions}, None

# A mode with no real action to execute (conversation, clarification,
# unsupported, workflow_continuation-with-no-capability,
# approval_required - the last already excluded by gate READY) never
# reaches this module's execution branch at all.
EXECUTABLE_MODES = frozenset({"single_action", "multi_action", "workflow_continuation"})


def decision_engine_live_enabled() -> bool:
    """M32 B1.1: canonical is the committed production default - the
    absence of this env var no longer means "off". Set it to "0"
    (any other value than unset/"1" is treated as off) as the
    operational rollback lever when legacy-first handling is needed
    without a redeploy."""
    value = os.environ.get(LIVE_ENV_VAR)
    if value is None:
        return True
    return value == "1"


def workflow_continuation_mode_enabled() -> bool:
    """M32 B1.5: the second cutover flag, decided the same way as B1.1 -
    canonical handles resumed/continuation turns by default. Set to "0"
    to force resumed turns back to legacy without touching the primary
    LIVE_ENV_VAR."""
    value = os.environ.get(WORKFLOW_CONTINUATION_ENV_VAR)
    if value is None:
        return True
    return value == "1"


def _current_allowlist() -> Optional[frozenset[str]]:
    """M32 B1.2: the emergency rollback lever, made runtime-settable.

    ``URI_CANONICAL_EXECUTION_ALLOWLIST``, when set, takes precedence
    over the module-level ``CANONICAL_EXECUTION_ALLOWLIST`` constant -
    a comma-separated list of capability ids narrows canonical
    authority to exactly those, and an explicitly empty string narrows
    it to nothing (full legacy-first fallback), both without a
    redeploy. Unset means "defer to the module constant", preserving
    the pre-B1.2 code-level default of unrestricted (``None``).
    """
    raw = os.environ.get(ALLOWLIST_ENV_VAR)
    if raw is None:
        return CANONICAL_EXECUTION_ALLOWLIST
    raw = raw.strip()
    if not raw:
        return frozenset()
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def is_allowlisted(capability_id: Optional[str]) -> bool:
    if not capability_id:
        return False
    allowlist = _current_allowlist()
    return allowlist is None or capability_id in allowlist


def canonical_killswitch_enabled() -> bool:
    """Whether an operator narrowed canonical authority for rollback.

    The default ``None`` (module constant, or ``ALLOWLIST_ENV_VAR``
    unset) is unrestricted.  Any concrete set, including an empty one -
    from either the module constant or the runtime env var - is an
    explicit request for legacy-first route handling.
    """
    return _current_allowlist() is not None


def _propose_durable_gmail_approval(
    *, orchestrator: Any, session_id: Optional[str], capability: str,
    action_name: str, bound_inputs: Dict[str, Any],
    binding_identity: Any = None,
) -> Optional[str]:
    """M32.1: MultiActionExecutor.execute()'s approval_required outcome
    (executor.py:54-57) is a stateless, per-call boolean check with no
    persistence of its own - unlike the legacy ApprovalGate.execute_tool()
    path, it never wrote anything to ApprovalStore, so an
    "awaiting_approval" Gmail/Drive envelope previously carried no
    action_id at all and could never actually be approved by anything,
    UI button or natural language alike (live-confirmed during M32.1's
    own investigation). Bridges it to the SAME ApprovalStore instance
    ApprovalGate already owns - never a second store instance pointed
    at a different file - so a real, durable, resumable action_id
    exists. Returns None (never raises) on any failure - a proposal
    write failing must degrade to "approval required, but not yet
    resumable" honestly, never break the turn that already succeeded
    in reaching a real, honest APPROVAL_REQUIRED decision."""
    approval_gate = getattr(orchestrator, "approval_gate", None)
    approval_store = getattr(approval_gate, "approval_store", None)
    if approval_store is None:
        return None
    try:
        proposed = approval_store.propose(
            capability_id=capability, arguments=bound_inputs,
            session_id=session_id, action_name=action_name,
            **({"binding_identity": binding_identity, "requires_reference_binding": True}
               if binding_identity is not None else {}),
        )
        return proposed.action_id
    except Exception:
        return None


def _execute_multi_action(
    contract: Dict[str, Any],
    *,
    capability_id: str,
    orchestrator: Any,
    session_id: Optional[str],
    user_text: str,
    principal: Any,
) -> Optional[Dict[str, Any]]:
    """M33 Batch B: the generalized form of the old `_execute_gmail` -
    any capability registered in `orchestrator.multi_action_dispatch.
    registry` (Gmail by default construction, plus whatever `server.py`'s
    user-context composition has published from Batch A's enabled
    external capabilities) executes through this ONE path. Gmail keeps
    its exact prior behavior because it is still exactly the same
    registered capability id going through the exact same `dispatch_
    explicit`/`dispatch_chain_explicit` calls - through registration,
    not through a `capability_id == "Gmail"` branch."""
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    if dispatch is None:
        return None
    actions: List[Dict[str, Any]] = [
        a for a in (contract.get("actions") or []) if isinstance(a, dict) and a.get("name")
    ]
    if not actions:
        return None
    if len(actions) == 1:
        if reference_clarification_enabled() and any(
            not check() for check in actions[0].get("_reference_rechecks", ())
        ):
            return _reference_block(session_id, "REFERENCE_STALE")
        action_name = actions[0]["name"]
        # A typed action may explicitly declare that it needs the current
        # user utterance. Bind that runtime-owned value generically; the
        # model cannot replace it by omitting the field and no action that
        # did not opt in receives an extra schema key.
        inputs = dict(actions[0].get("inputs") or {})
        capability = getattr(getattr(dispatch, "registry", None), "get_capability", lambda _n: None)(capability_id)
        selected_action = capability.get_action(action_name) if capability is not None else None
        if selected_action is not None and "request_text" in selected_action.parameters.parameters and "request_text" not in inputs:
            inputs["request_text"] = user_text
        envelope = dispatch.dispatch_explicit(
            capability_id, action_name, inputs,
            session_id=session_id, user_text=user_text, principal=principal,
            **({"reference_bindings": tuple(actions[0]["reference_bindings"])}
               if actions[0].get("reference_bindings") else {}),
        )
        # M32.1: a single-action awaiting_approval result is the ONLY
        # shape this milestone bridges to a durable, resumable action_id
        # - a multi-step chain (the `else` branch below) halting on a
        # mid-chain approval is a materially different problem (which
        # step, preserving already-completed steps) and is explicitly
        # out of this bounded milestone's scope; disclosed, not silently
        # handled. `_propose_durable_gmail_approval` already takes
        # `capability` as a parameter (never hardcodes "Gmail" itself),
        # so this bridge applies identically to any registered capability
        # - only its name is historical.
        if (
            isinstance(envelope, dict)
            and envelope.get("execution", {}).get("status") == "awaiting_approval"
        ):
            bound_inputs = envelope.get("plan", {}).get("inputs") or {}
            action_id = _propose_durable_gmail_approval(
                orchestrator=orchestrator, session_id=session_id, capability=capability_id,
                action_name=action_name, bound_inputs=bound_inputs,
                binding_identity=actions[0].get("_binding_identity"),
            )
            if action_id is not None:
                envelope = dict(envelope)
                envelope["execution"] = dict(envelope["execution"])
                envelope["execution"]["action_id"] = action_id
                response = envelope.get("response")
                envelope["response"] = (
                    {**response, "action_id": action_id}
                    if isinstance(response, dict) else {"action_id": action_id, "detail": response}
                )
    else:
        # M34 C3.3: an action's own "capability" (already validated
        # against the real directory by `_validate_contract()`, and
        # already independently re-authorized per its OWN capability by
        # `evaluate_gates()`'s per-group pipeline before this function
        # is ever reached) takes precedence; an action with none keeps
        # inheriting the contract's top-level `capability_id` exactly as
        # before this milestone - so a single-capability chain builds
        # the identical `steps` list it always did.
        steps = [
            {
                "capability": (a.get("capability") if isinstance(a.get("capability"), str) and a.get("capability") else capability_id),
                "action": a["name"],
                "inputs": a.get("inputs") or {},
                **({"reference_bindings": tuple(a["reference_bindings"])}
                   if a.get("reference_bindings") else {}),
                **({"reference_recheck": lambda checks=tuple(a["_reference_rechecks"]): all(check() for check in checks)}
                   if a.get("_reference_rechecks") else {}),
            }
            for a in actions
        ]
        envelope = dispatch.dispatch_chain_explicit(
            steps, session_id=session_id, principal=principal,
        )
    if envelope is None:
        return None
    envelope = dict(envelope)
    envelope.pop("handled", None)
    return envelope


def _execute_legacy_capability(
    contract: Dict[str, Any],
    *,
    orchestrator: Any,
    session_id: Optional[str],
    user_text: str,
    principal: Any,
    current_turn_attachment_ids: Optional[Sequence[str]] = None,
    recent_conversation: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    """Canonical entry to the existing legacy ToolDispatcher boundary.

    This does not recreate planning or approval logic.  It only lets a
    Directory-validated, explicit single-action contract reach the same
    ApprovalGate that owns legacy tool execution today.
    """
    capability_id = contract.get("capability")
    actions = contract.get("actions") or []
    if (
        not isinstance(capability_id, str)
        or len(actions) != 1
        or not isinstance(actions[0], dict)
        or actions[0].get("name") != capability_id
    ):
        return None
    approval_gate = getattr(orchestrator, "approval_gate", None)
    if approval_gate is None:
        return None
    runtime_context: Dict[str, Any] = {
        "session_id": session_id,
        "request_text": user_text,
        "principal": principal,
    }
    # This is runtime-owned context derived from the validated Turn State,
    # never an action input proposed by the model.  Omit it entirely for
    # legacy turns so read_attached_file retains its historic session scan.
    if current_turn_attachment_ids is not None:
        runtime_context["current_turn_attachment_ids"] = current_turn_attachment_ids
    if capability_id == "generate_document":
        if recent_conversation:
            runtime_context["decision_context"] = {
                "recent_conversation": recent_conversation[-5:]
            }
        from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
        proposed_inputs = actions[0].get("inputs") or {}
        if not isinstance(proposed_inputs, dict):
            return None
        allowed = LEGACY_TOOL_PARAMETERS[capability_id]["properties"]
        runtime_context.update({key: value for key, value in proposed_inputs.items() if key in allowed and key != "request_text"})
    if capability_id == "google_workspace_create":
        # The native Brain's structured arguments are proposals, never
        # authority. Pass only this tool's declared content fields through
        # the existing approval gate; runtime identity/session stay owned
        # by URI and cannot be replaced by model input.
        from uri_core.core.tool_schema import LEGACY_TOOL_PARAMETERS
        proposed_inputs = actions[0].get("inputs") or {}
        if not isinstance(proposed_inputs, dict):
            return None
        allowed = LEGACY_TOOL_PARAMETERS[capability_id]["properties"]
        runtime_context.update({key: value for key, value in proposed_inputs.items() if key in allowed})
    result = approval_gate.execute_tool(capability_id, **runtime_context)
    status = result.get("status")
    if status == "awaiting_approval":
        execution_status = "awaiting_approval"
    else:
        from uri_core.core.dispatcher import real_tool_status
        execution_status = real_tool_status(result)
    return {
        "status": "success" if execution_status in {"success", "ok", "awaiting_approval"} else "unavailable",
        "plan": {"status": "capability_selected", "capability": capability_id, "action": capability_id, "source": "canonical"},
        "execution": {"status": execution_status, "capability": capability_id, "action": capability_id},
        "response": result.get("data", result),
    }


def decide_fallback_reason(
    *,
    gate_outcome: str,
    capability_id: Optional[str],
    mode: Optional[str],
    reasons: Sequence[str] = (),
    capability_ids: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Pure, deterministic, model-free: the exact eligibility check
    `run_canonical_for_ask()` applies once a Decision Contract and its
    real GateResult already exist. Returns None (proceed to execute)
    only when the gate is READY, the capability is explicitly
    allowlisted, and the mode is one that has a real action to run -
    otherwise names the specific reason execution never happens, for
    both correctness and telemetry. Extracted as its own function so
    every non-READY outcome's fallback behavior is unit-testable
    without any model or orchestrator involved.

    `reasons` is the GateResult's own `reasons` list, inspected only for
    one specific, already-uniquely-named string:
    "false_unsupported_claim_rejected_by_directory" - decision_gates.py's
    own real, decided verdict that the model's "unsupported" claim is
    false because a plausibly-matching, available capability exists. That
    verdict is a completed canonical decision, not an engine/proposal
    defect - it happens to reuse the INVALID_PROPOSAL outcome value, but
    dispatching it as an engine failure would fall back to legacy for a
    turn canonical already decided correctly. Every other INVALID_PROPOSAL
    cause (malformed contract, unknown capability/action, a continuation
    with no active pointer, a mode requiring a capability that named none)
    is unaffected and still falls back exactly as before.

    `capability_ids` (M34 C3.3, optional, additive): for a heterogeneous
    `multi_action` proposal, EVERY distinct effective capability the
    proposal can dispatch must be supplied by the caller's canonical
    contract calculation and be allowlisted. Omitted (every caller before
    this milestone, and every single-capability proposal after it) falls
    back to checking exactly `capability_id` alone. This closes the
    per-action-override authority gap: `URI_CANONICAL_EXECUTION_ALLOWLIST`
    narrows canonical authority for EVERY capability a proposal can reach,
    not only the contract's top-level one."""
    if gate_outcome == "INVALID_PROPOSAL" and "false_unsupported_claim_rejected_by_directory" in reasons:
        return None
    if gate_outcome in {"INVALID_PROPOSAL", "DEGRADED"}:
        return f"engine_failure:{gate_outcome}"
    # M32.1: APPROVAL_REQUIRED now also reaches _execute_canonical() (see
    # run_canonical_for_ask's own dispatch condition below), so it must
    # pass through the SAME executable-mode/workflow-continuation/
    # allowlist checks READY already does - this function previously
    # returned None for APPROVAL_REQUIRED before ever reaching those
    # checks, which was safe only because APPROVAL_REQUIRED never
    # dispatched at all. Widening the outcome set here without this
    # would have silently skipped the allowlist/killswitch check for
    # every approval-required capability.
    if gate_outcome not in {"READY", "APPROVAL_REQUIRED"}:
        return None
    if mode not in EXECUTABLE_MODES:
        return None
    if mode == "workflow_continuation" and not workflow_continuation_mode_enabled():
        return "mode_not_executable:workflow_continuation"
    ids_to_check = list(capability_ids) if capability_ids is not None else [capability_id]
    if not all(is_allowlisted(one_id) for one_id in ids_to_check):
        return "canonical_killswitch_not_allowlisted"
    return None


def effective_capability_ids(contract: Dict[str, Any]) -> List[Optional[str]]:
    """Return every capability an execution contract can actually reach.

    Derived at the execution boundary rather than from GateResult rollups:
    gates report evaluation detail, while the allowlist must cover every
    action dispatch can address. Actions without an override retain the
    historical top-level identity. A no-action contract retains its
    pre-C3.3 top-level-only behavior.
    """
    top_level = contract.get("capability")
    actions = [action for action in (contract.get("actions") or []) if isinstance(action, dict)]
    raw_ids = [
        action.get("capability")
        if isinstance(action.get("capability"), str) and action.get("capability")
        else top_level
        for action in actions
    ] or [top_level]
    return list(dict.fromkeys(raw_ids))


def _is_heterogeneous_contract(contract: Dict[str, Any]) -> bool:
    return len(set(effective_capability_ids(contract))) > 1


def _canonical_nonexecution_envelope(
    contract: Dict[str, Any], gate_result: Any,
    capability_directory: Any = None,
) -> Dict[str, Any]:
    """Return a truthful terminal response for a valid non-execution turn.

    These outcomes are decisions, not failures.  In particular they must not
    be re-routed through the legacy planner simply because they are less
    convenient than an execution result.
    """
    outcome = getattr(gate_result, "outcome", "READY")
    missing = getattr(gate_result, "missing_field", None)
    clarification = contract.get("clarification")
    if outcome == "MISSING_PARAMETER" or contract.get("mode") == "clarification":
        message = clarification or (
            f"Please provide {missing}." if missing else "Please provide the missing information."
        )
        status, execution_status = "awaiting_user_response", "not_executed"
    elif outcome == "APPROVAL_REQUIRED" or contract.get("mode") == "approval_required":
        message = "This action requires your approval before it can run."
        status, execution_status = "approval_required", "not_executed"
    elif outcome == "DISCONNECTED" and contract.get("capability") and contract.get("mode") != "unsupported":
        message = "That capability is not connected right now."
        status, execution_status = "unavailable", "not_executed"
    elif outcome in {"UNSUPPORTED", "UNAVAILABLE", "PERMISSION_DENIED", "DISCONNECTED"} or contract.get("mode") == "unsupported":
        message = contract.get("unsupported_reason") or "URI cannot perform that request with an available capability."
        status, execution_status = "unavailable", "not_executed"
    else:
        message = contract.get("reason") or "I can help with that."
        status, execution_status = "success", "not_applicable"
    plan: Dict[str, Any] = {
        "status": "canonical_non_execution",
        "mode": contract.get("mode"),
        "capability": contract.get("capability"),
        "gate_outcome": outcome,
    }
    # M34 C3.3: for a heterogeneous proposal, report exactly which
    # capability/action(s) blocked the chain (the real per-group
    # GateResults, never re-derived) rather than only the aggregate
    # outcome - so a denial or approval requirement on one action in a
    # multi-capability chain is never reported as an undifferentiated,
    # unexplained failure of the whole turn.
    sub_results = getattr(gate_result, "sub_results", None) or []
    if sub_results:
        plan["per_capability"] = [
            {"capability_id": sub.capability_id, "outcome": sub.outcome, "action_names": list(sub.action_names)}
            for sub in sub_results
        ]
    response = {"message": message}
    if contract.get("mode") == "conversation" and execution_status == "not_applicable":
        response["available_capabilities"] = _conversation_capability_evidence(
            capability_directory
        )
    return {
        "status": status,
        "canonical_outcome": outcome,
        "plan": plan,
        "execution": {"status": execution_status, "capability": contract.get("capability")},
        "response": response,
    }


def _conversation_capability_evidence(capability_directory: Any) -> List[Dict[str, Any]]:
    """Bound current-user directory facts for the drafting Brain, without selecting a tool."""
    if capability_directory is None:
        return []
    try:
        summaries = capability_directory.summaries()
    except Exception:
        return []
    evidence = []
    for entry in summaries:
        if not isinstance(entry, dict):
            continue
        available = entry.get("available")
        if available is None and entry.get("source") == "multi_action":
            try:
                detail = capability_directory.describe(entry.get("capability_id"))
                available = detail.get("available") if isinstance(detail, dict) else None
            except Exception:
                available = None
        if available is not True:
            continue
        capability_id = entry.get("capability_id")
        if not isinstance(capability_id, str) or not capability_id:
            continue
        evidence.append({
            "id": capability_id[:80],
            "summary": str(entry.get("summary") or "")[:160],
            "requires_approval": entry.get("approval_required"),
        })
        if len(evidence) == 32:
            break
    return evidence


def _ready_read_prefix(contract, directory, principal, turn_state_data):
    """Return a gated read prefix when later inputs must come from its evidence.

    The whole proposal remains blocked. This only selects already-proposed
    actions; it neither binds missing inputs nor authorizes a later write.
    """
    from uri_core.core.decision_engine import DecisionOutcome
    from uri_core.core.decision_gates import evaluate_gates

    if contract.get("mode") != "multi_action":
        return []
    actions = contract.get("actions") or []
    if len(actions) < 2:
        return []
    # Legacy read tools use the same gate but have no multi-action dispatch.
    # Execute one independently ready read, then return its evidence to the
    # Brain. The suffix is never executed from this proposal.
    first = actions[0]
    first_id = first.get("capability") or contract.get("capability") if isinstance(first, dict) else None
    if isinstance(first, dict) and first_id in {"web_search", "fetch_url"} and first.get("name") == first_id:
        if not is_allowlisted(first_id):
            return []
        verdict = evaluate_gates(
            DecisionOutcome(status="ok", contract={**contract, "capability": first_id, "actions": [first]}),
            capability_directory=directory, principal=principal,
            turn_state_data=turn_state_data,
        )
        return [first] if verdict.outcome == "READY" else []
    prefix = []
    blocked = False
    # These are fields obtainable from earlier message evidence, not a
    # judgment about the user's words or an invented argument value.
    evidence_fields = {"message_id", "thread_id", "attachment_id", "to", "subject", "body", "reply_to", "in_reply_to_thread_id"}
    for action in actions:
        if not isinstance(action, dict) or not action.get("name"):
            return []
        capability_id = action.get("capability") or contract.get("capability")
        if not is_allowlisted(capability_id):
            return []
        detail = directory.describe(capability_id) if directory is not None else None
        schema = (detail or {}).get("action_schemas", {}).get(action["name"])
        if not isinstance(schema, dict):
            return []
        one_contract = {**contract, "capability": capability_id, "actions": [action]}
        verdict = evaluate_gates(
            DecisionOutcome(status="ok", contract=one_contract),
            capability_directory=directory, principal=principal,
            turn_state_data=turn_state_data,
        )
        if not blocked and verdict.outcome == "READY" and schema.get("read_only") is True:
            prefix.append(action)
            continue
        if verdict.outcome != "MISSING_PARAMETER" or not prefix:
            return []
        inputs = action.get("inputs") or {}
        missing = set(schema.get("required") or []) - set(inputs)
        if not missing or not missing <= evidence_fields:
            return []
        blocked = True
    # Gmail's search result contains message ids, sender, subject and
    # bounded bodies. A label listing, despite being read-only, does not
    # provide those values and must not unlock a dependent read/draft.
    has_message_evidence = any(
        (a.get("capability") or contract.get("capability")) == "Gmail"
        and a["name"] == "search_messages"
        for a in prefix
    )
    return prefix if blocked and has_message_evidence else []


def _execute_canonical(
    contract: Dict[str, Any],
    *,
    orchestrator: Any,
    session_id: Optional[str],
    user_text: str,
    principal: Any,
    current_turn_attachment_ids: Optional[Sequence[str]] = None,
    recent_conversation: Optional[List[Dict[str, Any]]] = None,
) -> Optional[Dict[str, Any]]:
    if reference_clarification_enabled() and contract.get("reference_slots"):
        slots = contract["reference_slots"]
        actions = contract.get("actions") or []
        if not isinstance(slots, list) or any(
            not any(isinstance(action, dict)
                    and (action.get("capability") or contract.get("capability")) == slot.get("target", {}).get("capability_id")
                    and action.get("name") == slot.get("target", {}).get("action_name")
                    and any(binding.ref_key == slot.get("ref_key")
                            for binding in action.get("reference_bindings") or ())
                    for action in actions)
            for slot in slots if isinstance(slot, dict)
        ):
            return _reference_block(session_id, "REFERENCE_BINDING_MISSING")
    capability_id = contract.get("capability")
    # M33 Batch B: registry lookup, not a `capability_id == "Gmail"`
    # branch - Gmail is simply always present in `dispatch.registry` by
    # its own default construction (`MultiActionCapabilityRegistry([Gmail
    # Capability()])`, unchanged); any external capability `server.py`'s
    # user-context composition has published lives in the exact same
    # registry and is reached by the exact same generalized call below.
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    registry = getattr(dispatch, "registry", None)
    if (
        isinstance(capability_id, str)
        and registry is not None
        and registry.get_capability(capability_id) is not None
    ):
        # M34 C3.3: a heterogeneous proposal's per-action "capability"
        # overrides only ever reach `dispatch_chain_explicit()` - the
        # ONE existing mechanism that already authorizes and executes a
        # real per-step capability. If any referenced capability (top-
        # level or per-action) is NOT also registered in this same
        # `dispatch.registry`, no existing execution boundary can run
        # this specific mix safely (a legacy single-tool capability like
        # `remember_fact` has no chain concept at all) - decline here
        # (fall back to legacy for the whole turn, exactly like any
        # other `execution_dispatch_returned_none` case) rather than
        # inventing a new mixed-boundary execution path or silently
        # dropping/misrouting an action the model explicitly named.
        referenced_ids = {capability_id}
        for action in contract.get("actions") or []:
            if isinstance(action, dict):
                named = action.get("capability")
                if isinstance(named, str) and named:
                    referenced_ids.add(named)
        if len(referenced_ids) > 1 and not all(
            registry.get_capability(one_id) is not None for one_id in referenced_ids
        ):
            return None
        return _execute_multi_action(
            contract, capability_id=capability_id, orchestrator=orchestrator,
            session_id=session_id, user_text=user_text, principal=principal,
        )
    if reference_clarification_enabled() and contract.get("reference_slots"):
        return _reference_block(session_id, "LEGACY_REFERENCE_UNSUPPORTED")
    return _execute_legacy_capability(
        contract, orchestrator=orchestrator, session_id=session_id,
        user_text=user_text, principal=principal,
        current_turn_attachment_ids=current_turn_attachment_ids,
        recent_conversation=recent_conversation,
    )


def build_canonical_telemetry(
    *,
    session_id: Optional[str],
    user_text: str,
    contract: Dict[str, Any],
    gate_result: Any,
    recall_at_5: Optional[bool],
    canonical_attempted: bool,
    envelope: Optional[Dict[str, Any]],
    fallback_used: bool,
    fallback_reason: Optional[str],
) -> Dict[str, Any]:
    """Privacy-safe by construction, mirroring `build_shadow_trace`'s
    own discipline: no raw user text, no raw tool output content - only
    status/id/enum fields already treated as non-sensitive elsewhere in
    this codebase."""
    execution_evidence_returned = bool(
        canonical_attempted and envelope is not None and envelope.get("execution") is not None
    )
    grounded_final_response = bool(
        canonical_attempted and envelope is not None and envelope.get("response") is not None
    )
    return {
        "timestamp": time.time(),
        "session_id": session_id,
        "user_text_length_bucket": len(user_text) // 20 * 20 if user_text else 0,
        "canonical_mode": contract.get("mode"),
        "selected_capability": contract.get("capability"),
        "selected_actions": [
            a.get("name") for a in (contract.get("actions") or []) if isinstance(a, dict)
        ],
        # M34 C3.3: per-action capability identity, additive - {action:
        # capability} for every action, falling back to the contract's
        # top-level `capability` for an action with no override of its
        # own (every contract before this milestone, and every single-
        # capability one after it, so `selected_capability` above
        # already told the whole story for those - this field's real
        # audit value appears only once a heterogeneous proposal exists).
        "action_capabilities": [
            {
                "action": a.get("name"),
                "capability": (
                    a.get("capability")
                    if isinstance(a.get("capability"), str) and a.get("capability")
                    else contract.get("capability")
                ),
            }
            for a in (contract.get("actions") or []) if isinstance(a, dict)
        ],
        "candidate_recall_at_5": recall_at_5,
        "gate_outcome": getattr(gate_result, "outcome", None),
        "canonical_execution_attempted": canonical_attempted,
        "canonical_execution_result": (envelope or {}).get("status") if envelope else None,
        "fallback_used": fallback_used,
        "fallback_reason": fallback_reason,
        "execution_evidence_returned": execution_evidence_returned,
        "grounded_final_response": grounded_final_response,
    }


def record_canonical_telemetry(
    telemetry: Dict[str, Any], path: str = DEFAULT_TELEMETRY_LOG_PATH
) -> None:
    # Reuses `record_shadow_trace`'s exact append-only, best-effort
    # semantics - never raises, never affects the real response.
    record_shadow_trace(telemetry, path=path)


def run_canonical_for_ask(
    *,
    orchestrator: Any,
    session_id: Optional[str],
    user_text: str,
    principal: Any,
    personalization_context: Any = None,
    log_path: str = DEFAULT_TELEMETRY_LOG_PATH,
    decision_observer: Any = None,
    current_turn_attachments: Optional[List[Dict[str, Any]]] = None,
    arn_state: Optional[Any] = None,
    reference_resume: Optional[Dict[str, Any]] = None,
    reference_root: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """The single M30.6 entry point for a live `/ask` call site
    (`server.py`). Returns a full `{"status", "session_id", "execution",
    "response", ...}` envelope - the SAME shape `/ask` already relays to
    the client - only when canonical execution actually ran for an
    allowlisted, gate-READY proposal; returns None in every other case
    (invalid contract, non-READY gate, non-allowlisted capability,
    non-executable mode, or any internal failure), so the caller's
    existing legacy `result` is used completely unchanged. Never
    raises."""
    from uri_core.core.decision_gates import evaluate_gates
    from uri_core.core.decision_engine import candidate_recall_at_k

    contract: Dict[str, Any] = {}
    gate_result = None
    recall_at_5 = None
    envelope: Optional[Dict[str, Any]] = None
    fallback_reason: Optional[str] = None
    canonical_attempted = False
    reference_dispatch_started = time.monotonic()

    try:
        turn_state_result, directory = build_turn_state_and_directory(
            orchestrator=orchestrator, session_id=session_id,
            user_text=user_text, principal=principal,
            current_turn_attachments=current_turn_attachments,
            arn_state=arn_state,
        )

        decision = propose_decision(
            turn_state_data=turn_state_result.data,
            capability_directory=directory,
            principal=principal,
            preselect=True,
        )

        if decision.status != "ok" or decision.contract is None:
            detail = str(decision.invalid_reason or decision.status)
            if reference_clarification_enabled() and "reference_slots" in detail:
                return _reference_block(session_id, "INVALID_REFERENCE_PROPOSAL")
            terminal = "provider" in detail.lower() and "unavailable" in detail.lower()
            fallback_reason = (
                "MODEL_TERMINALLY_UNAVAILABLE" if terminal
                else f"engine_failure:INVALID_PROPOSAL:{detail}"
            )
        else:
            contract = decision.contract
            if reference_clarification_enabled():
                try:
                    contract, reference_terminal = _reference_prepare(
                        contract, user_text=user_text, session_id=session_id,
                        orchestrator=orchestrator, principal=principal, directory=directory,
                        attachments=current_turn_attachments, resumed=reference_resume,
                        journal_root=reference_root, telemetry_path=log_path,
                    )
                except Exception:
                    return _reference_block(session_id, "REFERENCE_VALIDATION_UNAVAILABLE")
                if reference_terminal is not None:
                    return reference_terminal
                if contract is not decision.contract:
                    from uri_core.core.decision_engine import DecisionOutcome
                    decision = DecisionOutcome(status="ok", contract=contract)
            reference_dispatch_started = time.monotonic()
            gate_result = evaluate_gates(
                decision, capability_directory=directory, principal=principal,
                turn_state_data=turn_state_result.data,
            )
            if decision_observer is not None:
                try:
                    decision_observer(contract, gate_result)
                except Exception:
                    pass
            recall_at_5 = candidate_recall_at_k(
                turn_state_result.data, directory, contract.get("capability"), k=5
            )

            capability_id = contract.get("capability")
            mode = contract.get("mode")

            # M34 C3.3: check every capability dispatch could actually
            # reach, including an override shape that happens to form only
            # one gate group. GateResult sub-results are evidence, not the
            # allowlist authority source.
            capability_ids = effective_capability_ids(contract)

            fallback_reason = decide_fallback_reason(
                gate_outcome=gate_result.outcome, capability_id=capability_id, mode=mode,
                reasons=getattr(gate_result, "reasons", ()),
                capability_ids=capability_ids,
            )
            read_prefix = (
                _ready_read_prefix(contract, directory, principal, turn_state_result.data)
                if gate_result.outcome in {"MISSING_PARAMETER", "READY"} and fallback_reason is None
                and not (reference_clarification_enabled() and contract.get("reference_slots"))
                else []
            )
            if read_prefix:
                # Reuse canonical dispatch with a contract containing only
                # independently gated read actions. The deferred suffix is
                # evidence for the drafting Brain, never dispatched here.
                prefix_contract = {
                    **contract,
                    "capability": read_prefix[0].get("capability") or capability_id,
                    "actions": [
                        {**a, "capability": a.get("capability") or capability_id}
                        for a in read_prefix
                    ],
                }
                canonical_attempted = True
                envelope = _execute_canonical(
                    prefix_contract, orchestrator=orchestrator,
                    session_id=session_id, user_text=user_text, principal=principal,
                )
                if envelope is None:
                    fallback_reason = "execution_dispatch_returned_none"
                else:
                    envelope = dict(envelope)
                    envelope["plan"] = {
                        **envelope.get("plan", {}),
                        "partial_read_only": True,
                        "deferred_actions": [
                            {"capability": a.get("capability") or capability_id, "name": a["name"]}
                            for a in contract["actions"][len(read_prefix):]
                        ],
                    }
                    envelope["execution"] = {
                        **envelope.get("execution", {}), "partial_read_only": True,
                    }
                    if isinstance(envelope.get("response"), dict):
                        envelope["response"] = {
                            **envelope["response"],
                            "available_capabilities": _conversation_capability_evidence(directory),
                        }
            # M32.1: APPROVAL_REQUIRED now also reaches _execute_canonical()
            # - previously only READY did, which meant an approval-required
            # capability never reached ApprovalGate/ApprovalStore (or the
            # Gmail bridge above) at all and could never be durably
            # proposed. decide_fallback_reason() above already applies the
            # same executable-mode/allowlist gate to this outcome now, so
            # this widening cannot reach an un-allowlisted capability.
            if envelope is None and (
                fallback_reason is None
                and gate_result.outcome in ("READY", "APPROVAL_REQUIRED")
                and not (
                    gate_result.outcome == "APPROVAL_REQUIRED"
                    and _is_heterogeneous_contract(contract)
                )
                and mode in EXECUTABLE_MODES
            ):
                canonical_attempted = True
                # /ask supplied this list only after resolving the explicit
                # handles against the authenticated user's FileStore and the
                # request session.  Preserve an explicit-but-malformed list
                # as an empty explicit context (fail closed at the tool),
                # never as permission to scan older session files.
                attachment_ids = None
                if current_turn_attachments:
                    attachment_ids = [
                        item.get("file_id")
                        for item in current_turn_attachments
                        if isinstance(item, dict) and isinstance(item.get("file_id"), str)
                    ]
                envelope = _execute_canonical(
                    contract, orchestrator=orchestrator, session_id=session_id,
                    user_text=user_text, principal=principal,
                    current_turn_attachment_ids=attachment_ids,
                    recent_conversation=turn_state_result.data.get("recent_conversation"),
                )
                if envelope is None:
                    fallback_reason = "execution_dispatch_returned_none"
                else:
                    if reference_clarification_enabled() and contract.get("reference_slots"):
                        _reference_record_dispatch(
                            contract, envelope, principal, session_id, reference_root,
                            telemetry_path=log_path)
                    from uri_core.core.arn import attach_not_found_recovery

                    envelope = attach_not_found_recovery(
                        envelope,
                        goal=user_text,
                        source=str(capability_id or "capability_lookup"),
                        query=user_text,
                        state=arn_state,
                    )
            elif envelope is None and fallback_reason is None:
                envelope = _canonical_nonexecution_envelope(
                    contract, gate_result, capability_directory=directory
                )
    except Exception as exc:
        fallback_reason = f"canonical_execution_error:{exc}"
        envelope = None

    fallback_required = fallback_reason is not None
    if reference_clarification_enabled() and contract.get("reference_slots"):
        _record_reference_stage(
            path=log_path, session_id=str(session_id or ""), stage="dispatch",
            outcome=str((envelope or {}).get("execution", {}).get("status") or "not_executed"),
            started=reference_dispatch_started,
            reason="FALLBACK_BLOCKED" if fallback_required else "",
        )
    telemetry = build_canonical_telemetry(
        session_id=session_id, user_text=user_text, contract=contract,
        gate_result=gate_result, recall_at_5=recall_at_5,
        canonical_attempted=canonical_attempted, envelope=envelope,
        fallback_used=fallback_required, fallback_reason=fallback_reason,
    )
    record_canonical_telemetry(telemetry, path=log_path)

    if fallback_required:
        return {
            "_canonical_fallback": True,
            "fallback_reason": fallback_reason,
            "gate_outcome": getattr(gate_result, "outcome", "INVALID_PROPOSAL"),
        }

    envelope = dict(envelope)
    envelope["session_id"] = session_id
    if contract.get("_tentative_bindings"):
        envelope["tentative_binding"] = contract["_tentative_bindings"][0]
    envelope.setdefault("semantic_analysis", None)
    envelope.setdefault("error", None)

    # M32 B1.6: `_draft_narrative_safely` already guarantees (by its own
    # docstring and internal except clauses) that it never raises - any
    # drafting/validation failure calls `mark_narrative_unavailable` on
    # `envelope` itself before returning. Execution has already happened
    # by this point, so falling back to legacy here would risk a second,
    # duplicate dispatch of an already-completed side effect - not a
    # safe or correct fix. The residual gap this closes is narrower:
    # if `_draft_narrative_safely` were ever to raise anyway (a defect
    # in that guarantee, not something to assume away), the previous
    # bare `except: pass` left `envelope` with no narrative and no
    # honest reason at all. This is defense in depth, not a new
    # fallback path.
    try:
        orchestrator._draft_narrative_safely(
            user_text=user_text, response=envelope,
            personalization_context=personalization_context, session_id=session_id,
        )
    except Exception as exc:
        try:
            from uri_core.core.response_drafting import mark_narrative_unavailable

            mark_narrative_unavailable(envelope, exc, principal)
        except Exception:
            pass

    try:
        orchestrator._persist_session(session_id)
    except Exception:
        pass

    return envelope
