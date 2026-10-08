"""Phase 2 server PROFILE diagnostic (UI/operations slice, review rounds 3-5: VAL-1, LOG-1).

An intermittent HTTP 403 on a `/client/v1` request could not be attributed because the frozen client transport keeps
the status only. This pure-ASGI wrapper logs, for `/client/v1` responses with status >= 400 ONLY, a line of the form

    CLIENT_REFUSAL <METHOD> <route shape> <status> <CODE>

where the route shape is the request path with every segment that is not a known literal replaced by `{id}` and the
CODE is the JSON body's `detail` only when it is one of the frozen server's known refusal codes (`KNOWN_CODES`); any
other detail is logged as `OTHER_CODE`, and any method other than GET/POST as `OTHER_METHOD`. Query strings, request headers, request bodies, 2xx bodies and free text are
never read into the log (review round 5, LOG-1: an earlier version printed the raw path and detail).
"""
from __future__ import annotations

import json
import sys

# Allow-list (review round 6, LOG-1R): exactly the refusal codes the frozen paired server emits on /client/v1, extracted
# verbatim from uri_core/app/client_routes.py, core/client_service.py, core/client_pairing.py,
# core/client_execution_control.py, core/client_state_ports.py and core/paired_coordinator.py (ClientControlError / PairingError /
# ExecutionControlError / StatePortError / HTTPException details). Anything else, uppercase or not, logs as OTHER_CODE.
KNOWN_CODES = frozenset("""
APPROVAL_DIGEST_MISMATCH AUTHENTICATION_REQUIRED BASE_VERSION_REQUIRED CANONICAL_COMPOSITION_PENDING
CLAIM_ALREADY_SETTLED_OR_UNCERTAIN CLAIM_SCHEMA CLIENT_ALREADY_PAIRED CLIENT_BINDING CLIENT_BINDING_REQUIRED
CLIENT_INVALID CLIENT_SCHEMA_INVALID CLIENT_UNKNOWN CONTEXT_REQUIRED_AFTER_RESTART CONTEXT_SCOPE
CONTROL_STORE_UNAVAILABLE DUPLICATE_ARGUMENT EXECUTION_AUTHORITY_UNAVAILABLE EXECUTION_CONTROL_UNAVAILABLE
EXECUTION_SCOPE EXECUTION_TERMINAL EXECUTION_VERSION_CONFLICT IDEMPOTENCY_CONFLICT METHOD_NOT_ALLOWED
OPERATION_ALREADY_PREPARED PAIRED_COMPOSITION_REQUIRED PAIRING_INVALID PAIRING_REQUIRED PAIRING_REVOKED
PAIRING_STORE_UNAVAILABLE PREVIOUS_PROJECTION_DIGEST PRINCIPAL_BINDING PRINCIPAL_INVALID PRINCIPAL_SCOPE
PRINCIPAL_SESSION_INVALID PROVIDER_CHECKPOINT_SCHEMA RECEIPT_CANCEL_AFTER_DISPATCH RECEIPT_CONFLICT
RECEIPT_SCOPE RECEIPT_VERIFIER_UNAVAILABLE RECEIPT_WITHOUT_CLAIM REQUEST_BINDING REQUEST_LIMIT SERVER_BINDING
SESSION_EXPIRED SESSION_INVALID SESSION_REPLACEMENT_SCOPE SESSION_SCOPE TICKET_CLOCK_OR_GENERATION
TICKET_EXPIRED_OR_RESTARTED TICKET_REFUSED TICKET_UNKNOWN TURN_CAPACITY TURN_NOT_AWAITING_APPROVAL
TURN_NOT_CLAIMABLE TURN_NOT_CONTINUABLE TURN_NOT_SETTLEABLE TURN_NOT_WAITABLE TURN_SCOPE TURN_TERMINAL
TURN_UNKNOWN VERSION_CONFLICT
""".split())
KNOWN_METHODS = frozenset({"GET", "POST"})
_LITERALS = frozenset({"client", "v1", "turns", "session", "capabilities", "approval", "claim", "settle", "wait",
                       "continue", "status", "cancel"})


def route_shape(path) -> str:
    """`/client/v1/turns/<uuid>/approval` -> `/client/v1/turns/{id}/approval`; never echoes a non-literal segment."""
    if not isinstance(path, str):
        return "/{invalid}"
    parts = [p for p in path.split("?", 1)[0].split("/") if p]
    out = [p if p in _LITERALS else "{id}" for p in parts][:8]
    return "/" + "/".join(out)


def refusal_code(body: bytes) -> str:
    try:
        detail = json.loads(body).get("detail")
    except Exception:  # noqa: BLE001  (non-JSON or non-object body)
        return "NON_JSON_BODY"
    return detail if isinstance(detail, str) and detail in KNOWN_CODES else "OTHER_CODE"


def in_scope(path) -> bool:
    """Exactly `/client/v1` or a path below it (review round 6, LOG-2: `/client/v1evil` is outside)."""
    return isinstance(path, str) and (path == "/client/v1" or path.startswith("/client/v1/"))


def refusal_line(method, path, status, body) -> str:
    m = method if isinstance(method, str) and method in KNOWN_METHODS else "OTHER_METHOD"
    try:
        st = int(status) if 100 <= int(status) <= 599 else 0
    except (TypeError, ValueError):
        st = 0
    return f"CLIENT_REFUSAL {m} {route_shape(path)} {st} {refusal_code(body)}"


class RefusalLog:
    def __init__(self, app, sink=None):
        self.app = app
        self.sink = sink or (lambda line: print(line, file=sys.stderr, flush=True))

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or not in_scope(scope.get("path")):
            return await self.app(scope, receive, send)
        status, chunks = [None], []

        async def send_wrapped(message):
            if message["type"] == "http.response.start":
                status[0] = message.get("status")
            elif message["type"] == "http.response.body" and status[0] is not None and status[0] >= 400:
                chunks.append(message.get("body", b""))
                if not message.get("more_body"):
                    self.sink(refusal_line(scope.get("method"), scope.get("path"), status[0], b"".join(chunks)[:4096]))
            await send(message)
        await self.app(scope, receive, send_wrapped)
