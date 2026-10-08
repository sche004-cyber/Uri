"""URIv1 Needle 3 bridge runtime (Batch A2).

Runs inside the dedicated Needle virtualenv (e.g. ``.venv-needle``), NOT
inside the main URIv1 process. Speaks newline-delimited JSON over stdio.

Decode-only, proposal-only, generic:
- It never receives or hardcodes a wire schema; the schema and system
  prompt are supplied per "decode" request by the caller (needle_decoder.py)
  so this file carries no URIv1 semantic policy of its own.
- It never calls Needle's ``run()`` execution loop, and never executes a
  Python function on Needle's behalf. Only ``complete()`` (structured
  proposal, no execution) is used.
- Agents are cached by (system, schema) so repeated decode calls in the
  same process stay warm; a different schema/system starts a new agent.

This is a fresh, minimal implementation for URIv1 -- not a reuse of
``uri_core/core/edge/adapters/ensemble.py``'s NeedleSubprocessAdapter or
``scripts/m33_2_needle_bridge.py``'s Bridge class. Those carry
tool-selection/capability-routing policy (weather/Gmail/calendar schemas,
intent-name mapping) that A2 must not inherit. Only the general shape --
a subprocess speaking JSONL over stdio to an offline Needle process -- is
reused as a pattern, reimplemented here without that policy. See the A2
report section 7 for the full reuse-vs-reimplement decision.
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict

os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import needle  # noqa: E402  (offline environment must be fixed before import)


class DecodeOnlyBridge:
    def __init__(self) -> None:
        self._agents: Dict[str, Any] = {}
        self._load_time_ms: float = 0.0

    def _agent_key(self, system: str, schema: Dict[str, Any]) -> str:
        return json.dumps({"system": system, "schema": schema}, sort_keys=True)

    def _agent(self, system: str, schema: Dict[str, Any]) -> Any:
        key = self._agent_key(system, schema)
        agent = self._agents.get(key)
        if agent is None:
            started = time.perf_counter()
            agent = needle.Needle(tools=[schema], system=system, generation=3)
            self._load_time_ms = (time.perf_counter() - started) * 1000.0
            self._agents[key] = agent
        return agent

    def decode(self, request: Dict[str, Any]) -> Dict[str, Any]:
        system = request.get("system")
        schema = request.get("schema")
        text = request.get("text", "")
        max_new_tokens = int(request.get("max_new_tokens", 300))
        if not isinstance(system, str) or not isinstance(schema, dict):
            raise ValueError("decode request requires string 'system' and object 'schema'")
        agent = self._agent(system, schema)
        started = time.perf_counter()
        response = agent.complete(str(text), max_new_tokens=max_new_tokens)
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        response["_bridge_latency_ms"] = elapsed_ms
        response["_bridge_load_time_ms"] = self._load_time_ms
        return response

    def reset(self) -> None:
        for agent in self._agents.values():
            if hasattr(agent, "reset"):
                try:
                    agent.reset()
                except Exception:
                    pass

    def close(self) -> None:
        for agent in self._agents.values():
            agent.close()


def _write(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def main() -> int:
    bridge = DecodeOnlyBridge()
    try:
        for raw in sys.stdin:
            try:
                request = json.loads(raw)
                operation = request.get("operation")
                if operation == "ping":
                    _write(
                        {
                            "status": "ready",
                            "package": "cactus-needle",
                            "package_version": getattr(needle, "__version__", None),
                            "generation": 3,
                            "telemetry_disabled": os.environ.get("NEEDLE_TELEMETRY") == "0",
                            "offline_mode": os.environ.get("HF_HUB_OFFLINE") == "1",
                        }
                    )
                elif operation == "decode":
                    _write({"status": "ok", "response": bridge.decode(request)})
                elif operation == "reset":
                    bridge.reset()
                    _write({"status": "ok", "operation": "reset"})
                elif operation == "close":
                    return 0
                else:
                    raise ValueError("unknown bridge operation")
            except Exception as exc:  # deliberately broad: surface as a bridge error, never crash silently
                _write({"status": "error", "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        bridge.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
