"""Phase 2 operational qualification (EXE-1): a SCRIPTED local model endpoint for exercising the NATIVE Codex binary.

It speaks the subset of the Responses streaming API that `codex exec` 0.158.0 uses, on 127.0.0.1 only, and decides each
reply from the request text, never from a model:

  * the qualification probe prompt ("Reply with exactly the word OK ...")  -> message "OK"
  * a request mentioning `pong.txt`                                        -> exec_command that writes PONG into
                                                                              ./pong.txt, then message "DONE"
  * a request mentioning `essay`                                           -> exec_command `Start-Sleep -Seconds 600`,
                                                                              then a stream that stays open (for
                                                                              mid-run cancellation)
  * anything else                                                          -> message "UNSCRIPTED"

What this proves and what it does not: the NATIVE binary, its launch chain, the client-profile Codex home, the Windows
sandbox, the supervisor's job object and the lifecycle frames are all real. The MODEL is not: nothing here is evidence
about a provider, a login, or a model's behaviour, and a record made with it must say so.
"""
from __future__ import annotations

import http.server
import json
import threading
import time

WRITE_PONG = "[System.IO.File]::WriteAllText((Join-Path (Get-Location) 'pong.txt'), 'PONG')"
SLEEP = "Start-Sleep -Seconds 600"


def _text(body):
    parts = []

    def walk(x):
        if isinstance(x, str):
            parts.append(x)
        elif isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk([i for i in body.get("input", []) if isinstance(i, dict) and i.get("role") == "user"])
    return " ".join(parts)


class ScriptedEndpoint:
    def __init__(self, port=0, hold_s=600):
        self.requests = []
        self.hold_s = hold_s
        self._stop = threading.Event()
        endpoint = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("content-length", 0))
                body = json.loads(self.rfile.read(n) or b"{}")
                outputs = [i for i in body.get("input", []) if isinstance(i, dict) and i.get("type") == "function_call_output"]
                text = _text(body)
                kind = ("probe" if "Reply with exactly the word OK" in text else "pong" if "pong.txt" in text
                        else "essay" if "essay" in text else "unscripted")
                endpoint.requests.append({"at": time.time(), "path": self.path, "kind": kind, "tool_outputs": len(outputs),
                                          "model": body.get("model")})
                self.send_response(200)
                self.send_header("content-type", "text/event-stream")
                self.end_headers()

                def ev(obj):
                    self.wfile.write(("event: %s\ndata: %s\n\n" % (obj["type"], json.dumps(obj))).encode())
                    self.wfile.flush()
                try:
                    ev({"type": "response.created", "response": {"id": "r"}})
                    if kind in ("pong", "essay") and not outputs:
                        cmd = WRITE_PONG if kind == "pong" else SLEEP
                        args = {"cmd": cmd} if kind == "pong" else {"cmd": cmd, "yield_time_ms": 600000}
                        item = {"type": "function_call", "id": "fc1", "call_id": "call_1", "name": "exec_command",
                                "arguments": json.dumps(args)}
                    elif kind == "essay":
                        endpoint._stop.wait(endpoint.hold_s)       # keep the attempt running until it is killed
                        return
                    else:
                        word = {"probe": "OK", "pong": "DONE"}.get(kind, "UNSCRIPTED")
                        item = {"type": "message", "role": "assistant", "id": "m1", "content": [{"type": "output_text", "text": word}]}
                    ev({"type": "response.output_item.done", "item": item})
                    ev({"type": "response.completed", "response": {"id": "r", "usage": {"input_tokens": 1, "output_tokens": 1,
                                                                                          "total_tokens": 2}}})
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    endpoint.requests[-1]["client_disconnected"] = True

            def log_message(self, *a):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
        self.server.daemon_threads = True
        self.port = self.server.server_address[1]
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self.server.shutdown()
        self.server.server_close()

    def codex_config(self, sandbox="unelevated"):
        """config.toml for a SYNTHETIC client profile's Codex home: this endpoint as the model provider, plus the
        Windows sandbox mode. Never written into a real profile."""
        lines = ['# SYNTHETIC client profile (scripts/phase2oq_scripted_endpoint.py): scripted local endpoint, not a model',
                 'model = "uri-scripted"', 'model_provider = "uri_scripted"', "",
                 "[model_providers.uri_scripted]", 'name = "URI scripted local endpoint (test fixture)"',
                 f'base_url = "http://127.0.0.1:{self.port}/v1"', 'wire_api = "responses"', "requires_openai_auth = false"]
        if sandbox:
            lines += ["", "[windows]", f'sandbox = "{sandbox}"']
        return "\n".join(lines) + "\n"
