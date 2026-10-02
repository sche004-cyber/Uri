"""The per-user Gmail registry must read the same token path as OAuth connect."""

from pathlib import Path
from uuid import uuid4
from unittest.mock import Mock

from uri_core.app import server
from uri_core.core import google_auth_common
from uri_core.services import gmail_service


def test_gmail_registry_keeps_user_token_path_after_lifecycle_refresh(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("URI_EXTERNAL_CREDENTIAL_SECRET", "test-only-credential-secret")
    monkeypatch.setenv("URI_PROVIDER_KEY_SECRET", "test-only-provider-secret")
    user_id = str(uuid4())
    other_id = str(uuid4())
    token_root = tmp_path / "tokens"
    monkeypatch.setattr(server, "_USER_STATE_ROOT", str(tmp_path / "state"))
    monkeypatch.setattr(
        google_auth_common,
        "resolve_google_token_path",
        lambda scoped_user=None: str(token_root / (scoped_user or "install") / "token.json"),
    )

    context = server._build_user_context(user_id)
    expected = token_root / user_id / "token.json"
    other = token_root / other_id / "token.json"
    original_exists = Path.exists
    monkeypatch.setattr(
        Path,
        "exists",
        lambda path: path == expected or original_exists(path),
    )
    credential = Mock()
    credential.has_scopes.return_value = True
    loaded_paths = []

    def load_credentials(*, token_path, **_kwargs):
        loaded_paths.append(Path(token_path))
        return credential

    monkeypatch.setattr(gmail_service, "load_usable_credentials", load_credentials)
    monkeypatch.setattr(gmail_service, "build", lambda *_args, **_kwargs: object())

    for registry in (
        context.orchestrator.multi_action_dispatch.registry,
        server.refresh_user_external_lifecycle(user_id, context).registry,
    ):
        gmail = registry.get_capability("Gmail")
        assert gmail.gmail_service.user_id == user_id
        assert gmail.gmail_service.token_path == expected
        assert gmail.gmail_service.token_path != other
        assert gmail._availability()["available"] is True

    assert loaded_paths
    assert all(path == expected for path in loaded_paths)
