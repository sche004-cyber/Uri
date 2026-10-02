"""Focused verification coverage for LM Studio's dynamic model inventory."""

import secrets
from unittest.mock import MagicMock, patch

import pytest

from uri_core.app import server
from uri_core.core.provider_registry import CATALOGUE_BY_ID

TEST_KEY = secrets.token_urlsafe(24)


@pytest.fixture(autouse=True)
def clear_verified_models():
    server._verified_models_cache.clear()
    yield
    server._verified_models_cache.clear()


def _verify(response, *, base_url="http://localhost:1234/v1", failed_models=()):
    key_store = MagicMock()
    key_store.has_key.return_value = True
    key_store.get_key_for_use.return_value = TEST_KEY
    config_store = MagicMock()
    config_store.get_provider_config.return_value = {"base_url": base_url}
    provider = MagicMock()
    provider.complete.side_effect = lambda **kwargs: (
        (_ for _ in ()).throw(RuntimeError("probe failed"))
        if provider._config.model in failed_models else MagicMock()
    )

    def make_provider(config, api_key):
        assert api_key == TEST_KEY
        provider._config = config
        return provider

    with patch("uri_core.core.provider_keys.ProviderKeyStore", return_value=key_store), \
            patch("uri_core.core.provider_registry.ProviderConfigStore", return_value=config_store), \
            patch("uri_core.core.model_providers.OpenAICompatibleProvider", side_effect=make_provider), \
            patch("requests.get", return_value=response) as get:
        result = server.verify_provider("lm_studio", user_id="test-user")
    return result, get, provider


def _response(status, ids=()):
    response = MagicMock()
    response.status_code = status
    response.ok = status == 200
    response.json.return_value = {"data": [{"id": model} for model in ids]}
    return response


def test_discovery_uses_stored_bearer_key_and_lists_verified_models():
    result, get, probe = _verify(_response(200, ["loaded-model"]))
    assert result["verified_models"] == ["loaded-model"]
    get.assert_called_once_with(
        "http://localhost:1234/v1/models",
        headers={"Authorization": f"Bearer {TEST_KEY}"}, timeout=5.0,
        allow_redirects=False,
    )
    assert probe.complete.call_args.kwargs["max_tokens"] == 1
    assert server._verified_models_for("test-user", "lm_studio") == ["loaded-model"]

    with patch("uri_core.core.provider_registry.PROVIDER_CATALOGUE", [CATALOGUE_BY_ID["lm_studio"]]), \
            patch("uri_core.core.provider_keys.ProviderKeyStore") as keys, \
            patch("uri_core.core.provider_registry.ProviderConfigStore") as configs, \
            patch("uri_core.core.model_providers.OpenAICompatibleProvider") as provider, \
            patch.object(server, "_active_brain_for_user", return_value={"is_configured": False, "provider_id": None, "model": None}):
        keys.return_value.has_key.return_value = True
        keys.return_value.describe_key.return_value = {"last_four": "0000"}
        configs.return_value.get_provider_config.return_value = {}
        provider.return_value.describe.return_value.available = True
        listing = server.list_providers(user_id="test-user")
    assert listing["providers"][0]["models"] == [{
        "model_id": "loaded-model", "display_name": "loaded-model",
        "context_tokens": None, "verified": True,
    }]


@pytest.mark.parametrize("status", [401, 403])
def test_rejected_key_has_safe_error(status):
    result, _, probe = _verify(_response(status))
    assert result["verified"] is False
    assert "key was rejected" in result["error"]
    assert TEST_KEY not in str(result)
    probe.complete.assert_not_called()


def test_empty_inventory_reports_no_loaded_model():
    result, _, probe = _verify(_response(200))
    assert result["error"] == "No model is loaded in LM Studio."
    probe.complete.assert_not_called()


def test_only_successful_probes_are_cached():
    result, _, probe = _verify(_response(200, ["bad", "good"]), failed_models={"bad"})
    assert probe.complete.call_count == 2
    assert result["verified_models"] == ["good"]
    assert server._verified_models_for("test-user", "lm_studio") == ["good"]


def test_non_loopback_url_skips_discovery():
    result, get, _ = _verify(_response(200, ["remote"]), base_url="http://example.com/v1")
    get.assert_not_called()
    assert result["verified"] is False
