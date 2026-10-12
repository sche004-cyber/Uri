import json, sys, http.server
LOG = open(sys.argv[2], "a", encoding="utf-8"); CMD = sys.argv[3]
class H(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("content-length", 0)); body = json.loads(self.rfile.read(n) or b"{}")
        outs = [i for i in body.get("input", []) if isinstance(i, dict) and i.get("type") == "function_call_output"]
        LOG.write(json.dumps({"outs": outs})[:5000] + "\n"); LOG.flush()
        self.send_response(200); self.send_header("content-type", "text/event-stream"); self.end_headers()
        def ev(obj): self.wfile.write(("event: %s\ndata: %s\n\n" % (obj["type"], json.dumps(obj))).encode()); self.wfile.flush()
        ev({"type": "response.created", "response": {"id": "r"}})
        if not outs:
            item = {"type": "function_call", "id": "fc1", "call_id": "call_1", "name": "exec_command", "arguments": json.dumps({"cmd": CMD})}
        else:
            item = {"type": "message", "role": "assistant", "id": "m1", "content": [{"type": "output_text", "text": "DONE"}]}
        ev({"type": "response.output_item.done", "item": item})
        ev({"type": "response.completed", "response": {"id": "r", "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}})
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
