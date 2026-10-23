"""Office service routes for Writing Intelligence (plan 16, WI-A / WI-7 service part): check, apply, proofread,
rewrite, complete; UTF-16 offsets for the Flutter client; named refusals; nothing touches a document."""
import json
from types import SimpleNamespace

import pytest

from uri_assist import writing as WR
from uri_office.brain import OfficeBrain
from uri_office.errors import OfficeError
from uri_office.service import Office


class FakeClient:
    def __init__(self, *answers):
        self.answers = list(answers)
        self.bodies = []

    def stream_chat(self, body, *, cancel=None, deadlines=None):
        self.bodies.append(body)
        return SimpleNamespace(status="COMPLETE", text=json.dumps(self.answers.pop(0)), total_s=0.2, usage={})


class NoSpell:
    def check(self, text, lang):
        raise WR.WritingError("SPELL_UNAVAILABLE")

    def prewarm(self, lang=None):
        pass


@pytest.fixture(autouse=True)
def no_windows_spell(monkeypatch):
    monkeypatch.setattr(WR, "default_spell", lambda: NoSpell())


def test_check_gives_utf16_offsets_and_apply_round_trips(tmp_path):
    o = Office(tmp_path / "state", allowed_roots=[tmp_path])
    t = "\U0001F600 i agree  now"
    r = o.writing("check", {"text": t})
    assert r["status"]["spelling"] == "SPELL_UNAVAILABLE"
    i = next(s for s in r["suggestions"] if s["original"] == "i")
    assert (i["start"], i["end"], i["start16"], i["end16"]) == (2, 3, 3, 4)
    acc = [{k: s[k] for k in ("start", "end", "original")} | {"replacement": s["replacements"][0]}
           for s in r["suggestions"]]
    assert o.writing("apply", {"text": t, "accepted": acc})["text"] == "\U0001F600 I agree now"


def test_brain_routes_need_a_brain_and_use_it_only_on_request(tmp_path):
    o = Office(tmp_path / "state", allowed_roots=[tmp_path])
    with pytest.raises(OfficeError) as e:
        o.writing("proofread", {"text": "abc"})
    assert e.value.code == "BRAIN_UNAVAILABLE" and e.value.status == 503
    client = FakeClient({"status": "ok", "message": "", "text": "The files were sent."},
                        {"status": "ok", "message": "", "text": "Kindly send the files."},
                        {"status": "ok", "message": "", "text": "at the earliest."})
    o = Office(tmp_path / "state2", allowed_roots=[tmp_path], brain=OfficeBrain(client))
    o.writing("check", {"text": "The files was sent."})
    assert client.bodies == []                                   # typing checks never call the Brain
    p = o.writing("proofread", {"text": "The files was sent."})
    assert [(s["original"], s["replacements"][0]) for s in p["suggestions"]] == [("was", "were")]
    w = o.writing("rewrite", {"text": "send files", "tone": "formal"})
    assert w["suggestions"][0]["class"] == "rewrite" and w["suggestions"][0]["end16"] == len("send files")
    c = o.writing("complete", {"text": "Please reply"})
    assert c["suggestions"][0]["replacements"][0] == " at the earliest."
    assert len(client.bodies) == 3


def test_refusals_are_named(tmp_path):
    o = Office(tmp_path / "state", allowed_roots=[tmp_path], brain=OfficeBrain(FakeClient()))
    with pytest.raises(OfficeError) as e:
        o.writing("rewrite", {"text": "x", "tone": "loud"})
    assert e.value.code == "BAD_TONE"
    with pytest.raises(OfficeError) as e:
        o.writing("proofread", {"text": "card 4111 1111 1111 1111"})
    assert e.value.code == "SENSITIVE_TEXT" and e.value.status == 403
    with pytest.raises(OfficeError) as e:
        o.writing("check", {"text": 5})
    assert e.value.code == "BAD_REQUEST"
    with pytest.raises(OfficeError) as e:
        o.writing("apply", {"text": "I x", "accepted": [{"start": 0, "end": 1, "original": "i", "replacement": "I"}]})
    assert e.value.code == "STALE_SUGGESTION" and e.value.status == 409
    with pytest.raises(OfficeError) as e:
        o.writing("nope", {"text": ""})
    assert e.value.code == "NOT_FOUND"
