"""The Phase 2 server profile's refusal diagnostic logs codes and route shapes only (review round 5, LOG-1)."""
import asyncio

from uri_supervisor_bridge.refusal_log import KNOWN_CODES, RefusalLog, in_scope, refusal_line, route_shape


def _run(app, scope):
    sent = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)
    asyncio.run(app(scope, receive, send))
    return sent


def _app(status, body):
    async def app(scope, receive, send):
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": body, "more_body": False})
    return app


def test_route_shape_never_echoes_ids_or_queries():
    assert route_shape("/client/v1/turns/123e4567-e89b-42d3-a456-426614174000/approval") == "/client/v1/turns/{id}/approval"
    assert route_shape("/client/v1/turns/Bearer%20sk-secret/status?token=abc") == "/client/v1/turns/{id}/status"
    assert route_shape("/client/v1/" + "x" * 500) == "/client/v1/{id}"
    assert route_shape(None) == "/{invalid}"


def test_refusal_line_logs_only_identifier_codes():
    assert refusal_line("POST", "/client/v1/turns/abc/approval", 403, b'{"detail": "SESSION_SCOPE"}') == \
        "CLIENT_REFUSAL POST /client/v1/turns/{id}/approval 403 SESSION_SCOPE"
    assert refusal_line("POST", "/client/v1/session", 401, b'{"detail": "Bearer sk-live-secret-token"}').endswith(" 401 OTHER_CODE")
    assert refusal_line("GET", "/client/v1/capabilities", 500, b"<html>Bearer abc</html>").endswith(" 500 NON_JSON_BODY")
    # round 6, LOG-1R: an UPPERCASE free string is still not a code; only the frozen server's known codes are echoed
    for canary in ("SK_LIVE_SECRET_TOKEN", "BEARER_ABC", "X", "SESSION_SCOPE_EXTRA"):
        assert refusal_line("POST", "/client/v1/session", 403, ('{"detail": "%s"}' % canary).encode()).endswith(" 403 OTHER_CODE"), canary
    assert "SESSION_SCOPE" in KNOWN_CODES and "REQUEST_BINDING" in KNOWN_CODES and "CLIENT_BINDING" in KNOWN_CODES
    assert refusal_line("P O S T", "/client/v1/session", 403, b'{"detail": "X"}').startswith("CLIENT_REFUSAL OTHER_METHOD ")
    assert refusal_line("BEARERX", "/client/v1/session", 403, b'{"detail": "X"}').startswith("CLIENT_REFUSAL OTHER_METHOD ")
    assert refusal_line("POST", "/client/v1/session", "9999", b"{}").split()[3] == "0"
    line = refusal_line("POST", "/client/v1/turns/Bearer sk-1/approval?auth=sk-2", 403, b'{"detail": "sk-3 secret"}')
    assert "sk-" not in line and "secret" not in line and "auth" not in line


def test_wrapper_logs_refusals_only_and_passes_responses_through():
    lines = []
    ok = RefusalLog(_app(200, b'{"detail": "Bearer must-never-appear"}'), sink=lines.append)
    sent = _run(ok, {"type": "http", "method": "POST", "path": "/client/v1/turns", "query_string": b"x=Bearer+y"})
    assert lines == [] and sent[0]["status"] == 200 and sent[1]["body"] == b'{"detail": "Bearer must-never-appear"}'
    bad = RefusalLog(_app(403, b'{"detail": "REQUEST_BINDING"}'), sink=lines.append)
    _run(bad, {"type": "http", "method": "POST", "path": "/client/v1/turns/deadbeef/claim", "query_string": b"token=abc"})
    assert lines == ["CLIENT_REFUSAL POST /client/v1/turns/{id}/claim 403 REQUEST_BINDING"]
    other = RefusalLog(_app(403, b'{"detail": "SESSION_SCOPE"}'), sink=lines.append)
    _run(other, {"type": "http", "method": "GET", "path": "/runtime/identity"})     # outside /client/v1: untouched
    _run(other, {"type": "http", "method": "GET", "path": "/client/v1evil/x"})      # round 6, LOG-2: not below /client/v1
    assert len(lines) == 1
    assert in_scope("/client/v1") and in_scope("/client/v1/turns") and not in_scope("/client/v1evil") and not in_scope("/client/v10/x") and not in_scope(None)


def test_known_codes_are_exactly_the_frozen_servers_refusal_codes():
    import re
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    found = set()
    for f in ("uri_core/app/client_routes.py", "uri_core/core/client_service.py", "uri_core/core/client_pairing.py",
              "uri_core/core/client_execution_control.py", "uri_core/core/client_state_ports.py",
              "uri_core/core/paired_coordinator.py"):
        s = (root / f).read_text(encoding="utf-8")
        found |= set(re.findall(r'(?:ClientControlError|PairingError|ExecutionControlError|StatePortError)\("([A-Z][A-Z0-9_]+)"', s))
        found |= set(re.findall(r'detail="([A-Z][A-Z0-9_]+)"', s))
        found |= set(re.findall(r'content=\{"detail": "([A-Z][A-Z0-9_]+)"', s))
    assert set(KNOWN_CODES) == found, (set(KNOWN_CODES) ^ found)
