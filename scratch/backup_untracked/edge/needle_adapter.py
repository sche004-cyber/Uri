"""M35 URIv1 Batch A2.8D — Dedicated Needle 3 Subprocess Bridge Adapter.

Runs inside the dedicated Needle virtualenv (.venv-needle) via subprocess JSONL stdio.
Keeps Needle 3 resident in memory across benchmark calls for fast execution.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from uri_v1.edge.contracts import SecondBrainProposal


_BRIDGE_SCRIPT = """
import json
import os
import sys
import time

os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import needle

def main():
    tools = []
    agent = None
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
            op = req.get("op")
            if op == "init":
                tools = req.get("tools", [])
                agent = needle.Needle(tools=tools, generation=3)
                sys.stdout.write(json.dumps({"status": "ok", "tools_count": len(tools)}) + "\\n")
                sys.stdout.flush()
            elif op == "complete":
                text = req.get("text", "")
                t0 = time.perf_counter()
                res = agent.complete(text)
                lat_ms = (time.perf_counter() - t0) * 1000.0
                res["latency_ms"] = lat_ms
                sys.stdout.write(json.dumps({"status": "ok", "result": res}) + "\\n")
                sys.stdout.flush()
            elif op == "close":
                if agent:
                    agent.close()
                sys.stdout.write(json.dumps({"status": "closed"}) + "\\n")
                sys.stdout.flush()
                break
        except Exception as e:
            sys.stdout.write(json.dumps({"status": "error", "error": str(e)}) + "\\n")
            sys.stdout.flush()

if __name__ == "__main__":
    main()
"""


class NeedleAdapter:
    """Manages an interactive Needle 3 subprocess for fast-path inference."""

    def __init__(
        self,
        venv_python: Optional[Path] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        self.venv_python = venv_python or Path(r"C:\Users\cheta\Development\uri-agent\.venv-needle\Scripts\python.exe")
        self.tools = tools or []
        self._proc: Optional[subprocess.Popen] = None
        self._is_ready = False

    def start(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return

        cmd = [str(self.venv_python), "-c", _BRIDGE_SCRIPT]
        self._proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
        )

        # Initialize with tools
        init_req = json.dumps({"op": "init", "tools": self.tools})
        self._proc.stdin.write(init_req + "\n")
        self._proc.stdin.flush()

        resp_line = self._proc.stdout.readline()
        resp = json.loads(resp_line)
        if resp.get("status") == "ok":
            self._is_ready = True
        else:
            raise RuntimeError(f"Failed to initialize Needle: {resp}")

    def complete(self, user_text: str) -> SecondBrainProposal:
        if not self._is_ready or self._proc is None or self._proc.poll() is not None:
            self.start()

        req = json.dumps({"op": "complete", "text": user_text})
        t0 = time.perf_counter()
        self._proc.stdin.write(req + "\n")
        self._proc.stdin.flush()

        resp_line = self._proc.stdout.readline()
        lat_ms = (time.perf_counter() - t0) * 1000.0

        if not resp_line:
            return SecondBrainProposal(
                selected_tool=None,
                arguments={},
                confidence=None,
                escalate_to_main_brain=True,
                explanation="Needle process terminated unexpectedly",
                latency_ms=lat_ms,
                model_id="needle3",
                error="Process EOF",
            )

        resp = json.loads(resp_line)
        if resp.get("status") != "ok":
            return SecondBrainProposal(
                selected_tool=None,
                arguments={},
                confidence=None,
                escalate_to_main_brain=True,
                explanation=f"Needle error: {resp.get('error')}",
                latency_ms=lat_ms,
                model_id="needle3",
                error=resp.get("error"),
            )

        raw = resp["result"]
        calls = raw.get("function_calls") or []
        conf = raw.get("confidence")
        ram_mb = raw.get("peak_ram_mb")
        reasoning = raw.get("reasoning", "")

        if not calls:
            # Needle declined to call any tool
            return SecondBrainProposal(
                selected_tool=None,
                arguments={},
                confidence=conf,
                escalate_to_main_brain=True,
                explanation=f"Needle declined tools: {reasoning}",
                latency_ms=raw.get("latency_ms", lat_ms),
                peak_ram_mb=ram_mb,
                model_id="needle3",
            )

        first_call = calls[0]
        tool_name = first_call.get("name")
        args = first_call.get("arguments") or {}

        return SecondBrainProposal(
            selected_tool=tool_name,
            arguments=args,
            confidence=conf,
            escalate_to_main_brain=False,
            explanation=reasoning,
            latency_ms=raw.get("latency_ms", lat_ms),
            peak_ram_mb=ram_mb,
            model_id="needle3",
        )

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            try:
                self._proc.stdin.write(json.dumps({"op": "close"}) + "\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=2)
            except Exception:
                self._proc.terminate()
        self._proc = None
        self._is_ready = False

    def __enter__(self) -> "NeedleAdapter":
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        self.close()
