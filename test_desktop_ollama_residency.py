"""Mocked HTTP regressions for desktop Ollama model residency."""

import threading

import pytest
import requests

from uri_core.core.model_providers.base import ModelProviderConfig
from uri_core.core.model_providers.ollama_provider import OllamaProvider
from uri_core.core.model_providers.openai_compatible_provider import OpenAICompatibleProvider
from uri_desktop_seams import ollama_residency


GB = 1024**3
URL = "http://127.0.0.1:11434"


class Reply:
    status_code = 200

    def __init__(self, body):
        self.body = body

    def json(self):
        return self.body


def provider(model, url=URL):
    return OllamaProvider(ModelProviderConfig(base_url=url, model=model, context_tokens=8192))


def chat_reply(model):
    return Reply({"message": {"content": "ok"}, "model": model})


@pytest.fixture(autouse=True)
def fresh_guard(monkeypatch):
    monkeypatch.setattr(ollama_residency, "_states", {})
    monkeypatch.delenv("URI_DESKTOP_OLLAMA_RESIDENCY_ENABLED", raising=False)
    monkeypatch.delenv("URI_DESKTOP_OLLAMA_LARGE_MODEL_BYTES", raising=False)
    monkeypatch.delenv("URI_HARNESS_EDGE_CHAT_MODEL", raising=False)


def test_unloads_only_other_large_models_and_caches_loaded_set(monkeypatch):
    calls = []
    models = [
        {"name": "gemma4:12b", "size_vram": 8 * GB},
        {"name": "qwen3.5:9b", "size": 6 * GB},
        {"name": "qwen3:0.6b", "size": GB // 2},
        {"name": "another-small", "size": GB},
    ]

    def get(url, **kwargs):
        calls.append(("get", url, kwargs["timeout"]))
        assert url.endswith("/api/ps")
        return Reply({"models": models})

    def post(url, **kwargs):
        calls.append(("post", url, kwargs.get("json")))
        return chat_reply("gemma4:12b")

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    brain = provider("gemma4:12b")
    assert brain.complete(system="s", user="u").content == "ok"
    assert brain.complete(system="s", user="u").content == "ok"
    unloads = [item[2] for item in calls if item[0] == "post" and item[1].endswith("/api/generate")]
    assert unloads == [{"model": "qwen3.5:9b", "keep_alive": 0}]
    assert len([item for item in calls if item[0] == "get"]) == 1


def test_unloaded_current_uses_tag_size_and_preserves_configured_edge(monkeypatch):
    calls = []
    monkeypatch.setenv("URI_HARNESS_EDGE_CHAT_MODEL", "custom-edge")

    def get(url, **kwargs):
        calls.append(url)
        if url.endswith("/api/ps"):
            return Reply({"models": [
                {"name": "old-large", "size": 7 * GB},
                {"name": "custom-edge", "size": 3 * GB},
            ]})
        return Reply({"models": [{"name": "new-large", "size": 8 * GB}]})

    def post(url, **kwargs):
        calls.append(kwargs["json"])
        return chat_reply("new-large")

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    provider("new-large").complete(system="s", user="u")
    assert {"model": "old-large", "keep_alive": 0} in calls
    assert {"model": "custom-edge", "keep_alive": 0} not in calls


def test_small_target_does_not_evict_large_brain(monkeypatch):
    posts = []
    monkeypatch.setattr(requests, "get", lambda url, **kw: Reply({"models": [
        {"name": "gemma4:12b", "size": 8 * GB}, {"name": "qwen3:0.6b", "size": GB // 2},
    ]}))
    monkeypatch.setattr(requests, "post", lambda url, **kw: posts.append(url) or chat_reply("qwen3:0.6b"))
    provider("qwen3:0.6b").complete(system="s", user="u")
    assert posts == [f"{URL}/api/chat"]


def test_in_flight_model_is_never_unloaded(monkeypatch):
    started = threading.Event()
    release = threading.Event()
    calls = []
    errors = []

    def get(url, **kwargs):
        if url.endswith("/api/ps"):
            return Reply({"models": [
                {"name": "gemma4:12b", "size": 8 * GB},
                {"name": "qwen3.5:9b", "size": 6 * GB},
            ]})
        raise AssertionError(url)

    def post(url, **kwargs):
        if url.endswith("/api/generate"):
            calls.append(kwargs["json"]["model"])
        elif kwargs["json"]["model"] == "gemma4:12b":
            started.set()
            assert release.wait(3)
        return chat_reply(kwargs["json"]["model"])

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)

    def first():
        try:
            provider("gemma4:12b").complete(system="s", user="u")
        except Exception as exc:
            errors.append(exc)

    thread = threading.Thread(target=first)
    thread.start()
    try:
        assert started.wait(3)
        provider("qwen3.5:9b", "http://localhost:11434").complete(system="s", user="u")
        assert "gemma4:12b" not in calls
    finally:
        release.set()
        thread.join(3)
    assert not errors


def test_stream_keeps_model_in_flight_until_closed(monkeypatch):
    unloads = []

    class StreamReply:
        status_code = 200

        def iter_lines(self):
            yield b'{"message":{"content":"partial"},"done":false}'
            yield b'{"message":{"content":""},"done":true}'

        def close(self):
            pass

    monkeypatch.setattr(requests, "get", lambda url, **kw: Reply({"models": [
        {"name": "gemma4:12b", "size": 8 * GB},
        {"name": "qwen3.5:9b", "size": 6 * GB},
    ]}))

    def post(url, **kwargs):
        if url.endswith("/api/generate"):
            unloads.append(kwargs["json"]["model"])
        if kwargs.get("stream"):
            return StreamReply()
        return chat_reply("qwen3.5:9b")

    monkeypatch.setattr(requests, "post", post)
    stream = provider("gemma4:12b").complete_stream(system="s", user="u")
    try:
        assert next(stream).content == "partial"
        provider("qwen3.5:9b").complete(system="s", user="u")
        assert "gemma4:12b" not in unloads
    finally:
        stream.close()


@pytest.mark.parametrize("failure", ["query", "unload"])
def test_failure_is_harmless_and_http_timeouts_are_bounded(monkeypatch, failure):
    calls = []

    def get(url, **kwargs):
        calls.append(kwargs["timeout"])
        if failure == "query":
            raise requests.Timeout()
        return Reply({"models": [
            {"name": "gemma4:12b", "size": 8 * GB},
            {"name": "qwen3.5:9b", "size": 6 * GB},
        ]})

    def post(url, **kwargs):
        if url.endswith("/api/generate"):
            calls.append(kwargs["timeout"])
            raise requests.Timeout()
        return chat_reply("gemma4:12b")

    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(requests, "post", post)
    assert provider("gemma4:12b").complete(system="s", user="u").content == "ok"
    assert all(0 < timeout <= 2 for timeout in calls)


def test_disabled_switch_skips_residency_http(monkeypatch):
    monkeypatch.setenv("URI_DESKTOP_OLLAMA_RESIDENCY_ENABLED", "0")
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("unexpected inventory request"))
    monkeypatch.setattr(requests, "post", lambda url, **kw: chat_reply("gemma4:12b"))
    assert provider("gemma4:12b").complete(system="s", user="u").content == "ok"


def test_remote_ollama_skips_residency_http(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("unexpected inventory request"))
    monkeypatch.setattr(requests, "post", lambda url, **kw: chat_reply("gemma4:12b"))
    assert provider("gemma4:12b", "https://remote.example").complete(system="s", user="u").content == "ok"


def test_large_size_threshold_is_configurable(monkeypatch):
    monkeypatch.setenv("URI_DESKTOP_OLLAMA_LARGE_MODEL_BYTES", str(10 * GB))
    monkeypatch.setattr(requests, "get", lambda url, **kw: Reply({"models": [
        {"name": "gemma4:12b", "size": 8 * GB},
        {"name": "qwen3.5:9b", "size": 6 * GB},
    ]}))
    urls = []
    monkeypatch.setattr(requests, "post", lambda url, **kw: urls.append(url) or chat_reply("gemma4:12b"))
    provider("gemma4:12b").complete(system="s", user="u")
    assert urls == [f"{URL}/api/chat"]


def test_non_ollama_provider_does_not_probe_or_unload(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *a, **kw: pytest.fail("unexpected Ollama request"))
    urls = []

    def post(url, **kwargs):
        urls.append(url)
        return Reply({"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(requests, "post", post)
    other = OpenAICompatibleProvider(ModelProviderConfig(base_url="http://127.0.0.1:1234/v1", model="other"))
    assert other.complete(system="s", user="u").content == "ok"
    assert urls == ["http://127.0.0.1:1234/v1/chat/completions"]
