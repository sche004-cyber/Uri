import json
import socket
from datetime import datetime, timedelta, timezone
from urllib.error import URLError

import pytest

from polish import (FEW_SHOT_MESSAGES, OLLAMA_CHAT_URL, OLLAMA_PS_URL, PROMPT_VERSION,
                    Polisher, SYSTEM_PROMPT, _keep_alive_seconds)


def response(text):
    return json.dumps({"message": {"content": text}}).encode()


def unloaded_ps(*_args):
    return b'{"models": []}'


def polisher(*args, **kwargs):
    kwargs.setdefault("http_get", unloaded_ps)
    return Polisher(*args, **kwargs)


def test_success_and_request_body_are_guarded_and_configured():
    calls = []
    def post(url, body, timeout):
        calls.append((url, json.loads(body), timeout))
        return response("This is polished dictation.")

    result = polisher(True, "test-model", 3.5, http_post=post).polish("this is raw dictation")

    assert (result.text, result.used, result.fallback_reason) == ("This is polished dictation.", True, None)
    url, body, timeout = calls[0]
    assert (url, timeout, body["model"], body["stream"], body["think"]) == (OLLAMA_CHAT_URL, 3.5, "test-model", False, False)
    assert body["options"] == {"temperature": 0.2, "num_ctx": 16384}
    assert body["keep_alive"] == "30m"
    assert body["messages"][0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert body["messages"][-1] == {"role": "user", "content": "<dictation>this is raw dictation</dictation>"}


def test_prompt_v2_contains_fresh_few_shot_examples():
    assert PROMPT_VERSION == "v2"
    assert len(FEW_SHOT_MESSAGES) == 6
    messages = Polisher._messages("final dictation")
    assert messages[0]["content"] == SYSTEM_PROMPT
    assert sum(message["role"] == "assistant" for message in messages) == 6
    assert messages[-1]["content"] == "<dictation>final dictation</dictation>"


def test_edge_success_does_not_call_main_model():
    calls = []
    def post(_url, body, _timeout):
        calls.append(json.loads(body)["model"])
        return response("Clean edge result.")

    result = polisher(True, "main", 1, polish_edge_model="edge", http_post=post).polish("clean edge input here")

    assert (result.text, result.model, result.escalated) == ("Clean edge result.", "edge", False)
    assert calls == ["edge"]


def test_edge_guard_rail_failure_escalates_once_to_main_model():
    calls = []
    def post(_url, body, _timeout):
        model = json.loads(body)["model"]
        calls.append(model)
        return response("Sure, I can do that" if model == "edge" else "Clean main result.")

    result = polisher(True, "main", 1, polish_edge_model="edge", http_post=post).polish("clean edge input here")

    assert (result.text, result.used, result.model, result.escalated) == ("Clean main result.", True, "main", True)
    assert calls == ["edge", "main"]


def test_edge_and_main_guard_rail_failures_paste_raw_text():
    calls = []
    def post(_url, body, _timeout):
        calls.append(json.loads(body)["model"])
        return response("")

    result = polisher(True, "main", 1, polish_edge_model="edge", http_post=post).polish("clean edge input here")

    assert (result.text, result.used, result.model, result.escalated, result.fallback_reason) == (
        "clean edge input here", False, None, True, "empty")
    assert calls == ["edge", "main"]


def test_main_model_only_when_edge_is_not_set():
    calls = []
    def post(_url, body, _timeout):
        calls.append(json.loads(body)["model"])
        return response("Clean main result.")

    result = polisher(True, "main", 1, http_post=post).polish("clean main input here")

    assert (result.model, result.escalated, calls) == ("main", False, ["main"])


def test_short_and_off_never_escalate_or_call_http():
    def post(*_args):
        raise AssertionError("HTTP should not run")
    assert polisher(True, "main", 1, polish_edge_model="edge", http_post=post).polish("one two three").fallback_reason == "short"
    assert polisher(False, "main", 1, polish_edge_model="edge", http_post=post).polish("one two three four").fallback_reason == "off"


def test_loaded_context_length_is_reused_for_each_escalation_model():
    calls = []
    ps_response = json.dumps({"models": [
        {"name": "edge", "context_length": 4096},
        {"name": "main", "context_length": 8192},
    ]}).encode()
    def post(_url, body, _timeout):
        request = json.loads(body)
        calls.append(request)
        return response("" if request["model"] == "edge" else "Clean main result.")

    polisher(True, "main", 1, polish_num_ctx=16384, polish_edge_model="edge", http_post=post,
             http_get=lambda *_args: ps_response).polish("clean main input here")

    assert [(call["model"], call["options"]["num_ctx"]) for call in calls] == [("edge", 4096), ("main", 8192)]


@pytest.mark.parametrize(("exc", "reason"), [
    (TimeoutError(), "timeout"),
    (socket.timeout(), "timeout"),
    (URLError(socket.timeout()), "timeout"),
    (ConnectionError(), "error"),
])
def test_connection_and_timeout_fall_back(exc, reason):
    def post(*_args):
        raise exc
    result = polisher(True, "model", 1, http_post=post).polish("one two three four")
    assert (result.text, result.used, result.fallback_reason) == ("one two three four", False, reason)


def test_empty_output_falls_back():
    result = polisher(True, "model", 1, http_post=lambda *_args: response("  ")).polish("one two three four")
    assert result.fallback_reason == "empty"


@pytest.mark.parametrize("prefix", ["sure", "here is", "here's", "certainly", "i can't", "i cannot", "i'm sorry", "as an ai"])
def test_preambles_and_refusals_fall_back(prefix):
    result = polisher(True, "model", 1, http_post=lambda *_args: response(prefix + " one two three four")).polish("one two three four")
    assert result.fallback_reason == "refusal"


def test_dictation_starting_with_preamble_is_used():
    text = "Sure, let's meet at ten tomorrow"
    result = polisher(True, "model", 1, http_post=lambda *_args: response("Sure, let's meet at ten tomorrow.")).polish(text)
    assert (result.text, result.used, result.fallback_reason) == ("Sure, let's meet at ten tomorrow.", True, None)


def test_unsolicited_preamble_is_refusal():
    result = polisher(True, "model", 1, http_post=lambda *_args: response("Sure! Meet at ten tomorrow.")).polish("meet at ten tomorrow please")
    assert result.fallback_reason == "refusal"


@pytest.mark.parametrize("output", ["one two three four five six seven", "one"])
def test_length_limits_fall_back(output):
    result = polisher(True, "model", 1, http_post=lambda *_args: response(output)).polish("one two three four")
    assert result.fallback_reason == "length"


def test_short_and_disabled_skip_http():
    def post(*_args):
        raise AssertionError("HTTP should not run")
    assert polisher(True, "model", 1, http_post=post).polish("one two three").fallback_reason == "short"
    assert polisher(False, "model", 1, http_post=post).polish("one two three four").fallback_reason == "off"


def test_dictation_delimiters_are_stripped():
    result = polisher(True, "model", 1, http_post=lambda *_args: response("<dictation>One two three four</dictation>")).polish("one two three four")
    assert result.text == "One two three four"


def test_longer_loaded_expiry_is_preserved():
    now = datetime(2026, 10, 2, 8, 41, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    get_calls, post_calls = [], []

    def get(url, timeout):
        get_calls.append((url, timeout))
        return json.dumps({"models": [{"name": "test-model", "expires_at": (now + timedelta(minutes=59)).isoformat()}]}).encode()

    def post(_url, body, _timeout):
        post_calls.append(json.loads(body))
        return response("One two three four")

    Polisher(True, "test-model", 3, polish_keep_alive="30m", http_post=post, http_get=get, now=lambda: now).polish("one two three four")

    assert get_calls == [(OLLAMA_PS_URL, 1.0)]
    assert post_calls[0]["keep_alive"] == "3540s"


@pytest.mark.parametrize(("ps_response", "keep_alive"), [
    (b'{"models": [{"name": "test-model", "expires_at": "2026-10-02T09:00:00+05:30"}]}', "30m"),
    (b'{"models": [{"name": "other-model", "expires_at": "2026-10-02T10:00:00+05:30"}]}', "30m"),
])
def test_shorter_or_absent_loaded_model_uses_configured_keep_alive(ps_response, keep_alive):
    now = datetime(2026, 10, 2, 8, 41, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    post_calls = []

    def post(_url, body, _timeout):
        post_calls.append(json.loads(body))
        return response("One two three four")

    Polisher(True, "test-model", 3, polish_keep_alive=keep_alive, http_post=post,
             http_get=lambda *_args: ps_response, now=lambda: now).polish("one two three four")

    assert post_calls[0]["keep_alive"] == keep_alive


def test_ps_failure_uses_configured_keep_alive():
    post_calls = []

    def post(_url, body, _timeout):
        post_calls.append(json.loads(body))
        return response("One two three four")

    Polisher(True, "test-model", 3, polish_keep_alive="1h", http_post=post,
             http_get=lambda *_args: (_ for _ in ()).throw(ConnectionError())).polish("one two three four")

    assert post_calls[0]["keep_alive"] == "1h"


def test_forever_loaded_expiry_is_preserved():
    now = datetime(2026, 10, 2, 8, 41, tzinfo=timezone.utc)
    post_calls = []

    def post(_url, body, _timeout):
        post_calls.append(json.loads(body))
        return response("One two three four")

    ps_response = json.dumps({"models": [{"name": "test-model", "expires_at": (now + timedelta(days=3651)).isoformat()}]}).encode()
    Polisher(True, "test-model", 3, polish_keep_alive="30m", http_post=post,
             http_get=lambda *_args: ps_response, now=lambda: now).polish("one two three four")

    assert post_calls[0]["keep_alive"] == -1


@pytest.mark.parametrize(("value", "seconds"), [
    ("30m", 1800), ("1h", 3600), ("45s", 45), ("2340", 2340), (2340, 2340), ("-1", None), ("-4m", None),
])
def test_keep_alive_duration_parsing(value, seconds):
    assert _keep_alive_seconds(value) == seconds
