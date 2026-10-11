"""Regressions for review R9 of 3dd9cde (findings R9-01, R9-03, R9-04). Each fails without its repair.

R9-01  Text selected inside a field (OTP, CVV, e-mail, textarea, contenteditable) never becomes the snapshot's
       selection in real Chromium, and Python accepts a selection only when the adapter built it from page text and it
       contains no withheld value. The Brain request never carries such a value as "Selected text".
R9-03  The adapter's `has_value` (and its withholding) survive normalise(): a filled required withheld field is not
       REQUIRED_EMPTY, and a visible withheld field with a value but no rectangle still refuses a screenshot.
R9-04  A Brain answer is not returned after Stop, pause or a new grant.
"""
import json
import os
import shutil
import subprocess

import pytest

from uri_assist import bridge as B
from uri_assist import checks as CK
from uri_assist import perception as PE

from .test_a0_access_perception import (FakeClient, ask_and_wait, dom_snapshot, drawn_probe, grant, mk, on_screen, png,
                                       stamp)
from .test_a0_r1_review_regressions import FIX, ROOT, _chromium

FIELD_VALUES = ("482913", "417", "ashaR", "mailbox", "12 Lake Road", "Gatecode7781")


def _selection_runs():
    node = shutil.which("node")
    if node is None:
        pytest.skip("BLOCKED: node not installed")
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(FIX / "run_selection.cjs"), str(ROOT / "uri_assist/browser_extension/snapshot.js"),
                        str(FIX / "selection_page.html")], capture_output=True, text=True, env=env, timeout=120)
    if p.returncode != 0 and "Cannot find module" in p.stderr:
        pytest.skip("BLOCKED: playwright not installed")
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


# ---- R9-01 ------------------------------------------------------------------------------------------------------------

def test_r9_01_selection_inside_a_field_never_leaves_the_page():
    runs = _selection_runs()
    for name in ("dblclick_otp", "dblclick_cvv", "dblclick_email", "select_cvv_then_blur", "textarea_select",
                 "contenteditable_select"):
        s = runs[name]
        assert s["selection"] == "" and s["selection_withheld"] is True, (name, s["selection"])
        for v in FIELD_VALUES:
            assert v not in json.dumps(s), (name, v)
    # A drag across the form keeps the page text and labels, never a value.
    drag = runs["drag_across_form"]
    assert drag["selection"].startswith("Enter the code we sent") and "Your bank will never ask" in drag["selection"]
    assert drag["selection_withheld"] is True
    for v in FIELD_VALUES:
        assert v not in drag["selection"], v
    # Ordinary page text is still shared, marked as page text.
    assert runs["page_text"]["selection"] == "Enter the code we sent to your phone."
    assert runs["page_text"]["selection_source"] == "page_text" and runs["page_text"]["selection_withheld"] is False


def test_r9_01_real_snapshot_to_brain_body_has_no_field_value():
    s = _selection_runs()["dblclick_cvv"]
    client = FakeClient(text="It asks for a code.")
    br, _ = mk(snap=s, client=client)
    grant(br, perms=("observe",))
    assert ask_and_wait(br, "What did I select?")["status"] == "COMPLETE"
    body = json.dumps(client.bodies)
    assert "Selected text" not in body and "417" not in body and "selected text inside a form field" in body


@pytest.mark.parametrize("snap_over", [
    # An adapter that does not say the selection is page text (e.g. String(getSelection()) inside an input).
    {"selection": "417"},
    # Marked as page text but containing a value this layer withheld.
    {"selection": "my code 417", "selection_source": "page_text"},
])
def test_r9_01_python_layer_refuses_a_selection_that_is_not_page_text(snap_over):
    fields = [{"id": "cvv", "type": "text", "name": "cvv", "autocomplete": "cc-csc", "label": "Security code (CVV)",
               "value": "417", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}]
    obs = PE.normalise(dom_snapshot(fields=fields, **snap_over), stamp())
    assert obs.selection == "" and obs.selection_withheld is True
    client = FakeClient(text="ok")
    br, _ = mk(snap=dom_snapshot(fields=fields, **snap_over), client=client)
    grant(br, perms=("observe",))
    ask_and_wait(br, "What did I select?")
    body = json.dumps(client.bodies)
    assert "Selected text: " not in body and "417" not in body


def test_r9_01_page_text_selection_is_still_shared():
    # D10: shared only when drawn on screen (pieces with rectangles checked against a screenshot).
    snap = on_screen(dom_snapshot(selection="Fee payment due", selection_source="page_text"))
    obs = PE.normalise(snap, stamp(), probe=drawn_probe(snap))
    assert obs.selection == "Fee payment due" and obs.selection_withheld is False


# ---- R9-03 ------------------------------------------------------------------------------------------------------------

REQ_PAGE = ('<!doctype html><html><body><form><label for="roll">Roll number</label>'
            '<input id="roll" name="roll" required value="2026-CS-118"></form></body></html>')


def test_r9_03_real_snapshot_keeps_has_value_through_normalise(tmp_path):
    page = tmp_path / "req.html"
    page.write_text(REQ_PAGE)
    s = _chromium(str(page))["snapshot"]
    f = s["fields"][0]
    assert f["withheld"] == "not_shared" and f["value"] == "" and f["has_value"] is True
    obs = PE.normalise(s, stamp())
    assert obs.fields[0]["has_value"] is True
    assert not [x for x in CK.findings(obs) if x["code"] == "REQUIRED_EMPTY"]
    # The same field with no usable rectangle cannot be blacked out: a screenshot is refused.
    no_rect = {**s, "fields": [{k: v for k, v in f.items() if k != "rect"}], "sensitive_rects": []}
    assert PE.normalise(no_rect, stamp()).unlocated_sensitive is True
    bad_rect = {**s, "fields": [{**f, "rect": {"x": "a"}}], "sensitive_rects": []}
    assert PE.normalise(bad_rect, stamp()).unlocated_sensitive is True


def test_r9_03_screenshot_ask_refused_for_unlocated_filled_withheld_field():
    fields = [{"id": "roll", "type": "text", "name": "roll", "label": "Roll number", "value": "", "has_value": True,
               "withheld": "not_shared", "sensitive": True, "visible": True}]
    client = FakeClient()
    br, _ = mk(snap=dom_snapshot(fields=fields), png_bytes=png(), client=client, qualified=True)
    grant(br, perms=("observe",))
    with pytest.raises(B.Refused) as e:
        br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": True})
    assert e.value.code == "SENSITIVE_FIELDS_UNLOCATED"
    assert client.bodies == []


def test_r9_03_adapter_withholding_is_kept_and_empty_stays_empty():
    # The page withheld a short code under a "comments" name (its value rule cannot fire here, the value is empty).
    fields = [{"id": "c", "type": "text", "name": "comments", "label": "Enter code", "value": "", "has_value": True,
               "withheld": "sensitive", "sensitive": True, "required": True, "rect": {"x": 1, "y": 1, "w": 2, "h": 2}},
              {"id": "e", "type": "text", "name": "roll", "label": "Roll", "value": "", "has_value": False,
               "withheld": "not_shared", "sensitive": True, "required": True, "rect": {"x": 5, "y": 5, "w": 2, "h": 2}}]
    obs = PE.normalise(dom_snapshot(fields=fields), stamp())
    assert obs.fields[0]["sensitive"] is True and obs.fields[0]["has_value"] is True and "value" not in obs.fields[0]
    assert {"x": 1, "y": 1, "w": 2, "h": 2} in obs.sensitive_rects
    assert [x["field"] for x in CK.findings(obs) if x["code"] == "REQUIRED_EMPTY"] == ["Roll"]


# ---- R9-04 ------------------------------------------------------------------------------------------------------------

def _assert_blank(res, aid):
    assert res["state"] == "FINISHED" and res["ask_id"] == aid and res["status"] == "CANCELLED"
    assert res["answer"] == "" and res["observation"] is None
    assert "SECRET" not in json.dumps(res) and "Fee payment" not in json.dumps(res)


@pytest.mark.parametrize("step", ["revoke", "pause", "regrant", "pause_resume"])
def test_r9_04_answers_do_not_survive_stop_pause_or_a_new_grant(step):
    client = FakeClient(text="SECRET-DERIVED ANSWER about the page")
    br, _ = mk(client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "What is this?")
    assert out["status"] == "COMPLETE" and out["answer"].startswith("SECRET")
    aid = out["ask_id"]
    if step == "revoke":
        br.handle("assist_revoke", {"command": "assist_revoke"})
    elif step == "pause":
        br.handle("assist_pause", {"command": "assist_pause"})
    elif step == "regrant":
        br.handle("assist_revoke", {"command": "assist_revoke"})
        grant(br, perms=("observe",))
    else:
        br.handle("assist_pause", {"command": "assist_pause"})
        br.handle("assist_resume", {"command": "assist_resume"})
    _assert_blank(br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": aid}), aid)
    assert "SECRET" not in json.dumps(br._answers, default=str)        # not kept in memory either


def test_r9_04_answer_is_blank_once_the_grant_ends_by_any_path():
    client = FakeClient(text="SECRET-DERIVED ANSWER")
    br, _ = mk(client=client)
    grant(br, perms=("observe",))
    out = ask_and_wait(br, "q")
    assert out["answer"].startswith("SECRET")
    br.access.revoke("expired")         # the grant ends without a bridge command (expiry, target lost)
    _assert_blank(br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": out["ask_id"]}),
                  out["ask_id"])
    grant(br, perms=("observe",))       # a new grant does not bring it back
    _assert_blank(br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": out["ask_id"]}),
                  out["ask_id"])
    out2 = ask_and_wait(br, "q")        # an answer under the current grant is still returned
    assert out2["status"] == "COMPLETE" and out2["answer"].startswith("SECRET")
