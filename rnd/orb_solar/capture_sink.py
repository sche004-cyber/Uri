"""Tiny local sink that stores PNG frames posted by the prototype harness.

Used only for R&D evidence capture; it binds to loopback and writes into the
evidence folder under a sanitised name.
"""
import base64
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "docs", "orb_solar", "evidence", "captures")
OUT = os.path.abspath(OUT)
os.makedirs(OUT, exist_ok=True)
SAFE = re.compile(r"[^A-Za-z0-9_.-]")


class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, OPTIONS")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8")
        name, _, data = body.partition("|")
        name = SAFE.sub("_", name)[:80] or "frame"
        data = data.split(",", 1)[-1]
        path = os.path.join(OUT, name + ".png")
        with open(path, "wb") as fh:
            fh.write(base64.b64decode(data))
        self.send_response(200)
        self._cors()
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(path.encode("utf-8"))

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    HTTPServer(("127.0.0.1", 8732), Handler).serve_forever()
