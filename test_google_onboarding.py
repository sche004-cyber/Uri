"""Offline checks for desktop Google onboarding."""

import io
import os
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

os.environ.setdefault("URI_EXTERNAL_CREDENTIAL_SECRET", "test-external-secret")
os.environ.setdefault("URI_PROVIDER_KEY_SECRET", "test-provider-secret")

from starlette.requests import Request

from uri_core.app import server
from uri_core.services.google_errors import classify_google_error


def _request():
    return Request({"type": "http", "client": ("127.0.0.1", 1234), "headers": []})


def _principal():
    return SimpleNamespace(user_id="test-user")


def test_error_instructions():
    disabled = classify_google_error("Gmail API has not been used in project 12345 before or it is disabled: accessNotConfigured")
    assert disabled["kind"] == "api_disabled"
    assert "project=12345" in disabled["message"]
    assert classify_google_error("access_denied")["kind"] == "test_user"
    assert classify_google_error("invalid_grant")["kind"] == "sign_in_again"
    assert "token" not in classify_google_error("secret token random failure")["message"]


def test_drive_actions_surface_setup_instructions():
    from uri_core.tools.drive_search import DriveSearchTool
    from uri_core.tools.drive_upload import DriveUploadTool

    service = SimpleNamespace(
        search_drive=lambda query: {"success": False, "reason": "accessNotConfigured project 12345"},
        upload_file=lambda *args: {"success": False, "reason": "invalid_grant"},
    )
    searched = DriveSearchTool(drive_service=service).execute(request_text="report")
    assert "drive.googleapis.com?project=12345" in searched["message"]
    record = SimpleNamespace(file_id="test", filename="report.txt", media_type="text/plain")
    store = SimpleNamespace(list_for_session=lambda _: [record], path_for=lambda _: Path(__file__))
    uploaded = DriveUploadTool(drive_service=service, file_store=store).generate(session_id="test-session")
    assert "Sign in with Google again" in uploaded["message"]


def test_authorize_hands_url_to_client_and_can_cancel(monkeypatch):
    entered = threading.Event()

    def fake_connect(self, on_auth_url=None, cancel_event=None):
        on_auth_url("https://accounts.google.com/o/oauth2/v2/auth?state=test")
        entered.set()
        cancel_event.wait(2)
        return {"success": False, "reason": "cancelled"}

    monkeypatch.setattr("uri_core.services.gmail_service.GmailService.connect", fake_connect)
    monkeypatch.setattr("uri_core.services.gmail_service.GmailService.__init__", lambda self, user_id=None: None)
    original_exists = os.path.exists
    monkeypatch.setattr(server.os.path, "exists", lambda path: True if str(path).endswith("credentials.json") else original_exists(path))
    monkeypatch.setattr(server, "_connection_status_for_user", lambda _: [])
    result = server.authorize_connection("gmail", _request(), _principal())
    assert entered.is_set(), result
    assert result["started"] is True
    assert result["auth_url"].startswith("https://accounts.google.com/")
    assert server.cancel_google_connection(_request(), _principal()) == {"cancelled": True}
    assert server._google_auth_flow_state["auth_url"] is None
    restarted = server.authorize_connection("drive", _request(), _principal())
    assert restarted["started"] is True
    assert restarted["auth_url"] == result["auth_url"]
    server.cancel_google_connection(_request(), _principal())


def test_service_publishes_url_before_callback_and_fetch(monkeypatch):
    from uri_core.services import gmail_service as module

    events = []
    flow = SimpleNamespace(
        redirect_uri=None,
        credentials=SimpleNamespace(to_json=lambda: "{}"),
        authorization_url=lambda: ("https://accounts.google.com/auth?state=abc", "abc"),
        fetch_token=lambda **kwargs: events.append(("fetch", kwargs["authorization_response"])),
    )
    monkeypatch.setattr(module.InstalledAppFlow, "from_client_secrets_file", lambda *args: flow)

    class Server:
        server_port = 12345
        timeout = None

        def __init__(self, app):
            self.app = app

        def handle_request(self):
            assert events == [("url", "https://accounts.google.com/auth?state=abc")]
            self.app.last_request_uri = "http://127.0.0.1:12345/?code=opaque&state=abc"

        def server_close(self):
            pass

    monkeypatch.setattr(module.wsgiref.simple_server, "make_server", lambda host, port, app, **kwargs: Server(app))
    monkeypatch.setattr(module, "build", lambda *args, **kwargs: object())
    service = module.GmailService(token_path=Path("test_token_nonexistent.json"), credentials_path=Path(__file__))
    monkeypatch.setattr(module, "open", lambda *args, **kwargs: io.StringIO(), raising=False)
    result = service.connect(on_auth_url=lambda url: events.append(("url", url)))
    assert result["success"] is True
    assert flow.redirect_uri == "http://127.0.0.1:12345/"
    assert events[1][0] == "fetch"


def test_setup_reports_missing_credentials_and_unknown_apis(monkeypatch):
    from uri_core.services.gmail_service import GmailService

    def fake_init(self, user_id=None):
        self.credentials_path = MagicMock()
        self.credentials_path.is_file.return_value = False
        self.token_path = MagicMock()
        self.token_path.is_file.return_value = False
        self.SCOPES = ["scope"]

    monkeypatch.setattr(GmailService, "__init__", fake_init)
    result = server.google_setup(_principal())
    steps = {step["id"]: step for step in result["steps"]}
    assert list(steps) == ["client_secret", "signed_in", "gmail_api", "drive_api", "sheets_api", "docs_api", "slides_api", "forms_api"]
    assert steps["client_secret"]["status"] == "action_required"
    assert steps["gmail_api"]["status"] == "unknown"
    assert steps["forms_api"]["optional"] is True


def test_setup_classifies_disabled_api(monkeypatch):
    from uri_core.services.gmail_service import GmailService
    import uri_core.core.google_auth_common as common
    import googleapiclient.discovery as discovery

    def fake_init(self, user_id=None):
        self.credentials_path = MagicMock()
        self.credentials_path.is_file.return_value = True
        self.token_path = MagicMock()
        self.token_path.is_file.return_value = True
        self.SCOPES = ["scope"]

    monkeypatch.setattr(GmailService, "__init__", fake_init)
    monkeypatch.setattr(common, "load_usable_credentials", lambda **_: SimpleNamespace(valid=True, has_scopes=lambda _: True))
    client = MagicMock()
    client.users().labels().list().execute.side_effect = RuntimeError("accessNotConfigured project 9876")
    monkeypatch.setattr(discovery, "build", lambda *args, **kwargs: client)
    result = server.google_setup(_principal())
    gmail = result["steps"][2]
    assert gmail["status"] == "action_required"
    assert "project=9876" in gmail["help_url"]
