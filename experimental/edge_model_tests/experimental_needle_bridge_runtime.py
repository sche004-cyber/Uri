"""Experimental Needle Bridge with O(1) stateless reset and zero agent accumulation.
Lives strictly inside experimental/edge_model_tests/.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict

os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import needle

class ExperimentalDecodeBridge:
    def __init__(self) -> None:
        self._current_agent: Any = None
        self._current_key: str = ""
        self._load_time_ms: float = 0.0

    def _agent_key(self, system: str, schema: Dict[str, Any]) -> str:
        return json.dumps({"system": system, "schema": schema}, sort_keys=True)

    def _agent(self, system: str, schema: Dict[str, Any]) -> Any:
        key = self._agent_key(system, schema)
        if self._current_key != key or self._current_agent is None:
            started = time.perf_counter()
            self._current_agent = needle.Needle(tools=[schema], system=system, generation=3)
            self._load_time_ms = (time.perf_counter() - started) * 1000.0
            self._current_key = key
        return self._current_agent

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
        # Reset ONLY the active agent, never accumulating or looping over historical agents
        if self._current_agent is not None and hasattr(self._current_agent, "reset"):
            try:
                self._current_agent.reset()
            except Exception:
                pass

    def close(self) -> None:
        if self._current_agent is not None and hasattr(self._current_agent, "close"):
            self._current_agent.close()

def _write(payload: Dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()

def main() -> int:
    bridge = ExperimentalDecodeBridge()
    try:
        for raw in sys.stdin:
            try:
                request = json.loads(raw)
                op = request.get("operation")
                if op == "ping":
                    _write({
                        "status": "ready",
                        "package": "cactus-needle",
                        "package_version": getattr(needle, "__version__", None),
                        "generation": 3,
                        "telemetry_disabled": True,
                        "offline_mode": True,
                    })
                elif op == "decode":
                    _write({"status": "ok", "response": bridge.decode(request)})
                elif op == "reset":
                    bridge.reset()
                    _write({"status": "ok", "operation": "reset"})
                elif op == "close":
                    return 0
                else:
                    raise ValueError(f"unknown bridge operation: {op}")
            except Exception as exc:
                _write({"status": "error", "detail": f"{type(exc).__name__}: {exc}"})
    finally:
        bridge.close()
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
