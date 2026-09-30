"""Needle JSON-lines worker. Runs inside the Needle virtualenv.

Differences from the Stage-1 bridge (experimental_needle_bridge_runtime.py):
- stdin and stdout are reconfigured to UTF-8 explicitly (Stage-1 RC-9: the
  bridge wrote non-ASCII JSON in the Windows locale code page);
- agents are cached per (system, tools) key so repeated tool sets do not
  reload, and every decode reports whether it paid an agent build;
- ``reset`` is called before every decode so no state crosses cases.
"""
from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

sys.stdin.reconfigure(encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")

import needle  # noqa: E402

_agents: dict[str, object] = {}
_MAX_AGENTS = 64


def _agent(system: str, tools: list) -> tuple[object, float]:
    key = json.dumps([system, tools], sort_keys=True, ensure_ascii=False)
    if key in _agents:
        return _agents[key], 0.0
    if len(_agents) >= _MAX_AGENTS:
        k, a = next(iter(_agents.items()))
        try:
            a.close()
        finally:
            del _agents[k]
    t = time.perf_counter()
    a = needle.Needle(tools=tools, system=system, generation=3)
    _agents[key] = a
    return a, (time.perf_counter() - t) * 1000.0


def main() -> int:
    for raw in sys.stdin:
        try:
            req = json.loads(raw)
            op = req.get("op")
            if op == "ping":
                out = {"status": "ready", "package_version": getattr(needle, "__version__", None), "pid": os.getpid()}
            elif op == "decode":
                agent, build_ms = _agent(req["system"], req["tools"])
                agent.reset()
                t = time.perf_counter()
                resp = agent.complete(req["text"], max_new_tokens=int(req.get("max_new_tokens", 256)))
                out = {"status": "ok", "response": resp, "infer_ms": (time.perf_counter() - t) * 1000.0,
                       "agent_build_ms": build_ms}
            elif op == "close":
                return 0
            else:
                raise ValueError(f"unknown op {op}")
        except Exception as exc:  # reported, never swallowed
            out = {"status": "error", "detail": f"{type(exc).__name__}: {exc}"}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
