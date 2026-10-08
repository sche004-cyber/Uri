"""C2 strict paired HTTP edge; no legacy context or private store fallback."""
from fastapi import Depends, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from uri_core.client_contracts import FRAME_LIMIT, Continuation, ControlRequest, SessionRequest, TurnRequest
from uri_core.core.client_pairing import PairingError
from uri_core.core.client_service import ClientControlError
from uri_core.core.client_state_ports import StatePortError


class ClientBodyLimit:
    """Bound bytes before FastAPI/Pydantic allocates an entire request body."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/client/v1/"):
            return await self.app(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > FRAME_LIMIT:
                response = JSONResponse(status_code=413, content={"detail": "REQUEST_LIMIT"})
                return await response(scope, receive, send)
            if not message.get("more_body", False):
                break
        delivered = False
        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()
        return await self.app(scope, replay, send)


def bearer(value):
    if not value or not value.startswith("Bearer ") or not value[7:].strip():
        raise HTTPException(401, detail="AUTHENTICATION_REQUIRED")
    return value[7:].strip()


def register_client_routes(app):
    app.add_middleware(ClientBodyLimit)
    def service(request):
        result = getattr(request.app.state, "client_service", None)
        if result is None:
            raise HTTPException(503, detail="PAIRED_COMPOSITION_REQUIRED")
        return result

    def paired(request: Request, authorization: str | None = Header(default=None),
               x_uri_client: str | None = Header(default=None)):
        raw = bearer(authorization)
        if not x_uri_client:
            raise HTTPException(401, detail="CLIENT_BINDING_REQUIRED")
        return service(request).pairings.resolve(raw, x_uri_client)

    async def bounded(request: Request):
        # Check the actual body, including clients omitting Content-Length.
        size = 0
        async for chunk in request.stream():
            size += len(chunk)
            if size > FRAME_LIMIT:
                raise HTTPException(413, detail="REQUEST_LIMIT")

    @app.exception_handler(PairingError)
    async def pairing_error(request, error):
        return JSONResponse(status_code=error.status, content={"detail": str(error)})

    @app.exception_handler(ClientControlError)
    async def control_error(request, error):
        headers = {"Retry-After": "1"} if error.status == 429 else None
        return JSONResponse(status_code=error.status, content={"detail": str(error)}, headers=headers)

    @app.exception_handler(StatePortError)
    async def state_error(request, error):
        return JSONResponse(status_code=400, content={"detail": str(error)})

    # Validation errors on this new surface never echo input bodies/credentials.
    # Legacy validation behavior is retained on the existing app.
    from fastapi.exception_handlers import request_validation_exception_handler
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        if request.url.path.startswith("/client/v1/"):
            return JSONResponse(status_code=422, content={"detail": "CLIENT_SCHEMA_INVALID"})
        return await request_validation_exception_handler(request, error)

    @app.post("/client/v1/session", dependencies=[Depends(bounded)])
    def session(body: SessionRequest, request: Request, authorization: str | None = Header(default=None),
                x_uri_pairing: str | None = Header(default=None)):
        raw = bearer(authorization)
        if not x_uri_pairing:
            raise HTTPException(401, detail="PAIRING_REQUIRED")
        return service(request).pairings.acquire(body.server_id, body.client_id, raw, x_uri_pairing)

    @app.get("/client/v1/capabilities")
    def capabilities(request: Request, identity=Depends(paired)):
        return service(request).capabilities(identity)

    @app.post("/client/v1/turns", dependencies=[Depends(bounded)])
    def start(body: TurnRequest, request: Request, identity=Depends(paired)):
        return service(request).start(body, identity)

    @app.post("/client/v1/turns/{turn_id}/continue", dependencies=[Depends(bounded)])
    def continue_turn(turn_id: str, body: Continuation, request: Request, identity=Depends(paired)):
        return service(request).continue_turn(turn_id, body, identity)

    @app.post("/client/v1/turns/{turn_id}/cancel", dependencies=[Depends(bounded)])
    def cancel(turn_id: str, body: ControlRequest, request: Request, identity=Depends(paired)):
        return service(request).cancel(turn_id, body, identity)

    def coordinator(request):
        result = getattr(request.app.state, "coordinator", None)
        if result is None:
            raise HTTPException(503, detail="CANONICAL_COMPOSITION_PENDING")
        return result

    from uri_core.core.paired_coordinator import ApprovalRequest, ClaimRequest, SettleRequest, WaitRequest

    @app.post("/client/v1/turns/{turn_id}/approval", dependencies=[Depends(bounded)])
    def approval(turn_id: str, body: ApprovalRequest, request: Request, identity=Depends(paired)):
        return coordinator(request).approve(turn_id, body, identity)

    @app.post("/client/v1/turns/{turn_id}/claim", dependencies=[Depends(bounded)])
    def claim(turn_id: str, body: ClaimRequest, request: Request, identity=Depends(paired)):
        return coordinator(request).claim(turn_id, body, identity)

    @app.post("/client/v1/turns/{turn_id}/settle", dependencies=[Depends(bounded)])
    def settle(turn_id: str, body: SettleRequest, request: Request, identity=Depends(paired)):
        return coordinator(request).settle(turn_id, body, identity)

    @app.post("/client/v1/turns/{turn_id}/wait", dependencies=[Depends(bounded)])
    def wait(turn_id: str, body: WaitRequest, request: Request, identity=Depends(paired)):
        return coordinator(request).wait(turn_id, body, identity)

    @app.get("/client/v1/turns/{turn_id}/status")
    def status(turn_id: str, request: Request, identity=Depends(paired)):
        return service(request).status(turn_id, identity)

    return paired
