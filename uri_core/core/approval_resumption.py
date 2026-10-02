"""M32.1: durable resumed approval across turns.

Bridges a later natural-language message ("yes", "approve", "go
ahead") to the correct pending `ProposedAction` in `ApprovalStore`,
for exactly one session, exactly one unambiguous pending action, using
ONLY existing, already-tested dispatch entry points
(`ApprovalGate.decide()`, `MultiActionDispatch.dispatch_explicit()`).

This module never executes anything itself and never invents a new
authorization boundary - it only decides WHICH already-existing,
already-audited decide/dispatch call to make, using the SAME
`ApprovalStore` every other approval path already reads and writes.
Session isolation, expiry, single-use consumption, and fail-closed
error handling are inherited entirely from `ApprovalStore`'s own
existing behaviour (`propose`/`decide`/`consume`) - this module adds
no parallel state of its own.

`resume_pending_approval()` never raises and never guesses: it returns
`None` whenever resumption does not clearly apply, so the caller
(`server.py`'s `/ask`) falls through to completely normal processing
for that turn - the exact same "None means fall back" convention every
other M32/M32.1-era seam in this codebase already follows
(`run_native_tool_loop()`, `run_canonical_for_ask()`).
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

# M32.1: default-OFF, matching this repo's own standing convention for
# every prior newly-added risk-bearing behavior (native_tool_loop_
# enabled(), decision_engine_live_enabled(), workflow_continuation_
# mode_enabled() were all shipped default-off first).
APPROVAL_RESUMPTION_ENV_VAR = "URI_ENABLE_APPROVAL_RESUMPTION"


def approval_resumption_enabled() -> bool:
    return os.environ.get(APPROVAL_RESUMPTION_ENV_VAR) == "1"

from uri_core.core.approval_store import ApprovalError, ApprovalStore, ProposedAction


def _binding_principal(orchestrator: Any, principal: Any, session_id: str):
    from datetime import datetime, timezone
    from uri_desktop_seams.reference_clarification.evidence import (
        EvidenceCandidate, _file_item, _provider_fields, _provider_version,
    )
    from uri_desktop_seams.reference_clarification.service import BindingPrincipal
    from uri_desktop_seams.reference_clarification.store import ClarificationJournal
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    file_store = getattr(getattr(orchestrator, "approval_gate", None), "file_store", None)
    if principal is None or not getattr(principal, "user_id", None) or not session_id:
        raise ValueError("authenticated approval context unavailable")

    def read_source(source_class, locator):
        if source_class in {"file", "attachment", "conversation"}:
            if file_store is None:
                return None
            for record in file_store.list_for_session(session_id):
                item = _file_item(file_store, record, principal.user_id, session_id,
                                  datetime.now(timezone.utc), set())
                if item is not None and item.locator == locator:
                    return item
            return None
        if source_class == "gmail" and dispatch is not None:
            capability = dispatch.registry.get_capability("Gmail")
            if capability is None or not dispatch._action_permitted("Gmail", "read_message", principal):
                return None
            result = capability.read_message(locator)
            record = result.get("message") if result.get("status") == "success" else None
        elif source_class == "drive":
            from uri_core.core.capability_resolver import CapabilityResolver
            if not CapabilityResolver.is_allowed("drive_search", principal=principal):
                return None
            from uri_core.services.drive_service import DriveService
            service = DriveService(user_id=principal.user_id)
            if not service.connect().get("success"):
                return None
            try:
                record = service.service.files().get(
                    fileId=locator, fields="id,name,mimeType,modifiedTime,version"
                ).execute()
            except Exception:
                return None
        else:
            return None
        if not isinstance(record, dict):
            return None
        source_id, title, candidate_type, owner = _provider_fields(source_class, record)
        if source_id != locator or not title:
            return None
        return EvidenceCandidate(
            f"{source_class}:{principal.user_id}:{source_id}", source_id, source_class,
            title, candidate_type, source_id, _provider_version(source_class, record),
            datetime.now(timezone.utc).isoformat(), principal.user_id, None, owner=owner,
        )

    def get_action(capability_id, action_name):
        capability = dispatch.registry.get_capability(capability_id) if dispatch else None
        return capability.get_action(action_name) if capability else None

    def has_grant(capability_id, action_name):
        return bool(dispatch and dispatch._action_permitted(capability_id, action_name, principal))

    def read_binding(round_id):
        root = str(Path(file_store.storage_dir).parent.parent) if file_store is not None else None
        journal_store = ClarificationJournal(**({"root": root} if root else {}))
        with journal_store.transaction(principal.user_id, session_id) as journal:
            return journal.store.bindings.get(round_id)

    return BindingPrincipal(principal.user_id, session_id, read_source,
                            has_grant, get_action, read_binding)


def _recheck_binding(orchestrator: Any, principal: Any, session_id: str,
                     record: ProposedAction):
    if not record.requires_reference_binding:
        return None
    from uri_desktop_seams.reference_clarification.service import (
        ApprovalBindingIdentity, revalidate_binding_identity,
    )
    identity = record.binding_identity
    if (type(identity) is not ApprovalBindingIdentity or not identity.slots
            or any(slot.capability_id != record.capability_id
                   or slot.action_name != (record.action_name or record.capability_id)
                   for slot in identity.slots)):
        raise ValueError("approval reference identity is missing or changed")
    return revalidate_binding_identity(
        _binding_principal(orchestrator, principal, session_id), identity)

# Conservative, deterministic, whole-message matching only - never a
# substring search inside a longer sentence, so a genuinely new request
# that happens to contain the word "yes" elsewhere is never misread as
# a confirmation. Matched case-insensitively against the trimmed,
# punctuation-stripped message.
_AFFIRMATIVE = {
    "yes", "yes please", "yeah", "yep", "yup", "approve", "approved",
    "go ahead", "do it", "confirm", "confirmed", "ok", "okay", "sure",
    "please proceed", "proceed",
}
_NEGATIVE = {
    "no", "nope", "cancel", "never mind", "nevermind", "stop", "reject",
    "don't", "do not", "no thanks",
}

_STRIP_PUNCTUATION = re.compile(r"[.!?,;:]+$")


def classify_confirmation(text: str) -> Optional[bool]:
    """True for a clear affirmative, False for a clear negative, None
    for anything else - including anything longer/more elaborate than
    a short confirmation phrase, which is deliberately never treated as
    one. Never guesses."""
    if not isinstance(text, str):
        return None
    normalized = _STRIP_PUNCTUATION.sub("", text.strip().lower())
    if normalized in _AFFIRMATIVE:
        return True
    if normalized in _NEGATIVE:
        return False
    return None


def find_resumable_actions(
    approval_store: ApprovalStore, session_id: Optional[str]
) -> List[ProposedAction]:
    """Every non-expired PENDING action for this exact session, oldest
    first. Cross-session isolation: only ever filters by an exact
    `session_id` match - never a prefix, never "no session recorded"."""
    if not session_id:
        return []
    pending = [
        action
        for action in approval_store.list_pending()
        if action.session_id == session_id
    ]
    pending.sort(key=lambda a: a.created_at)
    return pending


def _clarification_envelope(pending: List[ProposedAction]) -> Dict[str, Any]:
    """Deterministic, never model-generated: names each pending action
    so the user can specify which one, rather than guessing or falling
    through to a fresh interpretation that would likely confuse a plain
    'yes' with an unrelated new request."""
    options = [
        {
            "action_id": action.action_id,
            "capability": action.capability_id,
            "action": action.action_name or action.capability_id,
        }
        for action in pending
    ]
    names = "; ".join(f"{o['capability']}/{o['action']}" for o in options)
    return {
        "status": "clarification_required",
        "session_id": None,
        "error": None,
        "semantic_analysis": None,
        "execution": {"status": "not_executed", "pending_actions": options},
        "response": {
            "message": (
                "You have more than one action awaiting approval "
                f"({names}). Please say which one, or use its own "
                "approval control."
            )
        },
        "narrative": None,
    }


def _error_envelope(session_id: Optional[str], message: str) -> Dict[str, Any]:
    return {
        "status": "error",
        "session_id": session_id,
        "error": message,
        "semantic_analysis": None,
        "execution": {"status": "not_executed"},
        "response": {"message": message},
        "narrative": None,
    }


def resume_by_action_id(*, orchestrator: Any, action_id: str,
                        session_id: str, approved: bool, principal: Any,
                        user_text: str = "") -> Dict[str, Any]:
    """Shared API/chat resume path for a specific durable proposal."""
    gate = getattr(orchestrator, "approval_gate", None)
    store = getattr(gate, "approval_store", None)
    if store is None:
        return _error_envelope(session_id, "Approval store unavailable.")
    record = store.get(action_id)
    if record is None or record.session_id != session_id:
        return _error_envelope(session_id, "Approval is unavailable for this session.")
    if record.action_name is None:
        result = gate.decide(action_id, approved=approved, session_id=session_id,
                             binding_principal=(_binding_principal(orchestrator, principal, session_id)
                                                if record.requires_reference_binding else None))
        return {"status": "success" if result.get("status") not in {"error", "rejected"} else "error",
                "session_id": session_id, "execution": {"status": result.get("status"), "action_id": action_id},
                "response": result, "narrative": None}
    if not approved:
        try:
            store.decide(action_id, approved=False, session_id=session_id)
        except ApprovalError as exc:
            return _error_envelope(session_id, str(exc))
        return {"status": "cancelled", "session_id": session_id,
                "execution": {"status": "not_executed", "action_id": action_id},
                "response": {"message": "Cancelled - that action will not be performed."},
                "narrative": None}
    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    if dispatch is None:
        return _error_envelope(session_id, "Approve this action in chat when the dispatcher is available.")
    try:
        _recheck_binding(orchestrator, principal, session_id, record)
        decided = store.decide(action_id, approved=True, session_id=session_id)
        bindings = _recheck_binding(orchestrator, principal, session_id, decided)
        store.consume(action_id, capability_id=decided.capability_id,
                      arguments=decided.arguments, session_id=session_id)
    except (ApprovalError, ValueError, TypeError) as exc:
        try:
            gate._record_audit_safely(event_type="capability_execution", status="approval_binding_rejected",
                                      session_id=session_id, capability=record.capability_id,
                                      metadata={"action_id": action_id, "reason": type(exc).__name__})
        except Exception:
            pass
        return _error_envelope(session_id, "Approval reference changed or is unavailable; please retry the request.")
    envelope = dispatch.dispatch_explicit(
        decided.capability_id, decided.action_name, decided.arguments,
        session_id=session_id, user_text=user_text, principal=principal,
        user_approved=True,
        **({"reference_bindings": bindings} if bindings is not None else {}),
    )
    if envelope is None:
        return _error_envelope(session_id, "Approval was recorded, but the action could not be dispatched.")
    envelope = dict(envelope)
    envelope.pop("handled", None)
    envelope.setdefault("session_id", session_id)
    envelope.setdefault("narrative", None)
    envelope.setdefault("error", None)
    envelope.setdefault("semantic_analysis", None)
    envelope["execution"] = {**(envelope.get("execution") or {}), "action_id": action_id}
    return envelope


def resume_pending_approval(
    *,
    orchestrator: Any,
    session_id: Optional[str],
    user_text: str,
    principal: Any = None,
) -> Optional[Dict[str, Any]]:
    """The entry point. Returns None whenever resumption does not
    apply (not a confirmation phrase, or nothing pending) - the caller
    must then run this turn through completely normal /ask processing.
    Returns a terminal envelope dict when it does apply: either a
    resumed decision/dispatch result, a deterministic clarification
    (2+ pending, never guessed), or an honest error (expired/stale/
    already-decided/wrong-session - all detected by ApprovalStore's own
    existing checks, never re-implemented here)."""
    approval_gate = getattr(orchestrator, "approval_gate", None)
    approval_store = getattr(approval_gate, "approval_store", None)
    if approval_store is None:
        return None

    approved = classify_confirmation(user_text)
    if approved is None:
        return None

    pending = find_resumable_actions(approval_store, session_id)
    if not pending:
        return None
    if len(pending) > 1:
        return _clarification_envelope(pending)

    action = pending[0]

    from uri_core.core.canonical_execution import reference_clarification_enabled
    if reference_clarification_enabled():
        return resume_by_action_id(
            orchestrator=orchestrator, action_id=action.action_id,
            session_id=session_id, approved=approved, principal=principal,
            user_text=user_text,
        )

    try:
        record = approval_store.decide(
            action.action_id, approved=approved, session_id=session_id
        )
    except ApprovalError as exc:
        return _error_envelope(session_id, str(exc))

    if not approved:
        return {
            "status": "cancelled",
            "session_id": session_id,
            "error": None,
            "semantic_analysis": None,
            "execution": {"status": "not_executed", "action_id": action.action_id},
            "response": {"message": "Cancelled - that action will not be performed."},
            "narrative": None,
        }

    if record.action_name is None:
        # Legacy single-tool shape - reuse ApprovalGate.decide() exactly
        # as POST /approve already does (consume + dispatch, same
        # audit trail, same authorization checks re-run live).
        result = approval_gate.decide(
            action.action_id, approved=True, session_id=session_id
        )
        status = result.get("status")
        return {
            "status": "success" if status not in {"error"} else "error",
            "session_id": session_id,
            "error": result.get("message") if status == "error" else None,
            "semantic_analysis": None,
            "execution": {
                "status": "success" if status not in {"error"} else "unavailable",
                "action_id": action.action_id,
            },
            "response": result,
            "narrative": None,
        }

    # Multi-action (Gmail-shaped) - consume() first (this is what makes
    # a duplicate "yes" fail honestly instead of re-dispatching), THEN
    # dispatch through the exact same dispatch_explicit() a fresh
    # approval would use, with user_approved=True and the ORIGINAL,
    # already-bound inputs from turn 1 - never re-resolved against this
    # turn's "yes" text.
    try:
        approval_store.consume(
            action.action_id,
            capability_id=record.capability_id,
            arguments=record.arguments,
            session_id=session_id,
        )
    except ApprovalError as exc:
        return _error_envelope(session_id, str(exc))

    dispatch = getattr(orchestrator, "multi_action_dispatch", None)
    if dispatch is None:
        return _error_envelope(
            session_id,
            "Approval was recorded, but this session has no capability "
            "dispatcher available to execute it.",
        )

    envelope = dispatch.dispatch_explicit(
        record.capability_id, record.action_name, record.arguments,
        session_id=session_id, user_text=user_text, principal=principal,
        user_approved=True,
    )
    if envelope is None:
        return _error_envelope(
            session_id, "Approval was recorded, but the action could not be re-dispatched."
        )
    envelope = dict(envelope)
    envelope.pop("handled", None)
    execution = dict(envelope.get("execution") or {})
    execution["action_id"] = action.action_id
    envelope["execution"] = execution
    envelope.setdefault("session_id", session_id)
    envelope.setdefault("error", None)
    envelope.setdefault("semantic_analysis", None)
    envelope.setdefault("narrative", None)
    return envelope
