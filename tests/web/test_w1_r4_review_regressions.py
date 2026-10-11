"""Regressions for review R4 of 1615512 (findings R4-02, R4-03). Each fails without its repair."""
from tests.web.d7_invariant import only_source_quotes  # D7
import socket
import threading
import time

import pytest

from uri_web import evaluate as EV
from uri_web import netpolicy as NP
from uri_web import records as R
from uri_web import safe_fetch as SF
from uri_web import synthesize as SY

# ---- R4-02: magnitudes and units are part of the number ----------------------------------------------------------

DIFFERENT = [("$5bn", "$5m"), ("$5M", "$5k"), ("2 crore", "2 lakh"), ("Rs.500 trillion", "Rs.500 crore"),
             ("5 miles", "5 km"), ("$5 billion", "$5 million"), ("3.2bn", "3.2mn"), ("10 lakhs", "10 crores")]
SAME = [("$5m", "$5 million"), ("$5m", "$5,000,000"), ("2.5bn", "2.5 billion"), ("5 km", "5 kilometres"),
        ("12%", "12 percent")]


def _sent(x):
    return f"The company raised {x} in new funding from investors this year."


@pytest.mark.parametrize("claim, source", DIFFERENT)
def test_r4_02_verify_drops_a_claim_with_another_magnitude(claim, source):
    v = SY.verify(_sent(claim)[:-1] + " [1].", [_sent(source)])
    assert only_source_quotes(v, [_sent(source)], _sent(claim)) and v.claims   # D7: the source's own value is shown


@pytest.mark.parametrize("claim, source", SAME)
def test_r4_02_verify_keeps_the_same_amount_written_differently(claim, source):
    v = SY.verify(_sent(claim)[:-1] + " [1].", [_sent(source)])
    assert len(v.claims) == 1, v.dropped


def _two(a, b):
    return [{"url": "https://a.example/x", "text": _sent(a)}, {"url": "https://b.example/y", "text": _sent(b)}]


@pytest.mark.parametrize("a, b", DIFFERENT)
def test_r4_02_conflict_detector_sees_magnitude_differences(a, b):
    assert len(EV.evaluate(_two(a, b), "funding").conflicts) == 1


@pytest.mark.parametrize("a, b", SAME)
def test_r4_02_same_amount_is_not_a_conflict(a, b):
    assert EV.evaluate(_two(a, b), "funding").conflicts == []


# ---- R4-03: the total deadline and cancellation hold while headers or chunk framing drip -------------------------

HOST = "127.0.0.2"


@pytest.fixture
def drip_server(monkeypatch):
    """A real local server that drips its response one byte every 0.2 s. 127.0.0.2 counts as public ONLY here."""
    orig = NP.check_address
    monkeypatch.setattr(NP, "check_address", lambda a: None if str(a) == HOST else orig(a))
    servers = []

    def start(payload, delay=0.2):
        s = socket.socket()
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((HOST, 0))
        except OSError:
            pytest.skip("BLOCKED: cannot bind 127.0.0.2")
        s.listen(4)
        servers.append(s)

        def handle(c):
            try:
                c.recv(65536)
                for b in payload:
                    c.sendall(bytes([b]))
                    time.sleep(delay)
            except OSError:
                pass
            c.close()

        def loop():
            while True:
                try:
                    c, _ = s.accept()
                except OSError:
                    return
                threading.Thread(target=handle, args=(c,), daemon=True).start()
        threading.Thread(target=loop, daemon=True).start()
        return s.getsockname()[1]
    yield start
    for s in servers:
        s.close()


SLOW_HEADERS = b"HTTP/1.1 200 OK\r\nX-Pad: " + b"a" * 400
CHUNK_DRIP = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nTransfer-Encoding: chunked\r\n\r\n1;x=" + b"a" * 400


def _fetch(port, cancel=None):
    f = SF.SafeFetcher(resolver=lambda h, p: [HOST], honour_robots=False, allowed_ports={port}, read_timeout=1.0,
                       total_timeout=1.5)
    t0 = time.monotonic()
    rec = f.fetch(f"http://victim.example:{port}/", cancel=cancel).record
    return rec, time.monotonic() - t0


@pytest.mark.parametrize("payload", [SLOW_HEADERS, CHUNK_DRIP], ids=["headers", "chunk-extension"])
def test_r4_03_total_timeout_holds_while_the_server_drips(drip_server, payload):
    rec, elapsed = _fetch(drip_server(payload))
    assert rec.fetch_status == R.TIMED_OUT
    assert elapsed < 3.0, elapsed


@pytest.mark.parametrize("payload", [SLOW_HEADERS, CHUNK_DRIP], ids=["headers", "chunk-extension"])
def test_r4_03_cancel_holds_while_the_server_drips(drip_server, payload):
    cf = SF.CancelFlag()
    threading.Timer(0.5, cf.cancel).start()
    rec, elapsed = _fetch(drip_server(payload), cancel=cf)
    assert rec.fetch_status == R.CANCELLED
    assert elapsed < 1.4, elapsed


def test_r4_03_a_normal_response_is_not_cut(drip_server):
    port = drip_server(b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n\r\nok", delay=0.002)
    f = SF.SafeFetcher(resolver=lambda h, p: [HOST], honour_robots=False, allowed_ports={port}, total_timeout=60)
    res = f.fetch(f"http://victim.example:{port}/")
    assert res.record.fetch_status == R.OK and res.text == "ok"
