"""A scriptable fake of the llama-server endpoints OI uses, on a real loopback socket.

Each POST /v1/chat/completions pops the next script from `server.scripts` (or uses `server.default`).
A script is a dict:
  {"chunks": [("answer"|"reasoning", text), ...], "finish": "stop"|"length"|None, "delay": s_between_chunks,
   "first_delay": s_before_first_chunk, "status": http_status, "raw": bytes_to_send_instead,
   "drop_after": n_chunks_then_close_socket, "json": non_stream_content_string}
The server records every request body and whether the client disconnected mid-stream.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        srv = self.server
        if self.path == "/health":
            self._json(srv.health, {"status": "ok" if srv.health == 200 else "loading"})
        elif self.path == "/props":
            self._json(200, srv.props)
        elif self.path == "/slots":
            self._json(200, [{"id": 0, "is_processing": srv.processing}])
        else:
            self._json(404, {})

    def do_POST(self):
        srv = self.server
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        srv.requests.append(body)
        script = srv.scripts.pop(0) if srv.scripts else dict(srv.default)
        time.sleep(script.get("header_delay", 0))      # server busy: no response headers yet
        if body.get("stream") and "json" in script:
            script = dict(script, chunks=[("answer", script["json"])], finish=script.get("finish", "stop"))
        if script.get("status", 200) != 200:
            self._json(script["status"], {"error": {"message": "fake failure"}})
            return
        if not body.get("stream"):
            content = script.get("json")
            if content is None:
                content = "".join(t for k, t in script.get("chunks", []) if k == "answer")
            reasoning = "".join(t for k, t in script.get("chunks", []) if k == "reasoning")
            time.sleep(script.get("first_delay", 0))
            self._json(200, {"choices": [{"message": {"content": content, "reasoning_content": reasoning or None},
                                          "finish_reason": script.get("finish", "stop")}],
                             "timings": {"prompt_n": 10, "predicted_n": 5}})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

        def send(obj_or_raw):
            data = obj_or_raw if isinstance(obj_or_raw, bytes) else ("data: " + json.dumps(obj_or_raw) + "\n\n").encode()
            self.wfile.write(b"%x\r\n%s\r\n" % (len(data), data))
            self.wfile.flush()

        srv.processing = True
        try:
            time.sleep(script.get("first_delay", 0))
            if "raw" in script:
                send(script["raw"])
            for i, (kind, text) in enumerate(script.get("chunks", [])):
                if script.get("drop_after") is not None and i >= script["drop_after"]:
                    self.connection.shutdown(socket.SHUT_RDWR)
                    srv.dropped += 1
                    return
                key = "reasoning_content" if kind == "reasoning" else "content"
                send({"choices": [{"delta": {key: text}, "finish_reason": None}]})
                time.sleep(script.get("delay", 0))
            if script.get("finish") is not None:
                send({"choices": [{"delta": {}, "finish_reason": script["finish"]}],
                      "timings": {"prompt_n": 12, "predicted_n": len(script.get("chunks", [])),
                                  "predicted_per_second": 100.0}, "usage": {"completion_tokens": 3}})
                send(b"data: [DONE]\n\n")
            self.wfile.write(b"0\r\n\r\n")
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError):
            srv.disconnects += 1
        finally:
            srv.processing = False


class FakeLlama(ThreadingHTTPServer):
    daemon_threads = True

    def handle_error(self, request, client_address):
        pass   # client disconnects are expected in cancellation tests

    def __init__(self, port=None):
        super().__init__(("127.0.0.1", port or free_port()), _Handler)
        self.scripts, self.requests = [], []
        self.default = {"chunks": [("answer", "ok")], "finish": "stop"}
        self.health, self.processing, self.disconnects, self.dropped = 200, False, 0, 0
        self.props = {"model_path": "X", "build_info": "b11425-e117148a4", "total_slots": 1,
                      "default_generation_settings": {"n_ctx": 32768}}
        self.thread = threading.Thread(target=self.serve_forever, daemon=True)

    @property
    def url(self):
        return "http://127.0.0.1:%d" % self.server_address[1]

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *a):
        self.shutdown()
        self.server_close()
