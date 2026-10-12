"""C1 identity is public; readiness uses existing strict principal enforcement."""
from fastapi import Depends, HTTPException, Query, Request
from uri_core.core.runtime_identity import RuntimeIdentityError


def register_runtime_routes(app, authenticated_principal):

    def identity(request):
        runtime=getattr(request.app.state,"runtime_identity",None)
        if runtime is None:
            raise HTTPException(503,detail="RUNTIME_MANIFEST_REQUIRED")
        return runtime

    @app.get("/runtime/identity")
    def public_identity(request: Request, nonce: str | None=Query(default=None)):
        try:
            return identity(request).public(nonce)
        except RuntimeIdentityError:
            # FastAPI's automatic 422 includes the supplied value. Do not echo
            # arbitrary input (potentially a mistakenly supplied credential).
            raise HTTPException(400,detail="NONCE_INVALID") from None

    @app.get("/runtime/status")
    def runtime_status(request: Request, principal=Depends(authenticated_principal)):
        return identity(request).status()
