"""Regressions for the coordinator repair after driver run r3 (Codex rounds R3..R8 on c4550417..0683d438) and the V3.1
fallback review FB2 of c4550417 (D:/uri-dev/m95-evidence/FB2_fallback_review_c4550417.txt).

Synthetic data only.
"""
import ast
import json
import sys
import unicodedata
from pathlib import Path

import httpx
import pytest

from uri_privacy import PrivacyRefused
from uri_privacy import classify as C
from uri_privacy.classify import classify, fold
from uri_web import search as S

from .helpers import TGateway

ROOT = Path(__file__).resolve().parents[2]
CARD = "4111111111111111"


def capture():
    sent = []

    def handler(req):
        sent.append(req)
        return httpx.Response(200, json={"results": [{"title": "t", "url": "https://example.com/a", "content": "c"}]})
    return sent, httpx.MockTransport(handler)


def wire(q):
    sent, t = capture()
    r = S.TavilyProvider(api_key="k", transport=t, privacy=TGateway()).search(q)
    return r, [json.loads(x.content)["query"] for x in sent]


def digits(s):
    return "".join(ch for ch in fold(s)[0] if ch.isdigit())


def invisible_sample():
    cps = [c for c in range(0x0000, 0x00A0) if unicodedata.category(chr(c)) == "Cc" and not chr(c).isspace()]
    cps += [c for c in range(0x0000, 0x30000) if unicodedata.category(chr(c)) == "Cf"]
    cps += [0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180E, 0x180F, 0x2800, 0x3164, 0xFE00, 0xFE0F, 0xFFA0,
            0x1BCA0, 0xE0100, 0xE01EF, 0xE000, 0xF8FF, 0xF0000, 0x0378, 0x0380, 0xFFFF]      # PUA and unassigned too
    return sorted(set(cps))


# --- FB2 R1-01: every invisible category, as a separator and inside a label -------------------------------------------
@pytest.mark.parametrize("cp", invisible_sample())
def test_fb2_r1_01_no_invisible_character_hides_a_card_or_a_credential(cp):
    ch = chr(cp)
    g = TGateway()
    try:
        out = g.prepare(f"card 4111{ch}1111{ch}1111{ch}1111 limit", requester="t", destination="WEB_SEARCH",
                        purpose="p").text
    except PrivacyRefused as exc:                 # LDEC-005: refused on doubt
        assert exc.code == "PRIVACY_DISGUISE_REFUSED"
    else:
        assert CARD not in digits(out) and ch not in out
    with pytest.raises(PrivacyRefused):
        g.prepare(f"wifi pass{ch}word: Mango#2026!", requester="t", destination="WEB_SEARCH", purpose="p")


@pytest.mark.parametrize("q,core", [("aadhaar 2345\u28006789\u28000124", "234567890124"),
                                    ("ssn 123\x0045\x006789", "123456789"), ("my otp\x00 482913", "482913"),
                                    ("pan ABCPE\u28001234F", "abcpe1234f"), ("call +91\u280098450\u280012345", "9845012345")])
def test_fb2_r1_01_other_values_with_invisibles(q, core):
    """Checked against the raw value, not against the classifier under test."""
    r, sent = wire(q)
    for s in sent:
        flat = "".join(ch for ch in fold(s)[0].lower() if ch.isalnum())
        assert core not in flat, s
        assert all(not unicodedata.category(c).startswith("C") or c.isspace() for c in s)


def test_canonical_is_what_is_sent():
    q = "caf\u00e9 \uff21\uff22 \u2764\ufe0f x\u2010y 10\u201320"
    out = TGateway().prepare(q, requester="t", destination="EXTERNAL_MODEL", purpose="p").text
    assert out == C.canonical(q) == "caf\u00e9 AB \u2764\ufe0f x-y 10-20"
    assert TGateway().prepare(q, requester="t", destination="LOCAL_BRAIN", purpose="p").text == q


# --- R3..R8 separator family and R8-01 --------------------------------------------------------------------------------
@pytest.mark.parametrize("q", ["card 4111;1111;1111;1111 limit", "card 4111; 1111; 1111; 1111", "card 4111 ; 1111 ; 1111 ; 1111",
                               "card 4111 - 1111 - 1111 - 1111", "card 4111 . 1111 . 1111 . 1111",
                               "card 4111--1111--1111--1111", "card 4111 - . 1111 - . 1111 - . 1111",
                               "card 4111;1111;1111;1111exp", "card 4111111111111111exp", "card 4111+1111 1111 1111",
                               "card 4111 1111 1111 11119", "card 4111*1111*1111*1111", "card 4111 ~ 1111 ~ 1111 ~ 1111"])
def test_r3_r8_any_separator_or_tail_keeps_the_card_off_the_wire(q):
    r, sent = wire(q)
    assert all(CARD not in digits(s) for s in sent)


# The other examples this test held (big totals, coordinates, ISBN, order ids, IMEI) are superseded by owner decision LDEC-006 (digit budget): 9+ digits in one run are redacted
# (test_ldec006.py); dates, times and IP addresses are the exempt classes.
@pytest.mark.parametrize("benign", ["meeting 2026-10-22 14:30:00 in room 4", "server 192.168.100.200 is down",
                                    "train 12627 at 19:20 on 2026-10-22"])
def test_long_number_rule_keeps_ordinary_numbers_readable(benign):
    assert not classify(benign).categories(), benign


def test_long_number_does_not_shadow_a_specific_grant():
    from uri_privacy.grants import GrantStore
    owner = object()
    grants = GrantStore(principal_verifier=lambda p: "owner" if p is owner else None)
    grants.grant(requester="t", categories=["GOV_ID"], purpose="p", destination="WEB_SEARCH", authorized_by="user:owner",
                 principal=owner)
    e = TGateway(grants=grants).prepare("status of Aadhaar 2345 6789 0124", requester="t", destination="WEB_SEARCH",
                                        purpose="p")
    assert "2345 6789 0124" in e.text


# --- R8-02: LOG with an encoded credential -----------------------------------------------------------------------------
@pytest.mark.parametrize("line", ["Authorization%3A%20Bearer%20sk-abcdefghijklmnop0123456789",
                                  "auth&#58; Bearer sk-abcdefghijklmnop0123456789", "password%3DMango%232026"])
def test_r8_02_log_never_keeps_an_encoded_credential(line):
    out = TGateway().prepare(line, requester="t", destination="LOG", purpose="p").text
    assert "sk-abc" not in out and "Mango" not in out


# --- R8-03: tokens ----------------------------------------------------------------------------------------------------
def test_r8_03_tokens_are_letters_only_and_do_not_resolve_across_scopes(monkeypatch):
    import secrets as SEC
    from uri_privacy import vault as V
    g = TGateway()
    monkeypatch.setattr(V.secrets, "choice", lambda alphabet: "q")          # force identical random suffixes
    a = g.prepare("mail alice@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p", scope="A")
    b = g.prepare("mail bob@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p", scope="B")
    assert a.text != b.text                                                  # scope identity survives forced RNG collision
    assert g.restore(a.text, "A", requester="t") == "mail alice@example.in"
    assert g.restore(a.text, "B", requester="t") == a.text                    # foreign token stays opaque
    monkeypatch.undo()
    tok = g.prepare("mail c@example.in", requester="t", destination="EXTERNAL_MODEL", purpose="p").text
    assert not any(ch.isdigit() for ch in tok.split("_")[-1])
    assert SEC is not None


# --- R8-04 / R3-04: audit failure keeps the grant --------------------------------------------------------------------
def test_r8_04_failed_success_audit_keeps_the_grant():
    from uri_privacy.audit import PrivacyAudit
    from uri_privacy.grants import GrantStore

    class FailOnSuccess(PrivacyAudit):
        def write(self, **f):
            if f.get("outcome") in ("ALLOWED", "SANITIZED"):
                raise OSError("disk full")
            return super().write(**f)
    owner = object()
    grants = GrantStore(principal_verifier=lambda p: "owner" if p is owner else None)
    gr = grants.grant(requester="t", categories=["CONTACT"], purpose="p", destination="WEB_SEARCH",
                      authorized_by="user:owner", principal=owner)
    with pytest.raises(PrivacyRefused):
        TGateway(grants=grants, audit=FailOnSuccess()).prepare("who is asha@example.in", requester="t",
                                                                destination="WEB_SEARCH", purpose="p")
    assert [g for g in grants.list() if g["grant_id"] == gr.grant_id][0]["uses_left"] == 1


# --- FB2 R1-02: compiled harness instruction --------------------------------------------------------------------------
def _worker_fns():
    src = (ROOT / "scripts" / "run_uri_integrated_worker.py").read_text(encoding="utf-8")
    nodes = [n for n in ast.parse(src).body if (isinstance(n, ast.FunctionDef) and n.name in ("harness_private",
             "harness_approval_private")) or (isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "HARNESS_TURNS"
                                                                                  for t in n.targets))]
    ns = {}
    exec(compile(ast.Module(nodes, []), "worker_fns", "exec"), ns)
    return ns, src


class TurnError(Exception):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class FakeTurns:
    def __init__(self):
        self.cancelled = []

    def handle(self, kind, command):
        if kind == "turn_cancel":
            self.cancelled.append(command["turn_id"])
            return {"state": "cancelled"}
        raise AssertionError(kind)


def approval(instruction):
    return {"state": "approval_required", "turn_id": "T-1", "executor_kind": "client_external_harness",
            "approval_request": {"arguments": {"inputs": {"instruction": instruction, "expected_file": "out.txt"}}}}


@pytest.fixture
def fns(monkeypatch, tmp_path):
    monkeypatch.setenv("URI_PRIVACY_HOME", str(tmp_path / "privacy"))
    import uri_privacy.gateway as G
    monkeypatch.setattr(G, "_default", None)
    return _worker_fns()[0]


def test_fb2_r1_02_an_instruction_from_an_earlier_turn_is_checked_at_approval(fns):
    turns = FakeTurns()
    with pytest.raises(TurnError) as e:
        fns["harness_approval_private"]("turn_intent", approval("note the wifi password: Mango#2026!"), turns, TurnError)
    assert e.value.code == "PRIVACY_REFUSED" and turns.cancelled == ["T-1"]


def test_fb2_r1_02_an_instruction_that_would_change_is_refused_not_rewritten(fns):
    turns = FakeTurns()
    with pytest.raises(TurnError) as e:
        fns["harness_approval_private"]("turn_start", approval("mail the summary to asha.rao7@example.in"), turns, TurnError)
    assert e.value.code == "PRIVACY_INSTRUCTION_CHANGED" and turns.cancelled == ["T-1"]


def test_fb2_r1_02_clean_instructions_and_other_rows_pass(fns):
    turns = FakeTurns()
    ok = approval("summarise notes.md into out.txt")
    assert fns["harness_approval_private"]("turn_start", ok, turns, TurnError) is ok
    local = {**ok, "executor_kind": "server_local_model"}
    assert fns["harness_approval_private"]("turn_start", local, turns, TurnError) is local
    assert turns.cancelled == []


def test_fb2_r1_02_missing_instruction_fails_closed(fns):
    turns = FakeTurns()
    bad = {"state": "approval_required", "turn_id": "T-2", "executor_kind": "client_external_harness",
           "approval_request": {"arguments": {}}}
    with pytest.raises(TurnError) as e:
        fns["harness_approval_private"]("turn_start", bad, turns, TurnError)
    assert e.value.code == "PRIVACY_INSTRUCTION_UNVERIFIED" and turns.cancelled == ["T-2"]


def test_fb2_r1_02_wired_after_the_supervised_path():
    _, src = _worker_fns()
    assert "harness_approval_private(\n                            kind, turns.handle(kind, harness_private(kind, command, TurnError)), turns, TurnError)" in src


# --- FB2 R1-05 ---------------------------------------------------------------------------------------------------------
def test_fb2_r1_05_split_pass_word_label():
    with pytest.raises(PrivacyRefused):
        TGateway().prepare("pass word: Mango#2026!", requester="t", destination="WEB_SEARCH", purpose="p")
