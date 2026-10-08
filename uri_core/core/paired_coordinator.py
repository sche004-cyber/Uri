"""C5 server-side paired turn coordinator (trusted composition).

Flow: selection (explicit, no fallback) -> canonical context -> untrusted proposal ->
intent discovery (reference binding, budgeted clarification, explicit confirmation) ->
execution proposal checked against the Confirmed Intent Contract -> existing deterministic
gates -> explicit user approval -> signed ticket (C4 control) -> client claim/execute/verify ->
receipt settle -> accurate reply.

Reuses prepare_for_paired_client / validate_canonical_proposal / ClientExecutionControl.
Introduces no reasoning engine, store or permission system. Pending arguments live in
memory only: a server restart fails closed (client must start a fresh turn).
A proposer (Brain, harness transport or the deterministic no-Brain rules below) can only
PROPOSE; it never approves, claims or settles.
"""
from __future__ import annotations

import hashlib
import re
import secrets
import time
import uuid

from uri_core.client_contracts import Binding, Wire, digest
from uri_core.core.client_execution_control import ClientExecutionControl, ExecutionControlError
from uri_core.core.client_service import ClientControlError, ExplicitGrants
from uri_core.core.client_state_ports import NeedsContext, StatePortError
from uri_core.core.intent_discovery import IntentDiscovery, _extract_harness, _extract_remember
from uri_core.core.paired_reasoning import (ReasoningSelectionPolicy, ReasoningUnavailable,
                                            prepare_for_paired_client, validate_canonical_proposal)
from uri_core.execution_contracts import ExecutionTicket

from pydantic import Field, StrictInt, model_validator
from typing import Literal

TERMINAL = {"reply", "failed", "cancelled", "expired"}
# Capabilities executed by an external provider in an isolated client workspace (copy-out only after
# verification): the only ones a provider-quota pause may close without effect.
PROVIDER_EXECUTED = {"external_harness_task"}
# failure_category prefix the client runtime uses ONLY when it refused before starting anything that could
# have an effect (no executor, unqualified/unavailable harness, invalid output name).
NOT_STARTED = "NOT_STARTED:"


class ApprovalRequest(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)
    decision: Literal["approve", "deny"]
    approval_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClaimRequest(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)
    ticket: dict
    execution_version: StrictInt = Field(ge=0)


class SettleRequest(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)
    ticket: dict
    receipt: dict


class WaitRequest(Binding):
    expected_version: StrictInt = Field(ge=0)
    idempotency_key: str = Field(min_length=16, max_length=128)
    checkpoint_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def _verifier(name, check):
    return (name, hashlib.sha256(name.encode()).hexdigest(), check)


DEFAULT_VERIFIERS = {
    "remember_fact": _verifier("uri.client.memory_readback.v1", "memory_readback"),
    "external_harness_task": _verifier("uri.client.harness_output_check.v1", "harness_output_check"),
}


def deterministic_proposer(prepared, request, selection):
    """No-Brain rules over the existing capability directory. Only explicit user wording
    produces an action; everything else is an honest conversation/unsupported answer."""
    text = request.text.strip()
    directory = prepared["directory"]
    base = {"goal": text[:200], "capability": None, "actions": [], "clarification": None,
            "unsupported_reason": None, "requires_approval": False, "confidence": 1.0,
            "reason": "deterministic_no_brain_rules"}
    # Provider-neutral: the executor is the user's explicit reasoning selection, never a name in the text.
    h = _extract_harness(text)
    hd = directory.describe("external_harness_task") if h else None
    if h and hd and hd["actions"]:
        # Only what the user actually said; a missing output file is asked for, never invented.
        inputs = {k: v for k, v in h.items() if v}
        return {**base, "mode": "single_action", "capability": "external_harness_task",
                "actions": [{"name": sorted(hd["actions"])[0], "inputs": inputs}]}
    m = re.match(r"^(?:please\s+)?(?:remember|save)\s+(?:that\s+|this\s*[:,]?\s*)?(.+)$", text, re.I | re.S)
    detail = directory.describe("remember_fact") if m else None
    if m and not detail:
        return {**base, "mode": "unsupported", "unsupported_reason": "capability_not_granted_to_client"}
    if m and detail and detail["actions"]:
        statement = _extract_remember(text).get("statement") or ""
        return {**base, "mode": "single_action", "capability": "remember_fact",
                "actions": [{"name": sorted(detail["actions"])[0],
                             "inputs": {"request_text": "remember that " + statement}}]}
    if re.search(r"\b(delete|erase|wipe|format|remove)\b.*\b(all|every|everything|files?|drive|disk)\b", text, re.I):
        return {**base, "mode": "unsupported", "unsupported_reason": "destructive_request_not_in_catalogue"}
    return {**base, "mode": "conversation"}


class PairedCoordinator:
    def __init__(self, service, runtime, policy, proposer=deterministic_proposer, qualified=("remember_fact",),
                 verifiers=None, clock=time.time, planner=None, interpreter=None):
        self.service, self.runtime, self.policy = service, runtime, policy
        self.proposer, self.qualified, self.clock = proposer, tuple(qualified), clock
        # planner(prepared, request, selection, confirmed_intent) -> execution proposal | None (Brain seam). It
        # may elaborate HOW; a proposal that changes WHAT is rejected and recompiled from the confirmed intent;
        # None means "no elaboration" and the confirmed intent is compiled deterministically.
        # interpreter(text, capability, slots, selection) -> {slot: value} (Brain seam). Bound per turn to the
        # user's explicit selection; its values must be verbatim user words and always need confirmation.
        # Either seam may raise ReasoningUnavailable: reported as such, never replaced by another source.
        self.planner, self.interpreter = planner, interpreter
        self.intents = IntentDiscovery(runtime.key)
        # capability -> (verifier_id, implementation_digest, evidence check name). Trusted composition only.
        self.verifiers = verifiers or dict(DEFAULT_VERIFIERS)
        self.pending = {}   # turn_id -> private pending state (memory only)
        self.control = ClientExecutionControl(runtime, authorize=self._authorize,
                                              verify_receipt=self._verify_receipt, clock=clock)

    # ---- phase 1: propose + gate -------------------------------------------------------------
    def __call__(self, record, request, identity, ports):
        env = lambda state, **f: (record.update(state=state), self.service._envelope(record, **f))[1]
        try:
            selection = self.policy.require(request.reasoning)
        except ReasoningUnavailable as exc:
            # Explicit selection unavailable: no fallback, no substitution. User must choose again.
            return env("failed", code=str(exc), message="The selected reasoning source is unavailable. "
                       "Choose another source explicitly; URI will not switch silently.")
        try:
            prepared = prepare_for_paired_client(self.service, request, identity, qualified_capabilities=self.qualified)
        except StatePortError as exc:
            return env("failed", code=str(exc))
        try:
            proposal = self.proposer(prepared, request, selection)
        except ReasoningUnavailable as exc:
            # The selected Brain failed or answered outside the contract: report it, never switch source.
            return env("failed", code=str(exc), message="The selected reasoning source could not produce a usable "
                       "proposal. Nothing was done. Choose a source explicitly to try again.")
        prior_turns = len(prepared["request"].get("recent_conversation") or [])
        if proposal.get("unsupported_reason") == "capability_not_granted_to_client":
            return env("reply", code="REFUSED_PERMISSION_DENIED", context={"prior_turns": prior_turns},
                       message="This client has not been granted that capability, so I did not do it.")
        permitted = {d["capability_id"] for d in prepared["directory"].summaries()}
        binding = {"principal_id": identity.principal.user_id, "client_id": identity.client_id,
                   "session_id": request.session_id}
        session = ports.read("sessions", "get_session", request.session_id)
        # Never interview the user about something this client may not do: ungranted requests skip
        # discovery and are refused by the existing gates below.
        intent_proposal = proposal if proposal.get("capability") in permitted else {"mode": "conversation"}
        current, _problem = self.intents.load(session, binding)
        if current is not None and self._ledger_revision(current["intent_id"]) > current["revision"]:
            # A validly signed but OLDER revision (e.g. replayed client state from before a correction)
            # must never resurrect superseded meaning.
            return env("reply", code="INTENT_STATE_STALE", context={"prior_turns": prior_turns},
                       session_update=self.intents.cleared(session),
                       message="The saved request is older than one already processed, so I set it aside. "
                               "Please restate what you want.")
        interpreter = None
        if self.interpreter is not None:
            interpreter = lambda text, capability, slots: self.interpreter(text, capability, slots, selection)
        try:
            outcome = self.intents.handle(text=request.text, decision=request.intent_decision,
                                          proposal=intent_proposal, binding=binding, session=session,
                                          ports=ports, turn_id=record["turn_id"], interpreter=interpreter)
        except StatePortError as exc:
            return env("failed", code=str(exc))
        except ReasoningUnavailable as exc:
            return env("failed", code=str(exc), message="The selected reasoning source could not interpret the "
                       "request. Nothing was done. Choose a source explicitly to try again.")
        intent = outcome.get("record")
        if intent is not None:
            # Durable server-side lineage: stale-replay and duplicate-execution guards read these.
            record["intent_id"], record["intent_revision"] = intent["intent_id"], intent["revision"]
        if outcome["kind"] == "needs_context":
            return env("needs_context", reads=outcome["reads"], code="INTENT_CONTEXT_REQUIRED")
        if outcome["kind"] in {"clarify", "confirm", "stopped"}:
            extra = {k: outcome[k] for k in ("clarification", "confirmation") if outcome.get(k) is not None}
            if intent is not None:
                extra["intent"] = self.intents.public(intent)
                extra["session_update"] = self.intents.session_with(session, intent)
            elif outcome.get("clear"):
                extra["session_update"] = self.intents.cleared(session)
            return env("reply", code=outcome["code"], message=outcome["message"],
                       context={"prior_turns": prior_turns}, **extra)
        replanned, rejected = False, None
        if outcome["kind"] == "confirmed" and self._intent_verified(intent["intent_id"]):
            # This exact confirmed intent already ran and was verified. A client that replays older saved
            # state (rollback, restore, stale device) must not obtain a second execution of it.
            return env("reply", code="INTENT_ALREADY_EXECUTED", context={"prior_turns": prior_turns},
                       session_update=self.intents.cleared(session),
                       message="That request was already carried out and verified, so I did not repeat it. "
                               "Start a new request if you want it done again.")
        if outcome["kind"] == "confirmed" and self._intent_possibly_executed(intent["intent_id"], record["turn_id"]):
            # A previous attempt for this exact intent was claimed and never settled: it may have run.
            # The client may not have persisted that fact (crash), so the server ledger decides.
            return env("reply", code="INTENT_EXECUTION_UNCERTAIN", context={"prior_turns": prior_turns},
                       intent=self.intents.public(intent),
                       message="A previous attempt at this request may already have run. Check the result first; "
                               "start a new request if it really needs to be done again.")
        if outcome["kind"] == "confirmed":
            compiled = self.intents.compile(intent)
            candidate = None
            if self.planner is not None:
                try:
                    candidate = self.planner(prepared, request, selection, self.intents.public(intent))
                except ReasoningUnavailable as exc:
                    # The confirmed intent is kept (session_update) so the user can retry explicitly.
                    return env("failed", code=str(exc), session_update=self.intents.session_with(session, intent),
                               message="The selected reasoning source could not plan the confirmed request. "
                                       "Nothing was done; your confirmed request is kept.")
            elif proposal.get("mode") == "single_action":
                candidate = proposal
            if candidate is None:
                candidate = compiled
            conflicts = self.intents.conflicts(intent, candidate)
            if conflicts:
                # The downstream proposal tried to change WHAT was confirmed: reject it, keep the evidence,
                # and execute the confirmed meaning compiled deterministically. Never reinterpret.
                replanned, rejected = True, {"digest": digest(candidate) if isinstance(candidate, dict) else None,
                                             "conflicts": conflicts}
                candidate = compiled
            proposal = candidate
        gate = validate_canonical_proposal(prepared, proposal, identity.principal,
                                           lambda cap, _principal: cap in permitted)
        if proposal.get("mode") == "conversation" and gate.outcome in {"READY", "INVALID_PROPOSAL"}:
            return env("reply", code="CONVERSATION", context={"prior_turns": prior_turns},
                       message="I can only act on an explicit request in this mode "
                               "(for example: 'remember that ...').")
        if gate.outcome not in {"READY", "APPROVAL_REQUIRED"}:
            refusal = {"PERMISSION_DENIED": "You have not granted this client that capability.",
                       "UNSUPPORTED": "That is not something URI can do.",
                       "UNAVAILABLE": "That capability is not available right now.",
                       "DISCONNECTED": "That capability's connection is not set up.",
                       "MISSING_PARAMETER": f"I need one more detail before I can act: {gate.missing_field}."}.get(
                gate.outcome, "I cannot safely act on that request.")
            code = "CLARIFICATION_REQUIRED" if gate.outcome == "MISSING_PARAMETER" else "REFUSED_" + gate.outcome
            extra = {"session_update": self.intents.session_with(session, intent)} if intent else {}
            return env("reply", code=code, gate=gate.to_dict(), message=refusal, **extra)
        if outcome["kind"] != "confirmed":
            # Executable arguments come ONLY from a Confirmed Intent Contract. A proposal that reaches here
            # unconfirmed (e.g. a Brain using multi_action for an intent capability, or naming a capability
            # intent discovery cannot interview for) would put proposer-chosen arguments in front of the
            # user; refuse it rather than ask the user to approve words they never said.
            return env("reply", code="REFUSED_UNCONFIRMED_ACTION", context={"prior_turns": prior_turns},
                       message="I can only act on a request I have confirmed with you. Nothing was done.")
        cap = gate.capability_id
        if cap not in self.verifiers:
            return env("reply", code="REFUSED_NO_VERIFIER", message="No independent verifier exists for that action.")
        action = proposal["actions"][0]
        args = {"action": action["name"], "inputs": action.get("inputs") or {}}
        args_digest = digest(args)
        intent_digest = intent["confirmed_digest"] if intent else None
        # Confirmed intent is frozen here: execution uses exactly these digest-bound arguments, and the
        # approval binds the Confirmed Intent Contract digest as well.
        approval_digest = digest({"turn": record["turn_id"], "op": record["operation_id"],
                                  "capability": cap, "args": args_digest, "intent": intent_digest})
        pend = {"capability": cap, "args": args, "args_digest": args_digest,
            "approval_digest": approval_digest, "approved": False, "denied": False, "ticket_issued": False,
            "principal_id": identity.principal.user_id, "client_id": identity.client_id,
            "verifier": self.verifiers[cap][:2], "check": self.verifiers[cap][2], "selection": selection.model_dump()}
        extra = {}
        if intent is not None:
            confirmed_session = self.intents.session_with(session, intent)
            ref = next(iter(intent["references"].values()), None)
            subject = ref if ref and ref.get("candidate_id") else None
            proposal_digest = digest(proposal)
            pend["sessions"] = {
                "verified": self.intents.session_with(confirmed_session, self.intents.after_execution(
                    intent, "verified", proposal_digest, replanned), clear=True, recent_subject=subject),
                "execution_uncertain": self.intents.session_with(confirmed_session, self.intents.after_execution(
                    intent, "execution_uncertain", proposal_digest, replanned)),
                "other": confirmed_session}
            extra = {"intent": self.intents.public(intent), "session_update": confirmed_session}
        self.pending[record["turn_id"]] = pend
        return env("approval_required", code="APPROVAL_REQUIRED", approval_request={
            "capability_id": cap, "argument_digest": args_digest, "approval_digest": approval_digest,
            "arguments": args, "effect": "local_write", "reversible": True, "gate": gate.to_dict(),
            "intent_digest": intent_digest, "replanned": replanned, "rejected_proposal": rejected}, **extra)

    # ---- phase 2: approval -> ticket ------------------------------------------------------------
    def approve(self, turn_id, body, identity):
        def step(record, live):
            pend = self.pending.get(turn_id)
            if record["state"] != "approval_required" or pend is None:
                raise ClientControlError("TURN_NOT_AWAITING_APPROVAL" if pend else "CONTEXT_REQUIRED_AFTER_RESTART")
            if body.approval_digest != pend["approval_digest"]:
                raise ClientControlError("APPROVAL_DIGEST_MISMATCH")
            if body.decision == "deny":
                pend["denied"] = True
                record["state"] = "cancelled"
                return self.service._envelope(record, code="APPROVAL_DENIED")
            pend["approved"] = True
            now = int(self.clock())
            ticket = ExecutionTicket(
                server_id=identity.server_id, client_id=identity.client_id, principal_id=identity.principal.user_id,
                session_id=record["session_id"], turn_id=turn_id, operation_id=record["operation_id"],
                ticket_id=str(uuid.uuid4()), generation=self.runtime.generation, capability_id=pend["capability"],
                argument_digest=pend["args_digest"], workspace_handle=str(uuid.uuid4()), workspace_version=0,
                approval_digest=pend["approval_digest"], approval_status="approved",
                verifier_id=pend["verifier"][0], implementation_digest=pend["verifier"][1],
                issued_at=now, expires_at=now + 60, deadline=now + 600, cancellation_nonce=secrets.token_hex(32))
            try:
                signed = self.control.prepare(ticket.model_dump(), identity)
            except ExecutionControlError as exc:
                pend["approved"] = False
                raise ClientControlError(str(exc), 403) from None
            pend["ticket_issued"] = True
            record["state"] = "ticket_issued"
            return self.service._envelope(record, code="TICKET_ISSUED", ticket=signed)
        return self.service.act(turn_id, body, identity, step)

    # ---- phase 3: claim / settle / provider wait --------------------------------------------------
    def claim(self, turn_id, body, identity):
        def step(record, live):
            if record["state"] != "ticket_issued":
                raise ClientControlError("TURN_NOT_CLAIMABLE")
            try:
                result = self.control.claim(body.ticket, identity, body.execution_version, body.idempotency_key)
            except ExecutionControlError as exc:
                raise ClientControlError(str(exc)) from None
            record["state"] = "executing"
            if result.get("dispatch") is True:
                record["dispatched"] = True     # durable: survives later state changes and restarts
            return self.service._envelope(record, code="CLAIMED", claim=result)
        return self.service.act(turn_id, body, identity, step)

    def settle(self, turn_id, body, identity):
        def step(record, live):
            prior = record["state"]
            if prior not in {"executing", "ticket_issued", "waiting_for_model"}:
                raise ClientControlError("TURN_NOT_SETTLEABLE")
            if isinstance(body.receipt, dict) and body.receipt.get("outcome") == "cancelled" and prior != "waiting_for_model":
                # After dispatch only the provider-quota path (recorded wait, isolated workspace, nothing copied
                # out) may close an attempt without effect. Any other "cancelled" receipt would be a false
                # terminal state hiding a possible effect; the attempt stays executing/uncertain.
                raise ClientControlError("RECEIPT_CANCEL_AFTER_DISPATCH")
            try:
                result = self.control.settle(body.ticket, body.receipt, identity)
            except ExecutionControlError as exc:
                raise ClientControlError(str(exc)) from None
            outcome = result["state"]
            if (outcome == "failed" and record.get("dispatched")
                    and not str(body.receipt.get("failure_category") or "").startswith(NOT_STARTED)):
                # A failure reported after dispatch does not show that nothing happened (a write may have
                # landed before a read-back mismatch; a harness may have acted before failing). Only the
                # client runtime's own pre-launch refusal (nothing effect-capable was started) closes it.
                outcome = "execution_uncertain"
                record["execution_reported"] = "failed"
            if outcome in {"verified", "failed", "cancelled"}:
                record["execution_closed"] = True
                record["execution_outcome"] = outcome
            sessions = (self.pending.get(turn_id) or {}).get("sessions")
            extra = {"session_update": sessions.get(outcome, sessions["other"])} if sessions else {}
            if prior == "waiting_for_model" and outcome == "cancelled":
                # Provider quota: checkpoint preserved, nothing verified, user must choose again.
                return self.service._envelope(record, code="WAITING_FOR_MODEL", execution=result,
                    message="The selected provider is out of quota. Your task is saved; choose another "
                            "provider to continue. Nothing was changed.", **extra)
            record["state"] = {"verified": "reply", "failed": "failed", "cancelled": "cancelled",
                               "execution_uncertain": "execution_uncertain"}[outcome]
            message = {"verified": "Done. The result was independently verified by URI.",
                       "failed": "The action failed; nothing was verified.",
                       "cancelled": "The action was cancelled before any verified effect.",
                       "execution_uncertain": "The outcome is uncertain. URI will not repeat it automatically; "
                                              "check the result before retrying."}[outcome]
            if record.get("execution_reported") == "failed" and outcome == "execution_uncertain":
                message = ("The action reported a failure, but URI cannot confirm that nothing changed. It will not "
                           "repeat it automatically; check the result before retrying.")
            return self.service._envelope(record, code="SETTLED_" + outcome.upper(), message=message, execution=result,
                                          **extra)
        return self.service.act(turn_id, body, identity, step)

    def wait(self, turn_id, body, identity):
        def step(record, live):
            pend = self.pending.get(turn_id)
            if (record["state"] not in {"ticket_issued", "executing"} or pend is None
                    or pend["capability"] not in PROVIDER_EXECUTED):
                # Only a provider-executed task can be paused for quota. Allowing it for a local write would
                # let a "cancelled" quota receipt close an attempt that may already have taken effect.
                raise ClientControlError("TURN_NOT_WAITABLE")
            record.update(state="waiting_for_model", checkpoint_digest=body.checkpoint_digest)
            return self.service._envelope(record, code="WAITING_FOR_MODEL", checkpoint_digest=body.checkpoint_digest)
        return self.service.act(turn_id, body, identity, step)

    def _ledger_revision(self, intent_id):
        try:
            data = self.service._load()
        except Exception:
            return float("inf")   # ledger unreadable: treat saved state as stale (fail closed)
        pruned = (data.get("intents") or {}).get(intent_id) or {}
        return max([t.get("intent_revision") or 0 for t in data["turns"].values() if t.get("intent_id") == intent_id]
                   + [pruned.get("revision") or 0])

    def _intent_verified(self, intent_id):
        try:
            data = self.service._load()
        except Exception:
            return True     # ledger unreadable: fail closed
        return bool(((data.get("intents") or {}).get(intent_id) or {}).get("verified")) or any(
            t.get("intent_id") == intent_id and t.get("execution_outcome") == "verified" for t in data["turns"].values())

    def _intent_possibly_executed(self, intent_id, current_turn):
        """True if any durable turn for this intent was claimed (dispatch authorized) without a
        verified/failed/cancelled settlement. Survives server and client restarts."""
        try:
            turns = self.service._load()["turns"]
        except Exception:
            return True     # ledger unreadable: fail closed
        return any(t.get("intent_id") == intent_id and t["turn_id"] != current_turn
                   and (t.get("state") in {"executing", "execution_uncertain"}
                        or (t.get("dispatched") and not t.get("execution_closed")))
                   for t in turns.values())

    # ---- trusted callbacks -----------------------------------------------------------------------
    def _authorize(self, ticket, identity, phase):
        pend = self.pending.get(ticket.turn_id)
        if (pend is None or not pend["approved"] or pend["denied"] or pend["client_id"] != identity.client_id
                or pend["principal_id"] != identity.principal.user_id):
            return False
        if (ticket.capability_id, ticket.argument_digest, ticket.approval_digest) != (
                pend["capability"], pend["args_digest"], pend["approval_digest"]):
            return False
        if ticket.capability_id not in self.qualified:
            return False
        # Current grants are re-checked at every phase: revocation stops claim.
        try:
            grants = self.service.pairings.grants(identity)
        except Exception:
            return False
        return ticket.capability_id in grants

    def _verify_receipt(self, ticket, receipt):
        if receipt.outcome != "verified":
            return True   # non-success outcomes carry no authority and need no evidence
        pend = self.pending.get(ticket.turn_id)
        return bool(pend and any(
            e.get("check") == pend["check"] and e.get("argument_digest") == ticket.argument_digest
            and e.get("verifier_id") == ticket.verifier_id and e.get("matched") is True for e in receipt.evidence))
