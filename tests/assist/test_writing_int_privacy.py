"""Writing Intelligence integration review WI-INT R2-01: labelled passwords, codes and keys never reach the Brain.

redact_text alone missed labelled values ("Password: Office@2026", "otp is 482913", "api_key: ..."); the guard now also
asks the M95 classifier (uri_privacy.classify) and refuses CREDENTIAL and SECRET_LIKE findings. Checked through every
Brain path: the writing functions, the Office /writing/* routes and the Assist bridge job.
"""
from __future__ import annotations

import pytest

from uri_assist import writing as W
from uri_office.brain import OfficeBrain
from uri_office.errors import OfficeError
from uri_office.service import Office

from tests.assist.test_writing import FakeBrain, _bridge
from tests.office_u2.test_writing_service import FakeClient

SECRETS = [
    "my password is hunter2",
    "pwd: Tr0ub4dor&3",
    "otp is 482913",
    "Password: Office@2026",
    "Login ID: dsouza Password: Welcome@123",
    "api_key: abcd1234efgh5678ijkl",
    "secret: Tr0ub4dor&3xyz",
    "The default password for the new mail account is Welcome@123, please change it.",
    "-----BEGIN RSA PRIVATE KEY-----\nMIIEow\n-----END RSA PRIVATE KEY-----",
]
ORDINARY = [
    "Please send the circular on leave to all sections by Monday.",
    "The meeting with Shri Anil Verma is on 5th November.",
    "Sanction Rs. 4,75,000 under F.No. 12/3/2026-Estt dated 5.11.2026.",
    "Commit 3f445a75 fixed the bug.",
]


@pytest.mark.parametrize("text", SECRETS)
def test_secret_text_never_reaches_the_brain_through_the_writing_functions(text):
    b = FakeBrain({"status": "ok", "message": "", "text": "x"})
    for call in (lambda: W.proofread(text, client=b), lambda: W.rewrite(text, "formal", client=b),
                 lambda: W.complete(text, client=b)):
        with pytest.raises(W.WritingError) as e:
            call()
        assert e.value.code == "SENSITIVE_TEXT"
    assert b.bodies == []


@pytest.mark.parametrize("text", SECRETS)
def test_secret_text_never_reaches_the_brain_through_the_office_routes(tmp_path, text):
    client = FakeClient()
    o = Office(tmp_path / "state", allowed_roots=[tmp_path], brain=OfficeBrain(client))
    for verb, body in (("proofread", {"text": text}), ("rewrite", {"text": text, "tone": "concise"}),
                       ("complete", {"text": text})):
        with pytest.raises(OfficeError) as e:
            o.writing(verb, body)
        assert e.value.code == "SENSITIVE_TEXT" and e.value.status == 403
    assert client.bodies == []
    assert o.writing("check", {"text": text})["suggestions"] is not None   # local checks still run


@pytest.mark.parametrize("text", SECRETS[:4])
def test_secret_text_never_reaches_the_brain_through_the_assist_bridge(text):
    b = FakeBrain({"status": "ok", "message": "", "text": "x"})
    _, br = _bridge(b)
    wid = br.handle("assist_write_brain", {"command": "assist_write_brain", "text": text, "op": "proofread"})["write_id"]
    br._wjob[1].join(5)
    st = br.handle("assist_write_status", {"command": "assist_write_status", "write_id": wid})
    assert st["status"] == "FAILED" and st["error"] == "SENSITIVE_TEXT"
    assert b.bodies == []


@pytest.mark.parametrize("text", ORDINARY)
def test_ordinary_office_text_still_goes_to_the_brain(text):
    b = FakeBrain({"status": "ok", "message": "", "text": text})
    W.proofread(text, client=b)
    assert len(b.bodies) == 1
