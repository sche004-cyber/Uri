import time

import pytest

from uri_operational_intelligence import brain_client as BC
from tests.oi.fake_llama import FakeLlama, free_port


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def body():
    return {"model": "local", "messages": [{"role": "user", "content": "hi"}], "max_tokens": 50}


def test_stream_complete_separates_reasoning_and_answer(fake):
    fake.scripts.append({"chunks": [("reasoning", "think "), ("reasoning", "more"), ("answer", "Hel"), ("answer", "lo")],
                         "finish": "stop"})
    seen = []
    r = BC.BrainClient(fake.url).stream_chat(body(), on_delta=lambda k, t: seen.append((k, t)))
    assert r.status == BC.COMPLETE and r.ok
    assert r.text == "Hello" and r.reasoning == "think more"
    assert seen[0] == ("reasoning", "think ") and seen[-1] == ("answer", "lo")
    assert r.ttft_s is not None and r.first_answer_s >= r.ttft_s
    assert r.timings["prompt_n"] == 12
    assert fake.requests[0]["stream"] is True and fake.requests[0]["stream_options"] == {"include_usage": True}


def test_length_is_incomplete_not_success(fake):
    fake.scripts.append({"chunks": [("answer", "partial")], "finish": "length"})
    r = BC.BrainClient(fake.url).stream_chat(body())
    assert r.status == BC.INCOMPLETE_LENGTH and not r.ok and r.text == "partial"


def test_cancel_mid_stream_closes_connection_and_server_sees_disconnect(fake):
    fake.scripts.append({"chunks": [("answer", "x")] * 200, "finish": "stop", "delay": 0.02})
    tok = BC.CancelToken()
    got = []

    def on(kind, t):
        got.append(t)
        if len(got) == 5:
            tok.cancel("test")
    t0 = time.monotonic()
    r = BC.BrainClient(fake.url).stream_chat(body(), cancel=tok, on_delta=on)
    assert r.status == BC.CANCELLED and not r.ok
    assert time.monotonic() - t0 < 2.0
    deadline = time.monotonic() + 3
    while fake.disconnects == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert fake.disconnects == 1           # the server observed the disconnect (slot release path)
    assert 5 <= len(got) < 200


def test_cancel_during_prefill_before_first_token(fake):
    fake.scripts.append({"chunks": [("answer", "late")], "finish": "stop", "first_delay": 3.0})
    tok = BC.CancelToken()
    import threading
    threading.Timer(0.3, tok.cancel).start()
    t0 = time.monotonic()
    r = BC.BrainClient(fake.url).stream_chat(body(), cancel=tok)
    assert r.status == BC.CANCELLED and time.monotonic() - t0 < 1.5 and r.text == ""


def test_first_token_timeout(fake):
    fake.scripts.append({"chunks": [("answer", "late")], "finish": "stop", "first_delay": 2.0})
    r = BC.BrainClient(fake.url).stream_chat(body(), deadlines=BC.Deadlines(first_token_s=0.4, idle_s=5, total_s=10))
    assert r.status == BC.TIMEOUT_FIRST_TOKEN and r.text == ""


def test_stall_after_output_began(fake):
    fake.scripts.append({"chunks": [("answer", "a"), ("answer", "b")], "finish": "stop", "delay": 1.5})
    r = BC.BrainClient(fake.url).stream_chat(body(), deadlines=BC.Deadlines(first_token_s=5, idle_s=0.4, total_s=10))
    assert r.status == BC.STALLED and r.text == "a"


def test_total_deadline(fake):
    fake.scripts.append({"chunks": [("answer", "a")] * 50, "finish": "stop", "delay": 0.1})
    r = BC.BrainClient(fake.url).stream_chat(body(), deadlines=BC.Deadlines(first_token_s=5, idle_s=5, total_s=0.5))
    assert r.status == BC.DEADLINE_EXCEEDED and 0 < len(r.text) < 50


def test_unreachable_is_reported_after_one_retry():
    r = BC.BrainClient("http://127.0.0.1:%d" % free_port()).stream_chat(body())
    assert r.status == BC.UNREACHABLE and r.retried is True and not r.ok


def test_stream_broken_after_output_is_interrupted_not_retried(fake):
    fake.scripts.append({"chunks": [("answer", "a"), ("answer", "b"), ("answer", "c")], "finish": "stop",
                         "drop_after": 2, "delay": 0.01})
    r = BC.BrainClient(fake.url).stream_chat(body())
    assert r.status == BC.INTERRUPTED and r.text == "ab" and r.retried is False
    assert len(fake.requests) == 1


def test_http_error_and_bad_sse(fake):
    fake.scripts.append({"status": 500})
    assert BC.BrainClient(fake.url).stream_chat(body()).status == BC.HTTP_ERROR
    fake.scripts.append({"raw": b"data: {not json}\n\n", "chunks": [], "finish": None})
    assert BC.BrainClient(fake.url).stream_chat(body()).status == BC.PROTOCOL_ERROR


def test_stream_without_finish_is_interrupted(fake):
    fake.scripts.append({"chunks": [("answer", "a")], "finish": None})
    r = BC.BrainClient(fake.url).stream_chat(body())
    assert r.status == BC.INTERRUPTED


def test_complete_json_paths(fake):
    c = BC.BrainClient(fake.url)
    fake.scripts.append({"json": '{"a": 1}', "finish": "stop"})
    r = c.complete_json(body())
    assert r.status == BC.COMPLETE and r.text == '{"a": 1}' and fake.requests[-1]["stream"] is True
    fake.scripts.append({"json": '{"a":', "finish": "length"})
    assert c.complete_json(body()).status == BC.INCOMPLETE_LENGTH
    fake.scripts.append({"status": 503})
    assert c.complete_json(body()).status == BC.HTTP_ERROR
    assert BC.BrainClient("http://127.0.0.1:%d" % free_port()).complete_json(body()).status == BC.UNREACHABLE


def test_deadline_and_cancel_work_while_waiting_for_response_headers(fake):
    """Live finding 2026-10-08: with the slot busy, headers did not arrive for minutes and a blocking send() ignored
    the first-token deadline (495 s turn). Both must act during the header wait."""
    fake.scripts.append({"chunks": [("answer", "late")], "finish": "stop", "header_delay": 3.0})
    t0 = time.monotonic()
    r = BC.BrainClient(fake.url).stream_chat(body(), deadlines=BC.Deadlines(first_token_s=0.4, idle_s=5, total_s=10))
    assert r.status == BC.TIMEOUT_FIRST_TOKEN and time.monotonic() - t0 < 1.5
    fake.scripts.append({"chunks": [("answer", "late")], "finish": "stop", "header_delay": 3.0})
    tok = BC.CancelToken()
    import threading
    threading.Timer(0.3, tok.cancel).start()
    t0 = time.monotonic()
    r = BC.BrainClient(fake.url).stream_chat(body(), cancel=tok)
    assert r.status == BC.CANCELLED and time.monotonic() - t0 < 1.5


def test_abandoned_header_wait_disconnects_and_pool_recovers(fake):
    """Round-6 audit: an abandoned send must not keep its connection (and the server's queued request) forever."""
    c = BC.BrainClient(fake.url)
    for _ in range(10):        # more abandons than the 8-connection pool
        # headers withheld far beyond the read cap: only the client-side read timeout can free these connections
        fake.scripts.append({"chunks": [("answer", "late")], "finish": "stop", "header_delay": 20.0})
        r = c.stream_chat(body(), deadlines=BC.Deadlines(first_token_s=0.2, idle_s=0.2, total_s=5))
        assert r.status in (BC.TIMEOUT_FIRST_TOKEN, BC.HTTP_ERROR)
    time.sleep(1.5)                        # read cap (0.2 + 1.0 s) has passed for every abandoned send
    fake.scripts.append({"chunks": [("answer", "ok")], "finish": "stop"})
    r = c.stream_chat(body())
    assert r.status == BC.COMPLETE and r.text == "ok"


def test_seam_timeout_disconnects_so_the_server_can_drop_the_generation(fake):
    fake.scripts.append({"chunks": [("answer", "x")] * 200, "finish": "stop", "delay": 0.02})
    r = BC.BrainClient(fake.url).complete_json(body(), timeout_s=0.5)
    assert r.status == BC.DEADLINE_EXCEEDED and fake.requests[-1]["stream"] is True
    deadline = time.monotonic() + 3
    while fake.disconnects == 0 and time.monotonic() < deadline:
        time.sleep(0.05)
    assert fake.disconnects == 1
