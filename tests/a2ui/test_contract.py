"""A2UI contract: the shared fixture cases, surface digests and the authority-side action gate (A-AC1..A-AC3)."""
import json
from pathlib import Path

import pytest

from uri_a2ui import validate as V
from uri_a2ui.surface import ActionRefused, Surface, check_action
from uri_a2ui.validate import A2uiInvalid

CASES = json.loads((Path(__file__).parent / "fixtures" / "contract_cases.json").read_text(encoding="utf-8"))
SHA = "a" * 64


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_shared_contract_cases(case):
    errs = []
    for m in case["messages"]:
        errs += V.validate_message(m)
    assert (errs[0]["code"] if errs else "valid") == case["expect"]


def proposal_surface(rev=1):
    comps = [
        {"id": "root", "component": "Column", "children": ["sel", "confirm", "revise"]},
        {"id": "sel", "component": "ChoicePicker", "label": "F", "multiple": True, "value": {"path": "/draft/selection"},
         "options": [{"label": "Diwali", "value": "diwali"}, {"label": "Holi", "value": "holi"}]},
        {"id": "confirm", "component": "Button", "label": "Confirm", "action": {"event": {
            "name": "scheduler.confirm_proposal",
            "context": {"proposal_sha256": {"path": "/bound/proposal_sha256"}, "selection": {"path": "/draft/selection"},
                        "time": {"path": "/draft/time"}, "offset_days": {"path": "/draft/offset"}}}}},
        {"id": "revise", "component": "Button", "label": "Revise", "action": {"event": {
            "name": "scheduler.review_artifact", "context": {"artifact_sha256": {"path": "/bound/proposal_sha256"},
                                                             "decision": "approve"}}}},
    ]
    return Surface("sched-1", "schedule_proposal", comps, data={"draft": {"selection": ["diwali"], "time": "09:00", "offset": "2"}},
                   bound={"proposal_sha256": SHA}, actions=("scheduler.confirm_proposal", "scheduler.review_artifact"),
                   revision=rev)


def act(s, comp="confirm", name="scheduler.confirm_proposal", **ctx):
    base = {"surface_digest": s.digest, "proposal_sha256": SHA, "selection": ["diwali"], "time": "09:00", "offset_days": "2"}
    base.update(ctx)
    return {"name": name, "surfaceId": s.surface_id, "sourceComponentId": comp, "timestamp": "2026-10-09T10:00:00Z",
            "context": {k: v for k, v in base.items() if v is not None}}


def test_surface_messages_validate_and_digest_is_delivered():
    s = proposal_surface()
    msgs = s.messages()
    assert V.require_valid(msgs) and msgs[2]["updateDataModel"]["value"]["bound"]["surface"]["digest"] == s.digest
    assert proposal_surface(rev=2).digest != s.digest                       # every revision is a different version


def test_surface_refuses_action_names_it_did_not_declare():
    s = proposal_surface()
    comps = s.components + []
    with pytest.raises(A2uiInvalid):
        Surface("x", "k", comps, actions=("scheduler.confirm_proposal",))  # Button 'revise' names an undeclared action


def test_check_action_accepts_exact_button_and_bound_values():
    s = proposal_surface()
    ctx = check_action(s, act(s))
    assert ctx == {"proposal_sha256": SHA, "selection": ["diwali"], "time": "09:00", "offset_days": "2"}


@pytest.mark.parametrize("mutation,code", [
    (dict(surface_digest="0" * 64), "STALE_SURFACE"),
    (dict(proposal_sha256="b" * 64), "BOUND_VALUE_MISMATCH"),
    (dict(time="25:00"), "BAD_CONTEXT_VALUE"),
    (dict(selection=["../etc"]), "BAD_CONTEXT_VALUE"),
    (dict(offset_days="30"), "BAD_CONTEXT_VALUE"),
    (dict(extra="x"), "UNDECLARED_CONTEXT"),
    (dict(proposal_sha256=None), "BOUND_VALUE_MISMATCH"),
])
def test_check_action_refusals(mutation, code):
    s = proposal_surface()
    with pytest.raises(ActionRefused) as e:
        check_action(s, act(s, **mutation))
    assert e.value.code == code


def test_check_action_refuses_forged_component_and_name():
    s = proposal_surface()
    with pytest.raises(ActionRefused) as e:
        check_action(s, act(s, comp="sel"))
    assert e.value.code == "NOT_FROM_THIS_BUTTON"
    with pytest.raises(ActionRefused) as e:
        check_action(s, act(s, comp="revise"))                              # right button, wrong name
    assert e.value.code == "NOT_FROM_THIS_BUTTON"
    with pytest.raises(ActionRefused) as e:
        check_action(s, act(s, name="calendar.correct_record"))
    assert e.value.code == "ACTION_NOT_ALLOWED_ON_SURFACE"
    m = act(s)
    m["surfaceId"] = "other"
    with pytest.raises(ActionRefused) as e:
        check_action(s, m)
    assert e.value.code == "SURFACE_MISMATCH"


def test_check_action_refuses_changed_literal():
    s = proposal_surface()
    m = {"name": "scheduler.review_artifact", "surfaceId": s.surface_id, "sourceComponentId": "revise",
         "context": {"surface_digest": s.digest, "artifact_sha256": SHA, "decision": "reject"}}
    with pytest.raises(ActionRefused) as e:
        check_action(s, m)
    assert e.value.code == "LITERAL_CHANGED"
    m["context"]["decision"] = "approve"
    assert check_action(s, m)["decision"] == "approve"


def test_record_roundtrip_keeps_digest():
    s = proposal_surface(rev=3)
    assert Surface.from_record(json.loads(json.dumps(s.to_record()))).digest == s.digest


def test_fuzzed_definitions_never_crash_the_validator():
    """Random structural mutations of valid messages: the validator returns codes, it never raises."""
    import random
    rnd = random.Random(20261009)
    junk = [None, True, 0, -1, 10 ** 12, 1.5, "", "x" * 5000, [], {}, ["a"], {"path": "/x"}, {"path": 5}, [[1]], {"a": {"b": []}},
            "javascript:x", {"event": {"name": ["x"]}}, {"componentId": [1], "path": "/a"}]
    base = [c["messages"] for c in CASES if c["expect"] == "valid"]
    s = proposal_surface()
    base.append(s.messages())
    n = 0
    for _ in range(3000):
        msgs = json.loads(json.dumps(rnd.choice(base)))
        m = rnd.choice(msgs)
        node, path = m, []
        for _ in range(rnd.randint(1, 6)):
            if isinstance(node, dict) and node:
                k = rnd.choice(list(node))
            elif isinstance(node, list) and node:
                k = rnd.randrange(len(node))
            else:
                break
            path.append((node, k))
            node = node[k]
        if path:
            parent, k = path[-1]
            parent[k] = rnd.choice(junk)
        for mm in msgs:
            V.validate_message(mm)                       # must not raise
        n += 1
        try:
            check_action(s, {"name": rnd.choice(junk + ["scheduler.confirm_proposal"]), "surfaceId": s.surface_id,
                             "sourceComponentId": rnd.choice(junk + ["confirm"]),
                             "context": rnd.choice([{"surface_digest": s.digest}, junk[-1], {}])})
        except ActionRefused:
            pass
    assert n == 3000
