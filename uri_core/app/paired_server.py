"""C2 opt-in Core composition. Never imports the legacy server/private stores."""
from contextlib import asynccontextmanager
import asyncio

from fastapi import FastAPI, Depends

from uri_core.app.client_routes import register_client_routes
from uri_core.app.runtime_routes import register_runtime_routes
from uri_core.core.client_service import ClientService


def create_app(runtime, composition=None):
    @asynccontextmanager
    async def lifespan(app):
        runtime.catalogue_ready = bool(app.state.client_service.registry.list_capabilities())
        runtime.started = True
        if runtime.guard:
            runtime.guard.starting = False
        async def expiry_loop():
            while True:
                await asyncio.sleep(1)
                app.state.client_service.expire()
        expiry_task = asyncio.create_task(expiry_loop())
        try:
            yield
        finally:
            expiry_task.cancel()
            try:
                await expiry_task
            except asyncio.CancelledError:
                pass
            app.state.client_service.live.clear()
            runtime.started = False

    app = FastAPI(lifespan=lifespan)
    app.state.runtime_identity = runtime
    app.state.client_service = ClientService(runtime)
    if composition is not None:
        # Trusted caller supplies policy/proposer; never a request or model.
        from uri_core.core.paired_coordinator import PairedCoordinator
        coordinator = PairedCoordinator(app.state.client_service, runtime, **composition)
        app.state.client_service.coordinator = coordinator
        app.state.coordinator = coordinator
    paired = register_client_routes(app)
    register_runtime_routes(app, paired)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


def default_composition():
    """Trusted server-side default: explicit no-Brain deterministic source only.

    No native harness row is listed, so harness selections are refused with
    ADAPTER_NOT_QUALIFIED until qualification evidence is added by composition.
    """
    from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
    return {"policy": ReasoningSelectionPolicy({("server_local_model", "uri-deterministic", None)})}
