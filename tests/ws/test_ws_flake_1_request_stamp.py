"""WS-FLAKE-1: a fresh Brain-host request must never be refused as stale because of its own time stamp.

write_host_request rounded `requested_at` to the NEAREST millisecond, which can be up to 0.5 ms in the future; the host
then saw a negative age and dropped the request as IGNORED_INVALID_OR_STALE. These tests use a fixed clock just past a
half-millisecond, so they fail every time on 03f0bf2c instead of at random.

Self-contained: no fixture files; everything is built here.
"""
import json

import pytest

from uri_operational_intelligence import brain_health as BH
from tests.ws.test_ws_hardening import CARD, G, Seq, new_host, raw

CLOCKS = (1_700_000_000.0006, 1_700_000_000.0005, 1_700_000_000.9999, 1_760_000_123.4567891)


@pytest.mark.parametrize("t", CLOCKS)
def test_wsf_ac1_stamp_is_never_in_the_future(tmp_path, monkeypatch, t):
    monkeypatch.setattr(BH.time, "time", lambda: t)
    (tmp_path / "client").mkdir()
    req = BH.write_host_request(tmp_path / "client", "restart")
    assert req["requested_at"] <= t
    assert t - req["requested_at"] < 0.001
    stored = json.loads((tmp_path / "client" / BH.REQUEST_FILE).read_text())
    assert stored["requested_at"] <= t


@pytest.mark.parametrize("t", CLOCKS)
@pytest.mark.parametrize("action", ("restart", "stop"))
def test_wsf_ac2_a_request_taken_at_once_is_accepted(tmp_path, monkeypatch, t, action):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    h.now = lambda: t
    monkeypatch.setattr(BH.time, "time", lambda: t)
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    BH.write_host_request(tmp_path / "client", action)
    assert h.take_request() == action
    assert h.report["last_request"]["result"] == "ACCEPTED"


def test_wsf_ac3_stale_requests_are_still_refused(tmp_path, monkeypatch):
    H, h = new_host(tmp_path, Seq([G.census(raw([], 300), card=CARD)]))
    t = 1_700_000_000.0006
    monkeypatch.setattr(BH.time, "time", lambda: t)
    (tmp_path / "client").mkdir(parents=True, exist_ok=True)
    BH.write_host_request(tmp_path / "client", "restart")
    h.now = lambda: t + H.REQUEST_MAX_AGE_S + 1
    assert h.take_request() is None
    assert h.report["last_request"]["result"] == "IGNORED_INVALID_OR_STALE"
