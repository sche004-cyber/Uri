"""INT-ARN-1 state adapter around frozen RAR and S1 binding authority."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable

from uri_core.capabilities.wrong_binding import ReferenceBinding, ReferenceBindingStatus, effective_wrong_binding_impact
from uri_v1.reference_clarification.authority import AuthorityClass, classify_authority, impact_value
from uri_v1.reference_clarification.binding import BindingResult, BindingService
from uri_v1.reference_clarification.builder import build_clarification
from uri_v1.reference_clarification.render_contracts import RenderOutput, make_render_request
from uri_v1.reference_clarification.render_validator import validate_render
from uri_v1.reference_clarification.safeguards import ClarificationSafeguards
from uri_v1.reference_clarification.store import BindingRecord
from uri_v1.reference_clarification.template_renderer import render_template
from uri_v1.turn.rar_clarification_contract import BindingState, ClarificationContract, ClarificationResponse, WrongBindingImpact
from uri_v1.turn.rar_contracts import RARDeterministicAnchor, RAROutcome, validate_rar_resolution
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended

from .evidence import EvidenceCandidate, EvidenceEnvelope
from .store import ClarificationJournal, Journal


@dataclass(frozen=True)
class TurnOutcome:
    state: BindingState
    status: str
    candidate_id: str | None = None
    binding_id: str | None = None
    contract: ClarificationContract | None = None
    render: RenderOutput | None = None
    reason: str | None = None


def _outcome(result: BindingResult, journal: Journal, draft: object = None) -> TurnOutcome:
    contract = journal.store.rounds[result.next_contract_id].contract if result.next_contract_id else None
    rendered = None
    if contract:
        if callable(draft):
            try:
                draft = draft(contract)
            except Exception:
                draft = None
        if validate_render(contract, draft).valid:
            parsed = json.loads(draft) if isinstance(draft, str) else draft
            parsed = (RenderOutput(parsed["question"], tuple(parsed["labels"].items()))
                      if isinstance(parsed, dict) else parsed)
            labels = dict(parsed.labels)
            rendered = RenderOutput(parsed.question,
                tuple((key, labels[key]) for key, _ in make_render_request(contract).slots))
        else:
            rendered = render_template(contract)
    status = (
        "CLARIFICATION_REQUIRED" if contract else
        "BOUND" if result.state in (BindingState.CONFIRMED, BindingState.TENTATIVE) else
        "APPLIED" if result.state in (BindingState.APPLIED, BindingState.TENTATIVE_APPLIED) else
        "CHANGE_ABANDONED" if result.state == BindingState.CHANGE_ABANDONED else
        "RETRY_REQUIRED"
    )
    return TurnOutcome(result.state, status, result.candidate_id, result.binding_id,
                       contract, rendered, result.reason)


def _same_source(saved: EvidenceCandidate, current: EvidenceCandidate, user_id: str, session_id: str) -> bool:
    return (saved.user_id == current.user_id == user_id
            and saved.id == current.id and saved.source_id == current.source_id
            and saved.source_class == current.source_class and saved.locator == current.locator
            and saved.version == current.version
            and saved.session_id == current.session_id
            and (saved.session_id is None or saved.session_id == session_id)
            and (not saved.is_current_attachment or current.is_current_attachment))


def _consistent_envelope(envelope: EvidenceEnvelope) -> bool:
    query = envelope.query
    if len(query.candidates) != len(envelope.inventory):
        return False
    return all(candidate.id == item.id and candidate.title == item.title
               and candidate.candidate_type == item.candidate_type
               and candidate.owner == item.owner
               and candidate.is_attachment == item.is_current_attachment
               for candidate, item in zip(query.candidates, envelope.inventory))


class ReferenceClarificationService:
    def __init__(self, *, journal: ClarificationJournal, max_no_progress_rounds: int = 2,
                 max_turn_cost: int = 5) -> None:
        if max_no_progress_rounds < 0 or max_turn_cost < 1:
            raise ValueError("invalid clarification budget")
        self.journal = journal
        self.max_no_progress_rounds = max_no_progress_rounds
        self.max_turn_cost = max_turn_cost

    def _binding_service(self, journal: Journal) -> BindingService:
        service = BindingService(journal.store, ClarificationSafeguards(
            self.max_no_progress_rounds, self.max_turn_cost))
        service._turn_safeguards = {(journal.session_id, turn): guard for turn, guard in journal.guards.items()}
        return service

    @staticmethod
    def _save_guards(journal: Journal, service: BindingService) -> None:
        journal.guards = {turn: guard for (session, turn), guard in service._turn_safeguards.items()
                          if session == journal.session_id}

    @staticmethod
    def _live(journal: Journal, key: str, envelope: EvidenceEnvelope | None) -> bool:
        if (not isinstance(envelope, EvidenceEnvelope) or envelope.abstained
                or not _consistent_envelope(envelope)):
            return False
        saved = journal.sources.get(key)
        if saved is None:
            return False
        if tuple(item.id for item in saved) != tuple(item.id for item in envelope.inventory):
            return False
        fresh = {item.id: item for item in envelope.inventory}
        return all(item.id in fresh and _same_source(item, fresh[item.id], journal.user_id, journal.session_id)
                   for item in saved)

    @staticmethod
    def _verified_binding(journal: Journal, binding_id: str, current: EvidenceEnvelope) -> bool:
        """A persisted CONFIRMED bit has no authority without fresh source and anchor proof."""
        binding = journal.store.bindings.get(binding_id)
        query = journal.store.binding_queries.get(binding_id)
        if binding is None or query is None or not ReferenceClarificationService._live(journal, binding_id, current):
            return False
        if binding.state not in (BindingState.CONFIRMED, BindingState.APPLIED,
                                 BindingState.TENTATIVE, BindingState.TENTATIVE_APPLIED):
            return False
        candidate = current.query.get_candidate(binding.candidate_id)
        if candidate is None or query.get_candidate(binding.candidate_id) != candidate:
            return False
        origin = journal.origins.get(binding_id)
        if origin in ("RAR_CERTAINTY", "RAR_TENTATIVE"):
            resolution = resolve_rar_deterministic_extended(query).resolution
            if resolution.outcome != RAROutcome.RESOLVED or resolution.candidate_id != binding.candidate_id:
                return False
            if binding.state in (BindingState.CONFIRMED, BindingState.APPLIED):
                return origin == "RAR_CERTAINTY" and classify_authority(resolution, query) == AuthorityClass.CERTAINTY
            return origin == "RAR_TENTATIVE" and journal.impacts.get(binding_id) in ("NONE", "RECOVERABLE")
        round_record = journal.store.rounds.get(binding_id)
        if round_record is None or not round_record.used or round_record.contract.session_id != journal.session_id:
            return False
        contract = round_record.contract
        if binding.candidate_id not in contract.scope_candidate_ids:
            return False
        from uri_v1.reference_clarification.fingerprints import candidate_fingerprint
        if dict(contract.scope_fingerprints).get(binding.candidate_id) != candidate_fingerprint(candidate):
            return False
        if origin == "RESPONSE:CANDIDATE":
            if binding.candidate_id not in {item.candidate_id for item in contract.candidates}:
                return False
            anchor = replace(round_record.query.deterministic_anchor or RARDeterministicAnchor(),
                             selected_ui_id=binding.candidate_id)
            scoped = tuple(current.query.get_candidate(cid) for cid in contract.scope_candidate_ids)
            if any(item is None for item in scoped):
                return False
            check = replace(round_record.query, candidates=scoped, deterministic_anchor=anchor)
        elif origin and origin.startswith("RESPONSE:FREE_INPUT:"):
            scoped = tuple(current.query.get_candidate(cid) for cid in contract.scope_candidate_ids)
            if any(item is None for item in scoped):
                return False
            anchor = round_record.query.deterministic_anchor
            check = replace(round_record.query, reference_expression=origin[len("RESPONSE:FREE_INPUT:"):],
                            candidates=scoped,
                            deterministic_anchor=replace(anchor, selected_ui_id=None) if anchor else None)
        else:
            return False
        resolution = resolve_rar_deterministic_extended(check).resolution
        if resolution.outcome != RAROutcome.RESOLVED or resolution.candidate_id != binding.candidate_id:
            return False
        if binding.state in (BindingState.CONFIRMED, BindingState.APPLIED):
            return classify_authority(resolution, check) == AuthorityClass.CERTAINTY
        return journal.impacts.get(binding_id) in ("NONE", "RECOVERABLE")

    def resolve(self, *, user_id: str, session_id: str, turn_id: str,
                envelope: EvidenceEnvelope, wrong_binding_impact: WrongBindingImpact | str | None,
                render_draft: object = None, trusted_selected_id: str | None = None) -> TurnOutcome:
        if not turn_id or envelope.abstained or any(item.user_id != user_id for item in envelope.inventory):
            return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source evidence unavailable")
        query = envelope.query
        if not _consistent_envelope(envelope):
            return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source scope mismatch")
        anchor = query.deterministic_anchor
        if anchor:
            inventory = {item.id: item for item in envelope.inventory}
            if (anchor.selected_ui_id is not None and anchor.selected_ui_id != trusted_selected_id
                    or anchor.current_attachment_id is not None and
                    (anchor.current_attachment_id not in inventory or
                     not inventory[anchor.current_attachment_id].is_current_attachment)
                    or anchor.unique_title_match is not None and
                    sum(item.title.strip().casefold() == query.reference_expression.strip().casefold()
                        for item in envelope.inventory) != 1
                    or anchor.unique_title_match is not None and
                    (anchor.unique_title_match not in inventory or
                     inventory[anchor.unique_title_match].title.strip().casefold() != query.reference_expression.strip().casefold())):
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="anchor not verified")
        resolution = resolve_rar_deterministic_extended(query).resolution
        validate_rar_resolution(resolution, query.candidates)
        built = build_clarification(query, resolution, session_id=session_id, turn_id=turn_id,
                                    wrong_binding_impact=wrong_binding_impact)
        with self.journal.transaction(user_id, session_id) as journal:
            service = self._binding_service(journal)
            result = service.register(built, query)
            key = result.next_contract_id or result.binding_id
            if key:
                journal.sources[key] = envelope.inventory
                journal.impacts[key] = impact_value(wrong_binding_impact).value
                if result.binding_id:
                    journal.origins[key] = "RAR_CERTAINTY" if result.state == BindingState.CONFIRMED else "RAR_TENTATIVE"
                    journal.binding_expires[key] = (datetime.now(timezone.utc) + timedelta(seconds=900)).isoformat()
            return _outcome(result, journal, render_draft)

    def respond(self, *, user_id: str, session_id: str, response: ClarificationResponse,
                refresh: Callable[[], EvidenceEnvelope], impact_reader: Callable[[], WrongBindingImpact | str | None],
                render_draft: object = None, now: datetime | None = None) -> TurnOutcome:
        with self.journal.transaction(user_id, session_id) as journal:
            record = journal.store.rounds.get(response.ambiguity_id)
            if record is None or record.contract.session_id != session_id:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="round unavailable")
            try:
                current, impact = refresh(), impact_reader()
            except Exception:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source refresh unavailable")
            if not self._live(journal, response.ambiguity_id, current):
                record.state = BindingState.REJECTED
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source changed")
            if impact_value(impact).value != journal.impacts.get(response.ambiguity_id):
                record.state = BindingState.REJECTED
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="action impact changed")
            service = self._binding_service(journal)
            result = service.respond(session_id, response, current.query,
                                     wrong_binding_impact=impact,
                                     current_candidate_locators={item.id: item.locator for item in current.inventory},
                                     now=now)
            self._save_guards(journal, service)
            if result.next_contract_id:
                journal.sources[result.next_contract_id] = current.inventory
                journal.impacts[result.next_contract_id] = impact_value(impact).value
            if result.state in (BindingState.CONFIRMED, BindingState.TENTATIVE) and result.candidate_id:
                key = result.binding_id or response.ambiguity_id
                journal.sources[key] = current.inventory
                journal.impacts[key] = impact_value(impact).value
                journal.origins[key] = ("RESPONSE:FREE_INPUT:" + response.text if response.text is not None
                                        else "RESPONSE:" + response.response_kind.value)
                journal.binding_expires[key] = record.contract.expires_at
                if result.binding_id is None:
                    result = replace(result, binding_id=key)
            return _outcome(result, journal, render_draft)

    def close_round(self, *, user_id: str, session_id: str, ambiguity_id: str) -> TurnOutcome:
        """Close a pending round when the user changes topic; no goal is replayed."""
        with self.journal.transaction(user_id, session_id) as journal:
            record = journal.store.rounds.get(ambiguity_id)
            if record is None or record.contract.session_id != session_id:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="round unavailable")
            try:
                state = self._binding_service(journal).close_round(ambiguity_id, session_id=session_id)
            except ValueError:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="round already closed")
            return TurnOutcome(state, "CHANGE_ABANDONED" if state == BindingState.CHANGE_ABANDONED
                               else "RETRY_REQUIRED")

    def open_change(self, *, user_id: str, session_id: str, binding_id: str, turn_id: str,
                    refresh: Callable[[], EvidenceEnvelope], impact_reader: Callable[[], WrongBindingImpact | str | None],
                    render_draft: object = None) -> TurnOutcome:
        with self.journal.transaction(user_id, session_id) as journal:
            prior = journal.store.bindings.get(binding_id)
            if prior is None or prior.session_id != session_id:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="binding unavailable")
            try:
                current, impact = refresh(), impact_reader()
            except Exception:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source refresh unavailable")
            if not self._verified_binding(journal, binding_id, current) or impact_value(impact).value != journal.impacts.get(binding_id):
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source or impact changed")
            service = self._binding_service(journal)
            resolution = resolve_rar_deterministic_extended(current.query).resolution
            result = service.open_change(binding_id, current.query, resolution,
                                         impact_reader=lambda: impact, turn_id=turn_id)
            if result.next_contract_id:
                journal.sources[result.next_contract_id] = current.inventory
                journal.impacts[result.next_contract_id] = impact_value(impact).value
            return _outcome(result, journal, render_draft)

    def record_execution(self, *, user_id: str, session_id: str, binding_id: str,
                         refresh: Callable[[], EvidenceEnvelope], impact_reader: Callable[[], WrongBindingImpact | str | None],
                         applied_result_exists: bool = True) -> TurnOutcome:
        with self.journal.transaction(user_id, session_id) as journal:
            binding = journal.store.bindings.get(binding_id)
            try:
                current, impact = refresh(), impact_reader()
            except Exception:
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="source refresh unavailable")
            if binding is None or binding.session_id != session_id or not self._verified_binding(journal, binding_id, current):
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="binding unavailable or source changed")
            if impact_value(impact).value != journal.impacts.get(binding_id):
                return TurnOutcome(BindingState.REJECTED, "RETRY_REQUIRED", reason="action impact changed")
            state = self._binding_service(journal).record_execution(binding_id, applied_result_exists=applied_result_exists)
            return TurnOutcome(state, "APPLIED", binding.candidate_id, binding_id)


@dataclass(frozen=True)
class SlotBindingIdentity:
    capability_id: str
    action_name: str
    argument_name: str
    ref_key: str
    candidate_id: str
    source_class: str
    locator: str
    source_version: str
    state: BindingState
    wrong_binding_impact: WrongBindingImpact
    user_id: str
    session_id: str
    round_id: str
    expires_at: str


@dataclass(frozen=True)
class ApprovalBindingIdentity:
    version: int
    requires_reference_binding: bool
    slots: tuple[SlotBindingIdentity, ...]
    action_slots: tuple[tuple[str, str, str, str], ...] = ()


@dataclass(frozen=True)
class BindingPrincipal:
    user_id: str
    session_id: str
    read_source: Callable[[str, str], EvidenceCandidate | None]
    has_grant: Callable[[str, str], bool]
    get_action: Callable[[str, str], object | None]
    read_binding: Callable[[str], BindingRecord | None]


def revalidate_binding_identity(principal: BindingPrincipal, identity: ApprovalBindingIdentity) -> tuple[ReferenceBinding, ...]:
    """Recheck approval metadata under the authenticated principal before consume.

    Raises ValueError on drift; a caller must leave the proposal unconsumed.
    """
    if (type(identity) is not ApprovalBindingIdentity or type(identity.version) is not int or identity.version != 1
            or type(identity.requires_reference_binding) is not bool
            or type(identity.slots) is not tuple or type(identity.action_slots) is not tuple
            or (identity.requires_reference_binding != bool(identity.slots))
            or identity.action_slots != tuple((slot.capability_id, slot.action_name,
                                               slot.argument_name, slot.ref_key)
                                              for slot in identity.slots if type(slot) is SlotBindingIdentity)):
        raise ValueError("binding identity missing or malformed")
    seen: set[tuple[str, str, str, str]] = set()
    renewed = []
    for slot in identity.slots:
        if (type(slot) is not SlotBindingIdentity or type(slot.state) is not BindingState
                or type(slot.wrong_binding_impact) is not WrongBindingImpact
                or any(type(value) is not str or not value for value in (
                slot.capability_id, slot.action_name, slot.argument_name, slot.ref_key,
                slot.candidate_id, slot.source_class, slot.locator, slot.source_version,
                slot.user_id, slot.session_id, slot.round_id, slot.expires_at))):
            raise ValueError("slot identity malformed")
        key = (slot.capability_id, slot.action_name, slot.argument_name, slot.ref_key)
        if key in seen or slot.user_id != principal.user_id or slot.session_id != principal.session_id:
            raise ValueError("slot scope mismatch")
        seen.add(key)
        expiry = datetime.fromisoformat(slot.expires_at)
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError("binding expired")
        try:
            action = principal.get_action(slot.capability_id, slot.action_name)
            granted = principal.has_grant(slot.capability_id, slot.action_name)
        except Exception as exc:
            raise ValueError("action authority unavailable") from exc
        if action is None or not granted:
            raise ValueError("action unavailable or grant revoked")
        arguments = getattr(action, "input_schema", None)
        if isinstance(arguments, dict) and slot.argument_name not in arguments.get("properties", {}):
            raise ValueError("action slot changed")
        declared_parameters = getattr(getattr(action, "parameters", None), "parameters", None)
        if isinstance(declared_parameters, dict) and slot.argument_name not in declared_parameters:
            raise ValueError("action slot changed")
        impact, declared = effective_wrong_binding_impact(action)
        if not declared or impact != slot.wrong_binding_impact:
            raise ValueError("action impact changed")
        try:
            current = principal.read_source(slot.source_class, slot.locator)
        except Exception as exc:
            raise ValueError("source unavailable") from exc
        if (current is None or current.user_id != principal.user_id or current.id != slot.candidate_id
                or current.source_class != slot.source_class or current.locator != slot.locator
                or current.version != slot.source_version
                or (current.session_id is not None and current.session_id != principal.session_id)):
            raise ValueError("source identity changed")
        if slot.state not in (BindingState.CONFIRMED, BindingState.TENTATIVE):
            raise ValueError("binding state invalid")
        try:
            binding = principal.read_binding(slot.round_id)
        except Exception as exc:
            raise ValueError("binding unavailable") from exc
        if (type(binding) is not BindingRecord or binding.ambiguity_id != slot.round_id
                or binding.session_id != principal.session_id or binding.candidate_id != slot.candidate_id
                or binding.state != slot.state or binding.superseded_by is not None):
            raise ValueError("binding changed")
        if slot.state == BindingState.TENTATIVE and impact not in (WrongBindingImpact.NONE, WrongBindingImpact.RECOVERABLE):
            raise ValueError("tentative binding is consequential")
        renewed.append(ReferenceBinding(slot.ref_key, slot.candidate_id,
            ReferenceBindingStatus.CONFIRMED if slot.state == BindingState.CONFIRMED else ReferenceBindingStatus.TENTATIVE))
    return tuple(renewed)
