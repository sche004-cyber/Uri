"""INT-ARN-1 Slice B: durable S1 mechanics; every journal lives under tmp_path."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from uri_desktop_seams.reference_clarification.evidence import EvidenceCandidate, EvidenceEnvelope
from uri_desktop_seams.reference_clarification.proposal import ReferenceSlot
from uri_desktop_seams.reference_clarification.service import (
    ApprovalBindingIdentity, BindingPrincipal, ReferenceClarificationService,
    SlotBindingIdentity, revalidate_binding_identity,
)
from uri_desktop_seams.reference_clarification.store import ClarificationJournal
from uri_v1.reference_clarification.authority import AuthorityClass, classify_authority
from uri_v1.reference_clarification.store import BindingRecord
from uri_v1.turn.rar_clarification_contract import (
    BindingState, ClarificationKind, ClarificationResponse, ResponseKind, WrongBindingImpact,
)
from uri_v1.turn.rar_contracts import (
    RARCandidate, RARDeterministicAnchor, RAREvidence, RARQuery,
)
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended

USER = str(uuid4())
OTHER = str(uuid4())
SESSION = "session-a"
SLOT = ReferenceSlot(0, 2, "it", "ref1", "files", "open", "file_id", "direct", "file")


@pytest.fixture
def tmp_path():
    # Windows sandbox access requires normal directory ACLs (tempfile uses 0700).
    path = Path(__file__).parent / "uri_desktop_seams" / "reference_clarification" / ".test_tmp" / uuid4().hex
    path.mkdir(parents=True)
    try:
        yield path
    finally:
        shutil.rmtree(path)


def envelope(expression="it", titles=("Alpha", "Beta"), anchor=None, aliases=(), user=USER):
    candidates = tuple(RARCandidate(f"file:{user}:{i}", title, "document", i,
                                    owner=f"owner-{i}", exact_aliases=aliases if i == 0 else ())
                       for i, title in enumerate(titles))
    inventory = tuple(EvidenceCandidate(item.id, str(i), "file", item.title, "document", str(i),
                                        f"v{i}", datetime.now(timezone.utc).isoformat(), user, SESSION,
                                        owner=item.owner)
                      for i, item in enumerate(candidates))
    query = RARQuery(expression, candidates, RAREvidence(clause_text=expression), anchor)
    return EvidenceEnvelope(SLOT, inventory, query)


def service(tmp_path, **kw):
    return ReferenceClarificationService(journal=ClarificationJournal(root=str(tmp_path)), **kw)


def resolve(svc, env, impact=WrongBindingImpact.CONSEQUENTIAL):
    return svc.resolve(user_id=USER, session_id=SESSION, turn_id="turn-a", envelope=env,
                       wrong_binding_impact=impact,
                       trusted_selected_id=(env.query.deterministic_anchor.selected_ui_id
                                            if env.query.deterministic_anchor else None))


@pytest.mark.parametrize("expression,anchor,aliases,expected", [
    ("file:" + USER + ":0", None, (), "EXACT_ID"),
    ("known alias", None, ("known alias",), "EXACT_ALIAS"),
    ("it", RARDeterministicAnchor(selected_ui_id="file:" + USER + ":0"), (), "ACTIVE_UI"),
    ("attached", RARDeterministicAnchor(current_attachment_id="file:" + USER + ":0"), (), "CURRENT_ATTACHMENT"),
    ("Alpha", RARDeterministicAnchor(unique_title_match="file:" + USER + ":0"), (), "EXACT_TITLE"),
    ("Alpha", None, (), "EXACT_TITLE"),
])
def test_d5_certainty_rules(tmp_path, expression, anchor, aliases, expected):
    env = envelope(expression, anchor=anchor, aliases=aliases)
    if anchor and anchor.current_attachment_id:
        env = replace(env, inventory=(replace(env.inventory[0], is_current_attachment=True), *env.inventory[1:]),
                      query=replace(env.query, candidates=(replace(env.query.candidates[0], is_attachment=True),
                                                           *env.query.candidates[1:])))
    resolution = resolve_rar_deterministic_extended(env.query).resolution
    assert resolution.rule_used.value == expected
    assert classify_authority(resolution, env.query) == AuthorityClass.CERTAINTY
    assert resolve(service(tmp_path), env).state == BindingState.CONFIRMED


@pytest.mark.parametrize("rule", ["ACTIVE_POINTER", "TYPE_FILTER", "CONTRAST_FILTER",
                                   "TEMPORAL_RELATION", "REVISION_RELATION", "TERM_DISCRIMINATION", "NONE"])
def test_d5_noncertainty_rule_table(rule):
    from uri_v1.turn.rar_contracts import RARBasis, RARDriverRule, RAROutcome, RARResolution
    query = envelope().query
    result = RARResolution("it", RAROutcome.RESOLVED, candidate_id=query.candidate_ids[0],
                           basis=RARBasis.DETERMINISTIC_ANCHOR, rule_used=RARDriverRule(rule))
    assert classify_authority(result, query) == AuthorityClass.HEURISTIC


def test_unverified_anchor_cannot_confirm(tmp_path):
    candidate_id = f"file:{USER}:0"
    env = envelope("it", anchor=RARDeterministicAnchor(selected_ui_id=candidate_id))
    result = service(tmp_path).resolve(user_id=USER, session_id=SESSION, turn_id="turn-a",
        envelope=env, wrong_binding_impact=WrongBindingImpact.CONSEQUENTIAL)
    assert result.state == BindingState.REJECTED
    attachment = envelope("attached", anchor=RARDeterministicAnchor(current_attachment_id=candidate_id))
    assert resolve(service(tmp_path), attachment).state == BindingState.REJECTED


@pytest.mark.parametrize("impact,expected", [
    (WrongBindingImpact.NONE, BindingState.TENTATIVE),
    (WrongBindingImpact.RECOVERABLE, BindingState.TENTATIVE),
    (WrongBindingImpact.CONSEQUENTIAL, BindingState.PENDING),
])
def test_heuristic_impact_and_confirm_one(tmp_path, impact, expected):
    env = envelope("attached", titles=("Alpha",))
    # A sole attachment without a trusted current-attachment anchor is heuristic.
    env = replace(env, query=replace(env.query, candidates=(replace(env.query.candidates[0], is_attachment=True),)),
                  inventory=(replace(env.inventory[0], is_current_attachment=True),))
    outcome = resolve(service(tmp_path), env, impact)
    assert outcome.state == expected
    if expected == BindingState.PENDING:
        assert outcome.contract.kind == ClarificationKind.CONFIRM_ONE


def test_restart_round_replay_cross_user_and_stale(tmp_path):
    env = envelope()
    first = resolve(service(tmp_path), env)
    assert first.contract
    fresh = service(tmp_path)
    response = ClarificationResponse(first.contract.ambiguity_id, ResponseKind.CANDIDATE,
        candidate_id=env.query.candidate_ids[0], candidate_set_fingerprint=first.contract.candidate_set_fingerprint)
    other = fresh.respond(user_id=OTHER, session_id=SESSION, response=response,
                          refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert other.state == BindingState.REJECTED
    wrong_session = fresh.respond(user_id=USER, session_id="session-b", response=response,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert wrong_session.state == BindingState.REJECTED
    selected = fresh.respond(user_id=USER, session_id=SESSION, response=response,
                             refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert selected.state == BindingState.CONFIRMED
    assert selected.binding_id == first.contract.ambiguity_id
    replay = fresh.respond(user_id=USER, session_id=SESSION, response=response,
                           refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert replay.state == BindingState.REJECTED
    changed = replace(env, inventory=(replace(env.inventory[0], version="changed"), *env.inventory[1:]))
    assert service(tmp_path).record_execution(user_id=USER, session_id=SESSION,
        binding_id=selected.binding_id, refresh=lambda: changed,
        impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL).state == BindingState.REJECTED
    assert service(tmp_path).record_execution(user_id=USER, session_id=SESSION,
        binding_id=selected.binding_id, refresh=lambda: env,
        impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL).state == BindingState.APPLIED


def test_free_input_full_round_scope_and_no_invention(tmp_path):
    env = envelope("it", titles=tuple("Same" for _ in range(6)))
    first = resolve(service(tmp_path), env)
    assert len(first.contract.scope_candidate_ids) == 6
    assert len(first.contract.candidates) <= 5
    hidden = env.query.candidate_ids[5]
    answer = ClarificationResponse(first.contract.ambiguity_id, ResponseKind.FREE_INPUT, text=hidden)
    bound = service(tmp_path).respond(user_id=USER, session_id=SESSION, response=answer,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert bound.state == BindingState.CONFIRMED and bound.candidate_id == hidden
    second = resolve(service(tmp_path), env)
    absent = service(tmp_path).respond(user_id=USER, session_id=SESSION,
        response=ClarificationResponse(second.contract.ambiguity_id, ResponseKind.FREE_INPUT, text="file:absent:99"),
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert absent.state != BindingState.CONFIRMED


def test_attribute_starts_new_round(tmp_path):
    env = envelope("it", titles=tuple("Same" for _ in range(6)))
    grouped = tuple(replace(item, owner="owner-a" if i < 3 else "owner-b")
                    for i, item in enumerate(env.query.candidates))
    env = replace(env, query=replace(env.query, candidates=grouped),
                  inventory=tuple(replace(item, owner=grouped[i].owner)
                                  for i, item in enumerate(env.inventory)))
    first = resolve(service(tmp_path), env)
    assert first.contract.kind == ClarificationKind.CHOOSE_ATTRIBUTE
    option = first.contract.attribute_options[0]
    next_turn = service(tmp_path).respond(user_id=USER, session_id=SESSION,
        response=ClarificationResponse(first.contract.ambiguity_id, ResponseKind.ATTRIBUTE,
            option_key=option.option_key, candidate_set_fingerprint=first.contract.candidate_set_fingerprint),
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert next_turn.contract and next_turn.contract.ambiguity_id != first.contract.ambiguity_id
    assert next_turn.contract.round_index == 2


def test_progress_budget_stops_repeated_no_progress(tmp_path):
    svc = service(tmp_path, max_no_progress_rounds=0)
    env = envelope()
    first = resolve(svc, env)
    result = svc.respond(user_id=USER, session_id=SESSION,
        response=ClarificationResponse(first.contract.ambiguity_id, ResponseKind.FREE_INPUT, text="it"),
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert result.state == BindingState.REJECTED
    assert "budget" in result.reason


def test_close_round_prevents_later_selection(tmp_path):
    env = envelope()
    first = resolve(service(tmp_path), env)
    assert service(tmp_path).close_round(user_id=USER, session_id=SESSION,
        ambiguity_id=first.contract.ambiguity_id).state == BindingState.EXPIRED
    response = ClarificationResponse(first.contract.ambiguity_id, ResponseKind.CANDIDATE,
        candidate_id=env.query.candidate_ids[0], candidate_set_fingerprint=first.contract.candidate_set_fingerprint)
    assert service(tmp_path).respond(user_id=USER, session_id=SESSION, response=response,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL).state == BindingState.REJECTED


def test_refresh_failure_fails_closed(tmp_path):
    env = envelope()
    first = resolve(service(tmp_path), env)
    response = ClarificationResponse(first.contract.ambiguity_id, ResponseKind.CANDIDATE,
        candidate_id=env.query.candidate_ids[0], candidate_set_fingerprint=first.contract.candidate_set_fingerprint)
    def unavailable():
        raise OSError("offline")
    assert service(tmp_path).respond(user_id=USER, session_id=SESSION, response=response,
        refresh=unavailable, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL).state == BindingState.REJECTED


def test_change_rebind_after_restart(tmp_path):
    env = envelope("attached", titles=("Alpha", "Beta"))
    candidate = replace(env.query.candidates[0], is_attachment=True)
    env = replace(env, query=replace(env.query, candidates=(candidate, env.query.candidates[1])),
                  inventory=(replace(env.inventory[0], is_current_attachment=True), env.inventory[1]))
    tentative = resolve(service(tmp_path), env, WrongBindingImpact.RECOVERABLE)
    assert tentative.state == BindingState.TENTATIVE
    changed = service(tmp_path).open_change(user_id=USER, session_id=SESSION,
        binding_id=tentative.binding_id, turn_id="turn-b", refresh=lambda: env,
        impact_reader=lambda: WrongBindingImpact.RECOVERABLE)
    assert changed.contract and changed.state == BindingState.CHANGE_PENDING
    answer = ClarificationResponse(changed.contract.ambiguity_id, ResponseKind.CANDIDATE,
        candidate_id=env.query.candidate_ids[1],
        candidate_set_fingerprint=changed.contract.candidate_set_fingerprint)
    rebound = service(tmp_path).respond(user_id=USER, session_id=SESSION, response=answer,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.RECOVERABLE)
    assert rebound.state == BindingState.CONFIRMED


def test_expired_and_corrupt_journal_quarantine(tmp_path):
    env = envelope()
    first = resolve(service(tmp_path), env)
    response = ClarificationResponse(first.contract.ambiguity_id, ResponseKind.CANDIDATE,
        candidate_id=env.query.candidate_ids[0], candidate_set_fingerprint=first.contract.candidate_set_fingerprint)
    expired = service(tmp_path).respond(user_id=USER, session_id=SESSION, response=response,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL,
        now=datetime.now(timezone.utc) + timedelta(days=1))
    assert expired.state == BindingState.EXPIRED
    path = ClarificationJournal(root=str(tmp_path)).path(USER, SESSION)
    path.write_text("{bad", encoding="utf-8")
    result = service(tmp_path).respond(user_id=USER, session_id=SESSION, response=response,
        refresh=lambda: env, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL)
    assert result.state == BindingState.REJECTED
    assert list(path.parent.glob(path.name + ".corrupt.*"))


def test_journal_load_prunes_expired_round_and_binding(tmp_path):
    env = envelope()
    pending = resolve(service(tmp_path), env)
    bound = resolve(service(tmp_path), envelope(f"file:{USER}:0"))
    path = ClarificationJournal(root=str(tmp_path)).path(USER, SESSION)
    raw = json.loads(path.read_text(encoding="utf-8"))
    old = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    raw["rounds"][pending.contract.ambiguity_id]["contract"]["expires_at"] = old
    raw["binding_expires"][bound.binding_id] = old
    path.write_text(json.dumps(raw), encoding="utf-8")
    with ClarificationJournal(root=str(tmp_path)).transaction(USER, SESSION) as journal:
        assert pending.contract.ambiguity_id not in journal.store.rounds
        assert bound.binding_id not in journal.store.bindings


def test_serialized_confirmed_revalidated(tmp_path):
    env = envelope(env_id := f"file:{USER}:0", titles=("Alpha",))
    bound = resolve(service(tmp_path), env)
    assert bound.state == BindingState.CONFIRMED
    path = ClarificationJournal(root=str(tmp_path)).path(USER, SESSION)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["bindings"][bound.binding_id]["state"] = "CONFIRMED"
    path.write_text(json.dumps(raw), encoding="utf-8")
    stale = replace(env, inventory=(replace(env.inventory[0], version="v-new"),))
    assert service(tmp_path).record_execution(user_id=USER, session_id=SESSION, binding_id=bound.binding_id,
        refresh=lambda: stale, impact_reader=lambda: WrongBindingImpact.CONSEQUENTIAL).state == BindingState.REJECTED


def test_render_fallback(tmp_path):
    first = service(tmp_path).resolve(user_id=USER, session_id=SESSION, turn_id="turn-a",
        envelope=envelope(), wrong_binding_impact=WrongBindingImpact.CONSEQUENTIAL,
        render_draft={"question": "I selected a secret", "labels": {}})
    assert first.contract and first.render
    assert "selected" not in first.render.question


def test_approval_identity_drift_and_requires_semantics():
    current = envelope("Alpha", titles=("Alpha",)).inventory[0]
    class Action:
        wrong_binding_impact = __import__("uri_core.capabilities.wrong_binding", fromlist=["WrongBindingImpact"]).WrongBindingImpact.RECOVERABLE
        input_schema = {"properties": {"file_id": {"type": "string"}}}
    grant = {"allowed": True}
    source = {"item": current}
    action = {"item": Action()}
    binding = {"item": BindingRecord("round-a", SESSION, current.id, BindingState.CONFIRMED, "fingerprint")}
    principal = BindingPrincipal(USER, SESSION, lambda cls, loc: source["item"],
                                 lambda cap, name: grant["allowed"], lambda cap, name: action["item"],
                                 lambda round_id: binding["item"])
    slot = SlotBindingIdentity("files", "open", "file_id", "ref1", current.id,
        "file", current.locator, current.version, BindingState.CONFIRMED,
        WrongBindingImpact.RECOVERABLE, USER, SESSION, "round-a",
        (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    identity = ApprovalBindingIdentity(1, True, (slot,), (("files", "open", "file_id", "ref1"),))
    assert len(revalidate_binding_identity(principal, identity)) == 1
    assert revalidate_binding_identity(principal, ApprovalBindingIdentity(1, False, ())) == ()
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, ApprovalBindingIdentity(1, True, ()))
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, replace(identity, version=2))
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, replace(identity, action_slots=()))
    for stale in (replace(slot, source_version="old"), replace(slot, user_id=OTHER),
                  replace(slot, expires_at=(datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat())):
        with pytest.raises(ValueError):
            revalidate_binding_identity(principal, replace(identity, slots=(stale,)))
    source["item"] = None
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, identity)
    source["item"] = current
    grant["allowed"] = False
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, identity)
    grant["allowed"] = True
    binding["item"] = replace(binding["item"], superseded_by="round-b")
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, identity)
    binding["item"] = replace(binding["item"], superseded_by=None)
    action["item"] = object()
    with pytest.raises(ValueError):
        revalidate_binding_identity(principal, identity)
