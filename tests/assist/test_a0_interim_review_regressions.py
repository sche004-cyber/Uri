"""Regressions for the interim review of 74b24eb (docs/assist/INTERIM_REVIEW.md). Each fails without its repair."""
import json
import os
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from uri_assist import access as AC
from uri_assist import bridge as B
from uri_assist import perception as PE
from uri_assist import redact as RD

from .test_a0_access_perception import FakeAdapter, FakeClient, dom_snapshot, grant, mk, png

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
SECRETS = ("123456", "654321", "9876", "246810", "135790", "Tr0ub4dor&3", "737", "4111.1111.1111.1111",
           "4111 1111 1111 1111", "eyJhbGciOiJIUzI1NiJ9", "abcdef123456", "tvly-ABCDEFGH12345678",
           "9f86d081884c7d659a2feaa0c55ad015", "2345 6789 0123", "tok_abcdefabcdef")


# ---- F4: Assist Brain work never blocks the command thread; Stop and a user turn cancel it ---------------------------

def _slow_bridge():
    gate = threading.Event()
    client = FakeClient(gate=gate)
    br, _ = mk(client=client)
    grant(br, perms=("observe",))
    return br, client, gate


def test_f4_ask_returns_at_once_and_revoke_cancels_and_discards():
    br, client, gate = _slow_bridge()
    out = br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": False})
    assert "ask_id" in out and br.asking                   # the command returned while the Brain is still working
    st = br.handle("assist_revoke", {"command": "assist_revoke"})   # immediate, not queued behind the answer
    assert st["state"] == "OFF"
    br.wait(5)
    res = br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": out["ask_id"]})
    assert res["status"] == "CANCELLED" and res["answer"] == "" and client.cancelled is True
    gate.set()


def test_f4_user_turn_cancels_assist_work():
    br, client, gate = _slow_bridge()
    aid = br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": False})["ask_id"]
    br.cancel_brain_work("user_turn")                      # what the worker does before an oi_turn
    br.wait(5)
    res = br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": aid})
    assert res["status"] == "CANCELLED" and res["cancel_reason"] == "user_turn"
    gate.set()


def test_f4_answer_discarded_if_grant_changed_during_generation():
    gate = threading.Event()
    client = FakeClient(gate=gate)
    br, _ = mk(client=client)
    grant(br, perms=("observe",))
    aid = br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": False})["ask_id"]
    br.access.pause()                                      # bypassing the bridge: the job itself must notice
    gate.set()
    br.wait(5)
    res = br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": aid})
    assert res["status"] == "CANCELLED" and res["answer"] == ""


def test_f4_deferred_ask_emits_nothing_before_release_and_one_at_a_time():
    events, gate = [], threading.Event()
    ad = FakeAdapter("browser_tab", dom_snapshot(), targets=[{"target_id": "t", "label": "x"}])
    br = B.AssistCommands(adapters={AC.ScopeKind.BROWSER_TAB: ad}, brain_client=FakeClient(gate=gate),
                          write_event=events.append, defer_start=True)
    grant(br, perms=("observe",))
    aid = br.handle("assist_ask", {"command": "assist_ask", "question": "q", "use_screenshot": False})["ask_id"]
    with pytest.raises(B.Refused) as e:
        br.handle("assist_ask", {"command": "assist_ask", "question": "q2", "use_screenshot": False})
    assert e.value.code == "ASK_IN_PROGRESS"
    br.wait(0.2)
    assert events == [] and br.handle("assist_ask_status", {"command": "assist_ask_status", "ask_id": aid})["state"] == "RUNNING"
    br.release()
    gate.set()
    br.wait(5)
    assert events[-1]["type"] == "assist.answer" and events[-1]["turn_id"] == aid


# ---- F5: one-time codes, PINs and card formats --------------------------------------------------------------------

@pytest.mark.parametrize("field", [
    {"name": "totp"}, {"name": "smsOtp"}, {"name": "userPin"}, {"name": "verification_code"}, {"name": "mfa_code"},
    {"label": "Verification code"}, {"label": "2FA code"}, {"name": "pw"}, {"name": "cvn"}, {"name": "cardnumber"},
    {"label": "Code", "value": "482913"},
])
def test_f5_sensitive_names(field):
    assert RD.field_is_sensitive(field)


@pytest.mark.parametrize("field", [{"name": "hotpot"}, {"name": "spinner"}, {"name": "pinnacle"}, {"name": "pincode"},
                                   {"label": "PIN code", "value": "411001"}, {"name": "author"}, {"name": "passenger"}])
def test_f5_ordinary_names_are_not_over_redacted(field):
    assert not RD.field_is_sensitive(field)


def test_f5_card_separators():
    from collections import Counter
    c = Counter()
    out = RD.redact_text("a 4111.1111.1111.1111 b 4111 1111 1111 1111", c)
    assert "4111" not in out and c["card"] == 2


def _chromium(page):
    node = shutil.which("node")
    if node is None:
        pytest.skip("BLOCKED: node not installed")
    env = dict(os.environ, NODE_PATH=os.environ.get("NODE_PATH", "/opt/node22/lib/node_modules"))
    p = subprocess.run([node, str(FIX / "run_snapshot.cjs"), str(ROOT / "uri_assist/browser_extension/snapshot.js"),
                        str(FIX / page)], capture_output=True, text=True, env=env, timeout=120)
    if p.returncode != 0 and "Cannot find module" in p.stderr:
        pytest.skip("BLOCKED: playwright not installed")
    assert p.returncode == 0, p.stderr[-500:]
    return json.loads(p.stdout)


def test_f5_in_page_layer_matches_python_on_hostile_fields():
    s = _chromium("tricky_fields.html")["snapshot"]
    raw = json.dumps(s)
    for secret in SECRETS:
        assert secret not in raw, secret                    # nothing left the page
    js_sensitive = {f["id"] or f["name"] for f in s["fields"] if f["sensitive"]}
    py = PE.normalise({**s}, AC.Stamp("g", 1, "t", "dom", 0.0))
    py_sensitive = {f.get("id") or f.get("name") for f in py.fields if f.get("sensitive")}
    assert js_sensitive == py_sensitive                     # the two layers agree
    assert {"a", "b", "c", "d", "e", "f", "g", "h"} <= js_sensitive
    assert "k" not in js_sensitive and "l" not in js_sensitive          # postal PIN code and spinner stay readable
    assert {"i", "j"} <= {f["id"] for f in s["fields"]}    # contenteditable="" and plaintext-only are fields


# ---- LOW: hidden inputs do not block screenshots; adapters must bind the target -------------------------------------

def test_low_hidden_inputs_are_not_unlocated_but_visible_ones_are():
    snap = dom_snapshot(fields=[{"type": "hidden", "name": "csrf", "value": "tok"},
                                {"type": "password", "label": "Password", "value": "x", "rect": {"x": 1, "y": 1, "w": 2, "h": 2}}])
    assert PE.normalise(snap, AC.Stamp("g", 1, "t", "dom", 0.0)).unlocated_sensitive is False
    snap2 = dom_snapshot(fields=[{"type": "password", "label": "Password", "value": "x"}])
    assert PE.normalise(snap2, AC.Stamp("g", 1, "t", "dom", 0.0)).unlocated_sensitive is True


def test_low_adapter_must_bind_the_target():
    class Unbound(FakeAdapter):
        def capture(self, target_id):
            return dom_snapshot()                          # no target_id
    acc = AC.AccessController()
    p = PE.Perceiver(acc, {AC.ScopeKind.BROWSER_TAB: Unbound("browser_tab", dom_snapshot())})
    acc.grant_scope("browser_tab", "t", "x", ["observe"])
    with pytest.raises(PE.PerceptionRefused) as e:
        p.observe()
    assert e.value.code == "TARGET_UNBOUND"
