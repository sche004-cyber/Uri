import json

import pytest

from uri_core.core.model_providers.base import (ProviderResponseError, ProviderTimeoutError,
                                                ProviderUnavailableError)
from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import core_provider as CP
from uri_operational_intelligence.runtime_v1 import Readiness, load_config
from tests.oi.fake_llama import FakeLlama, free_port


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def test_provider_is_fast_tier_json_grammar(fake):
    fake.scripts.append({"json": '{"mode": "conversation"}', "finish": "stop"})
    p = CP.RuntimeV1Provider(load_config(), BC.BrainClient(fake.url))
    r = p.complete(system="S", user="U", max_tokens=500)
    body = fake.requests[-1]
    assert r.content == '{"mode": "conversation"}' and r.provider == CP.PROVIDER_ID
    assert body["response_format"] == {"type": "json_object"} and body["chat_template_kwargs"] == {"enable_thinking": False}
    assert body["temperature"] == 0.0 and body["max_tokens"] == 500 and "thinking_budget_tokens" not in body
    assert p.calls[-1]["status"] == "COMPLETE"


def test_provider_failures_raise_typed_errors_never_text(fake):
    cfg = load_config()
    fake.scripts.append({"json": '{"mode":', "finish": "length"})
    with pytest.raises(ProviderResponseError):
        CP.RuntimeV1Provider(cfg, BC.BrainClient(fake.url)).complete(system="S", user="U")
    fake.scripts.append({"status": 500})
    with pytest.raises(ProviderUnavailableError):
        CP.RuntimeV1Provider(cfg, BC.BrainClient(fake.url)).complete(system="S", user="U")
    with pytest.raises(ProviderUnavailableError):
        CP.RuntimeV1Provider(cfg, BC.BrainClient("http://127.0.0.1:%d" % free_port())).complete(system="S", user="U")
    fake.scripts.append({"json": "{}", "first_delay": 2.0})
    with pytest.raises(ProviderTimeoutError):
        CP.RuntimeV1Provider(cfg, BC.BrainClient(fake.url), timeout_s=0.5).complete(system="S", user="U")


def test_describe_never_raises_and_reports_readiness(fake):
    cfg = load_config()
    p = CP.RuntimeV1Provider(cfg, BC.BrainClient(fake.url), readiness=lambda: Readiness("READY", fake.url))
    d = p.describe()
    assert d.available and d.location == "local" and d.context_window == 32768
    boom = CP.RuntimeV1Provider(cfg, BC.BrainClient(fake.url), readiness=lambda: 1 / 0)
    assert boom.describe().available is False


def test_snap_and_b1_routing():
    assert CP.snap_to_user_span("ext is 4412", "My ext is 4412.") == "ext is 4412."
    assert CP.snap_to_user_span("not there", "My ext is 4412.") == "not there"
    assert CP.snap_to_user_span(None, "x") is None


def test_selection_row_is_explicit_server_local_model():
    cfg = load_config()
    assert CP.selection_row(cfg) == ("server_local_model", "llamacpp-runtime-v1", "qwen3.6-35b-a3b-ud-iq3_s")
