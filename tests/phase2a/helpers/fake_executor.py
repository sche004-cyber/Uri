"""Scripted fake executor speaking the generic NDJSON dialect. Used ONLY by tests.

Scenarios mimic real failure shapes seen in Codex/Claude streams: no terminal event, terminal then hang,
truncated final line, free-text success contradicting a failed command, quota text, grandchild processes.
"""
import argparse
import json
import os
import subprocess
import sys
import time


def emit(obj, newline=True):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + ("\n" if newline else ""))
    sys.stdout.flush()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--path")
    ap.add_argument("--content", default="data")
    ap.add_argument("--sleep", type=float, default=3600)
    ap.add_argument("--pidfile")
    ap.add_argument("--counter")
    a = ap.parse_args()
    s = a.scenario
    if s != "evil_session":
        emit({"type": "session", "session_id": "sess-" + os.environ.get("URI_ATTEMPT_FENCE", "0")})

    def write():
        with open(a.path, "w", encoding="utf-8") as f:
            f.write(a.content)
        if a.counter:
            with open(a.counter, "a", encoding="utf-8") as c:
                c.write("effect" + chr(10))

    if s == "ok_write":
        write()
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        emit({"type": "done", "ok": True, "summary": "wrote"})
    elif s == "ok_read":
        emit({"type": "tool_result", "command": "read", "exit_code": 0})
        emit({"type": "done", "ok": True, "summary": "read"})
    elif s == "no_terminal_after_write":
        write()
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
    elif s == "no_terminal_nothing":
        emit({"type": "message", "text": "thinking"})
    elif s == "terminal_hang":
        write()
        emit({"type": "done", "ok": True, "summary": "wrote"})
        time.sleep(a.sleep)
    elif s == "truncated_terminal":
        write()
        sys.stdout.write('{"type":"done","ok":true,"summ')
        sys.stdout.flush()
    elif s == "text_success_but_failed_command":
        emit({"type": "tool_result", "command": "pytest -q", "exit_code": 1})
        emit({"type": "message", "text": "All tests passed. Success!"})
    elif s == "claims_success_no_effect":
        emit({"type": "done", "ok": True, "summary": "all done"})
    elif s == "quota":
        emit({"type": "done", "ok": False, "message": "rate_limit reached, try later"})
    elif s == "quota_reset":
        emit({"type": "done", "ok": False, "message": "rate_limit reached reset_at=" + a.content})
    elif s == "done_then_exit3":
        emit({"type": "done", "ok": True, "summary": "claims ok but crashes"})
        sys.stdout.flush()
        os._exit(3)
    elif s == "evil_session":
        emit({"type": "session", "session_id": "--dangerously-skip-permissions"})
    elif s == "error_claim":
        emit({"type": "done", "ok": False, "message": "boom"})
    elif s == "partial_write_then_die":
        with open(a.path, "w", encoding="utf-8") as f:
            f.write("PART")
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        os._exit(3)
    elif s == "sleep":
        emit({"type": "safe_point"})
        time.sleep(a.sleep)
    elif s == "sleep_unsafe":
        emit({"type": "message", "text": "working"})
        time.sleep(a.sleep)
    elif s == "grandchild":
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(3600)"])
        if a.pidfile:
            with open(a.pidfile, "w") as f:
                f.write(str(child.pid))
        emit({"type": "message", "text": "spawned"})
        time.sleep(a.sleep)
    elif s == "unicode_write":
        write()
        emit({"type": "message", "text": "готово ✓ 日本語"})
        emit({"type": "done", "ok": True, "summary": "ok"})
    else:
        emit({"type": "message", "text": "unknown scenario"})
        sys.exit(2)


if __name__ == "__main__":
    main()
