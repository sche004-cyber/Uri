"""Development HTTP/SSE surface for Operational Intelligence (loopback only, bearer token, no CORS).

    .venv\\Scripts\\python.exe -m uri_operational_intelligence.server --port 18471

Endpoints (contract: docs/operational_intelligence/OI_UI_INTEGRATION_CONTRACT.md):
  GET  /oi/v1/brain/status                 readiness of Runtime v1 (never starts it)
  POST /oi/v1/turns                        {"text", "session_id", "depth"?, "turn_id"?} -> text/event-stream of events
  POST /oi/v1/turns/{turn_id}/cancel       cancel a running turn
  GET  /oi/v1/simulate/{scenario}          text/event-stream of a simulated sequence (no runtime needed)

Not a production service and not wired into the URI server or client. Core is attached only when a CoreGateway is
supplied by the caller (tests, a materialized runtime); without one, action requests are refused honestly
(CORE_UNAVAILABLE) and nothing is executed.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import queue
import secrets
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import brain_client as BC
from . import runtime_v1 as R
from .events import EventSink, simulate
from .orchestrator import Orchestrator
from .task_ledger import TaskLedger


class TurnBody(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    session_id: str = Field(min_length=1, max_length=128)
    depth: str = "auto"
    turn_id: str | None = Field(default=None, max_length=128)


def create_app(*, token: str, orchestrator: Orchestrator, manager: R.RuntimeManager | None = None):
    perf = orchestrator.perf
    app = FastAPI()

    def auth(request: Request):
        if not secrets.compare_digest(request.headers.get("authorization", ""), "Bearer " + token):
            raise HTTPException(401, "UNAUTHORIZED")

    @app.get("/oi/v1/brain/status")
    def status(request: Request):
        auth(request)
        if manager is None:
            return {"state": "NOT_CONFIGURED"}
        r = manager.status().to_dict()
        if perf is not None and r["state"] == R.READY:
            r["performance"] = perf.assess(pid=r["pid"], sample=True)
            if r["performance"]["state"] == "DEGRADED":
                r["state"] = "DEGRADED"
        return r

    @app.post("/oi/v1/turns")
    def turn(body: TurnBody, request: Request):
        auth(request)
        if body.depth not in ("auto", "fast", "normal", "deep"):
            raise HTTPException(422, "UNKNOWN_DEPTH")
        q: queue.Queue = queue.Queue()
        sink = EventSink(callback=q.put)
        turn_id = body.turn_id or secrets.token_hex(16)

        def run():
            try:
                orchestrator.handle_turn(body.text, body.session_id, depth=body.depth, sink=sink, turn_id=turn_id)
            except Exception as exc:     # never leave the stream hanging; report, never guess
                sink.emit(turn_id, "error", code="OI_INTERNAL", message=type(exc).__name__, recoverable=True,
                          recovery_options=["retry"])
                sink.emit(turn_id, "turn.finished", status="error", route="unknown", total_s=0.0)
            finally:
                q.put(None)

        threading.Thread(target=run, daemon=True).start()

        async def stream():
            finished = False
            try:
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        ev = await asyncio.to_thread(q.get, True, 0.25)
                    except queue.Empty:
                        continue
                    if ev is None:
                        finished = True
                        return
                    yield "data: " + json.dumps(ev, ensure_ascii=False) + "\n\n"
            finally:
                if not finished:
                    # Reader went away: stop inference instead of generating into a queue nobody reads.
                    orchestrator.cancel(turn_id, "client_disconnected")

        return StreamingResponse(stream(), media_type="text/event-stream", headers={"X-OI-Turn": turn_id})

    @app.post("/oi/v1/turns/{turn_id}/cancel")
    def cancel(turn_id: str, request: Request):
        auth(request)
        return {"cancelled": orchestrator.cancel(turn_id)}

    @app.get("/oi/v1/simulate/{scenario}")
    def sim(scenario: str, request: Request):
        auth(request)
        try:
            events = simulate(scenario)
        except ValueError:
            raise HTTPException(404, "UNKNOWN_SCENARIO") from None
        return StreamingResponse(("data: " + json.dumps(e) + "\n\n" for e in events), media_type="text/event-stream")

    return app


def main(argv=None):
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=18471)
    a = ap.parse_args(argv)
    if a.port in (8000, 8018, 8021, 11434, 1234, 18470):
        raise SystemExit("PORT_RESERVED")
    cfg = R.load_config()
    mgr = R.RuntimeManager(cfg)
    client = BC.BrainClient(R.base_url(cfg))
    from .core_provider import selection
    from .perf_monitor import PerfMonitor
    perf = PerfMonitor()
    r = mgr.status()
    if r.state == R.READY:
        perf.set_baseline(r.pid)   # attached instance: baseline = first observation (weaker than a fresh-start baseline)
    ledger = TaskLedger(R.DEFAULT_STATE.parent / "tasks")
    ledger.acquire_owner()        # refuses to start if another process owns (and may be running) these tasks
    print("ledger recovery:", ledger.recover(), flush=True)    # restart rules before serving anything
    orch = Orchestrator(client=client, core=None, brain_selection=selection(cfg), ledger=ledger,
                        capability_ids={"remember_fact", "external_harness_task"}, readiness=mgr.status, perf=perf)
    token = secrets.token_urlsafe(32)
    tok_file = R.DEFAULT_STATE / "oi_server.token"
    tok_file.parent.mkdir(parents=True, exist_ok=True)
    tok_file.write_text(token, encoding="utf-8")
    print("token file:", tok_file, flush=True)
    uvicorn.run(create_app(token=token, orchestrator=orch, manager=mgr), host="127.0.0.1", port=a.port, log_level="warning")


if __name__ == "__main__":
    main()
