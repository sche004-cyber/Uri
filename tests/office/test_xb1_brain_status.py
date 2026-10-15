"""M2-XB-1 (O2 real-app run r7): the Excel Brain said a request was ambiguous while its ops still changed the draft.

The Brain's answer now carries `status`. Only "propose" may put changes in the draft; "clarify" and "cannot" leave the
draft exactly as it was, whatever ops came with them.
"""
import json
from types import SimpleNamespace

import jsonschema
import pytest
from openpyxl import Workbook

from uri_office import ops as O
from uri_office.brain import OfficeBrain, schema_for
from uri_office.errors import OfficeError
from uri_office.service import Office


class FakeClient:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.bodies = []

    def stream_chat(self, body, *, cancel=None, deadlines=None):
        self.bodies.append(body)
        return SimpleNamespace(status="COMPLETE", text=json.dumps(self.answers.pop(0)), ttft_s=0.1, total_s=0.2,
                               timings={})


def op(**kw):
    base = {k: None for k in O.BRAIN_SCHEMA["properties"]["ops"]["items"]["required"]}
    return {**base, **kw}


def budget(path):
    """The shape of the r7 fixture: a budget with Digitization in row 5."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Budget"
    for r in (("Head", "Amount"), ("Salaries", 400000), ("Office", 50000), ("Training", 30000),
              ("Digitization", 60000)):
        ws.append(list(r))
    wb.save(path)
    return path


# The answer the live Brain gave in r7: a clarifying message and, in the same answer, an op over B5.
AMBIGUOUS = {"message": "Your request is ambiguous: insert a new row below Digitization, or replace its amount?",
             "status": "clarify",
             "ops": [op(op="set_values", sheet="Budget", range="B5", values=[[25000]])]}


@pytest.fixture
def session(tmp_path):
    def make(*answers):
        client = FakeClient(*answers)
        o = Office(tmp_path / "state", allowed_roots=[tmp_path], brain=OfficeBrain(client))
        v = o.open_local(str(budget(tmp_path / "budget.xlsx")))
        return o, v["workbook_id"], client
    return make


def test_clarify_answer_never_changes_the_draft(session):
    o, wid, _ = session(AMBIGUOUS)
    r = o.instruct(wid, {"text": "Add a row for Travel with 25000 below Digitization", "active_sheet": "Budget"})
    assert r["status"] == "clarify"
    assert r["proposed"] == [] and r["refused"] == []
    assert r["draft"]["changes"] == []                                 # B5 is not touched, not even as a proposal
    assert "ambiguous" in r["message"]


def test_cannot_answer_never_changes_the_draft(session):
    o, wid, _ = session({**AMBIGUOUS, "status": "cannot", "message": "Rows cannot be inserted in a local file."})
    r = o.instruct(wid, {"text": "Insert a row above row 3", "active_sheet": "Budget"})
    assert r["status"] == "cannot" and r["draft"]["changes"] == [] and r["proposed"] == []


def test_propose_answer_still_drafts(session):
    o, wid, _ = session({"message": "Added Travel below the table.", "status": "propose",
                         "ops": [op(op="set_values", sheet="Budget", range="A6:B6", values=[["Travel", 25000]])]})
    r = o.instruct(wid, {"text": "Add a row for Travel with 25000 at the end", "active_sheet": "Budget"})
    assert r["status"] == "propose"
    assert sorted(c["cell"] for c in r["draft"]["changes"]) == ["A6", "B6"]
    assert all(c["state"] == "proposed" for c in r["draft"]["changes"])


@pytest.mark.parametrize("status", [None, "maybe", ""])
def test_missing_or_unknown_status_is_refused_without_change(session, status):
    answer = {k: v for k, v in AMBIGUOUS.items() if k != "status"}
    if status is not None:
        answer["status"] = status
    o, wid, _ = session(answer)
    with pytest.raises(OfficeError) as e:
        o.instruct(wid, {"text": "Add a row for Travel", "active_sheet": "Budget"})
    assert e.value.code == "BRAIN_OUTPUT_INVALID"
    assert o.view(wid)["draft"]["changes"] == []


def test_clarify_without_message_gets_a_fixed_question(session):
    o, wid, _ = session({**AMBIGUOUS, "message": "  "})
    r = o.instruct(wid, {"text": "fix it", "active_sheet": "Budget"})
    assert r["message"] == "Please say more precisely what to change; nothing was changed."


def test_check_task_keeps_findings_but_drops_ops_when_not_proposing(tmp_path):
    """The M2 check task: findings are reported; a 'clarify' status still never drafts its ops."""
    brain = OfficeBrain(FakeClient({"message": "Which total is right?", "status": "clarify", "findings": [
        {"sheet": "Budget", "cell": "B5", "issue": "Differs from the reference."}],
        "ops": [op(op="set_values", sheet="Budget", range="B5", values=[[1]])]}))
    sheets = [{"name": "Budget", "max_row": 5, "max_col": 2, "cells": {"B5": {"v": 60000}}}]
    res = brain.plan("check it", sheets=sheets, active="Budget", engine="local", locked={}, history_rows=[],
                     sources=[], task="check")
    assert res["status"] == "clarify" and res["edits"] == []
    assert res["findings"] == [{"sheet": "Budget", "cell": "B5", "issue": "Differs from the reference."}]


@pytest.mark.parametrize("engine,sources,task", [("local", None, "edit"), ("google", None, "edit"),
                                                  ("new", None, "build"), ("local", [], "check")])
def test_every_schema_requires_status_and_the_prompt_explains_it(engine, sources, task):
    schema = schema_for(engine, sources, task)
    jsonschema.Draft202012Validator.check_schema(schema)
    assert "status" in schema["required"]
    assert schema["properties"]["status"]["enum"] == ["propose", "clarify", "cannot"]
    # The explanation comes before the status in the schema's property order (constrained decoding writes in order).
    keys = list(schema["properties"])
    assert keys.index("message") < keys.index("status") < keys.index("ops")


def test_prompt_states_the_status_rule_and_the_overwrite_rule(tmp_path):
    client = FakeClient({"message": "ok", "status": "propose", "ops": []})
    OfficeBrain(client).plan("x", sheets=[{"name": "S", "max_row": 1, "max_col": 1, "cells": {}}], active="S", engine="local", locked={},
                             history_rows=[])
    system = client.bodies[0]["messages"][0]["content"]
    assert "status to 'propose' only when" in system and "'clarify'" in system and "'cannot'" in system
    assert "never write over cells that already hold data unless the owner asked" in system


# ---- NOOP-1 (readiness run r3): restated cells are not changes ------------------------------------------------------
def test_restated_cells_are_not_drafted(session):
    """The shape of the live r3 answer: the whole row is restated while only the amount changes."""
    o, wid, _ = session({"message": "I will update the Digitization row.", "status": "propose",
                         "ops": [op(op="set_values", sheet="Budget", range="A5:B5", values=[["Digitization", 25000]])]})
    r = o.instruct(wid, {"text": "Set Digitization to 25000", "active_sheet": "Budget"})
    assert [c["cell"] for c in r["draft"]["changes"]] == ["B5"]
    assert r["proposed"] and len(r["proposed"]) == 1


def test_unchanged_helper():
    from uri_office.ops import unchanged_edit
    cur = {("S", "A1"): {"v": "Travel"}, ("S", "B1"): {"v": 60000}, ("S", "C1"): {"f": "=B1*2", "v": 120000}}
    assert unchanged_edit({"sheet": "S", "cell": "A1", "value": "Travel"}, cur)
    assert unchanged_edit({"sheet": "S", "cell": "B1", "value": 60000.0}, cur)
    assert not unchanged_edit({"sheet": "S", "cell": "B1", "value": 25000}, cur)
    assert not unchanged_edit({"sheet": "S", "cell": "B1", "value": "60000"}, cur)      # text is not a number
    assert not unchanged_edit({"sheet": "S", "cell": "C1", "value": 120000}, cur)       # value over a formula
    assert unchanged_edit({"sheet": "S", "cell": "C1", "formula": "=B1*2"}, cur)
    assert not unchanged_edit({"sheet": "S", "cell": "D1", "value": "x"}, cur)         # unseen cell
    assert not unchanged_edit({"sheet": "S", "cell": "B1", "value": True}, {("S", "B1"): {"v": 1}})
    big = {("S", "A1"): {"v": 2 ** 53}}                                                     # Codex R7-4
    assert not unchanged_edit({"sheet": "S", "cell": "A1", "value": 2 ** 53 + 1}, big)
    assert not unchanged_edit({"sheet": "S", "cell": "A1", "value": "Travel"},
                              {("S", "A1"): {"v": "Travel", "pending": True}})                   # R7-3


def test_keeping_the_old_value_against_a_pending_proposal_is_drafted(session):
    """Codex R7-3: B5 has a pending proposal 60000 -> 25000; the owner asks to keep 60000: that answer is a change."""
    o, wid, _ = session(
        {"message": "Set to 25000.", "status": "propose",
         "ops": [op(op="set_values", sheet="Budget", range="B5", values=[[25000]])]},
        {"message": "Keep 60000.", "status": "propose",
         "ops": [op(op="set_values", sheet="Budget", range="B5", values=[[60000]])]})
    o.instruct(wid, {"text": "Set Digitization to 25000", "active_sheet": "Budget"})
    r = o.instruct(wid, {"text": "No, keep it at 60000", "active_sheet": "Budget"})
    assert len(r["proposed"]) == 1


def test_a_restatement_does_not_block_a_later_change_of_the_same_cell(session):
    """Codex R8-1: B5 restated as 60000, then set to 25000 in the same answer: the real change is drafted."""
    o, wid, _ = session({"message": "Set B5.", "status": "propose", "ops": [
        op(op="set_values", sheet="Budget", range="B5", values=[[60000]]),
        op(op="set_values", sheet="Budget", range="B5", values=[[25000]])]})
    r = o.instruct(wid, {"text": "Set Digitization to 25000", "active_sheet": "Budget"})
    assert r["refused"] == []
    assert [(c["cell"], c["after"]) for c in r["draft"]["changes"]] == [("B5", {"v": 25000})]


def test_a_later_write_back_to_the_old_value_is_still_an_overlap(session):
    """Codex R9-1: B5 = 25000, then B5 = 60000 (the original) in one answer is a planning slip, refused as before."""
    o, wid, _ = session({"message": "Set B5.", "status": "propose", "ops": [
        op(op="set_values", sheet="Budget", range="B5", values=[[25000]]),
        op(op="set_values", sheet="Budget", range="B5", values=[[60000]])]})
    r = o.instruct(wid, {"text": "Set Digitization to 25000", "active_sheet": "Budget"})
    assert [x["code"] for x in r["refused"]] == ["OVERLAPS_EARLIER_OP"]
    assert [(c["cell"], c["after"]) for c in r["draft"]["changes"]] == [("B5", {"v": 25000})]
