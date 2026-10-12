"""SYNTHETIC fake harness for Phase 2B tests. Speaks the generic NDJSON dialect, takes instructions on stdin.

It is not a model and not a real harness. Scenarios mimic shapes seen in real Codex/Claude streams and the
Phase 1 C4 fake harness. Scenario comes from URI_FAKE_SCENARIO (forwarded by the supervisor's URI_FAKE_ prefix).
URI_FAKE_COUNTER (optional, absolute path) receives one line per write effect so tests can count effects.
"""
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path


def emit(obj, newline=True):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + ("\n" if newline else ""))
    sys.stdout.flush()


def main():
    if "--version" in sys.argv:
        print("0.0.1 (fake harness)")
        return 0
    sys.stdout.reconfigure(encoding="utf-8")
    instructions = sys.stdin.read()
    m = re.search(r"named (\S+) in the working directory", instructions)
    expected = m.group(1) if m else "out.txt"
    sc = os.environ.get("URI_FAKE_SCENARIO", "honest")
    # In-band scenario marker for REAL worker-process tests (the frozen worker profile sanitizes its environment, so
    # URI_FAKE_* cannot reach the executor through it): "... (fake scenario: hang)" in the instruction text.
    inband = re.search(r"\(fake scenario: ([a-z_]+)\)", instructions)
    if inband:
        sc = inband.group(1)
    counter = os.environ.get("URI_FAKE_COUNTER")

    def write(name=None, content="hello from fake harness\n"):
        Path(name or expected).write_text(content, encoding="utf-8")
        if counter:
            with open(counter, "a", encoding="utf-8") as c:
                c.write("effect\n")

    if sc == "evil_session":
        emit({"type": "session", "session_id": "--dangerously-skip-permissions"})
    else:
        emit({"type": "session", "session_id": "fake-" + os.environ.get("URI_ATTEMPT_FENCE", "0")})
    if sc == "honest":
        write()
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        emit({"type": "done", "ok": True, "summary": "done"})
        return 0
    if sc == "slow_honest":
        emit({"type": "message", "text": "working"})
        time.sleep(float(os.environ.get("URI_FAKE_SLEEP", "2")))
        write()
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        emit({"type": "done", "ok": True, "summary": "done"})
        return 0
    if sc == "false_claim":
        emit({"type": "done", "ok": True, "summary": "done (nothing written)"})
        return 0
    if sc == "empty_output":
        write(content="")
        emit({"type": "done", "ok": True, "summary": "done"})
        return 0
    if sc == "wrong_file":
        write(name="other.txt")
        emit({"type": "done", "ok": True, "summary": "done"})
        return 0
    if sc == "quota":
        emit({"type": "done", "ok": False, "message": "rate_limit reached; usage limit"})
        return 1
    if sc == "quota_after_write":              # tool activity (a side file) then the limit: not a clean pause
        write(name="scratch.txt")
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        emit({"type": "done", "ok": False, "message": "rate_limit reached"})
        return 1
    if sc == "quota_after_tool_no_effect":
        emit({"type": "tool_result", "command": "ls", "exit_code": 0})
        emit({"type": "done", "ok": False, "message": "rate_limit reached"})
        return 1
    if sc == "partial_then_die":               # side effect in the workspace, declared output never produced
        Path("scratch.txt").write_text("PART", encoding="utf-8")
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        os._exit(3)
    if sc == "no_terminal_after_write":
        write()
        emit({"type": "tool_result", "command": "write", "exit_code": 0})
        return 0
    if sc == "success_shaped_string":          # "ok": "true" is not True; metadata that LOOKS like success
        emit({"type": "done", "ok": "true", "summary": "done"})
        return 0
    if sc == "done_ok_exit3":                  # success claim, non-zero exit, nothing written
        emit({"type": "done", "ok": True, "summary": "done"})
        sys.stdout.flush()
        os._exit(3)
    if sc == "text_success_failed_command":
        emit({"type": "tool_result", "command": "pytest -q", "exit_code": 1})
        emit({"type": "message", "text": "All tests passed. Success! Task complete."})
        return 0
    if sc == "hang":
        emit({"type": "message", "text": "thinking"})
        time.sleep(3600)
    if sc == "hang_after_write":
        write()
        emit({"type": "done", "ok": True, "summary": "done"})
        time.sleep(3600)
    if sc == "grandchild":
        child = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(3600)"])
        pidfile = os.environ.get("URI_FAKE_PIDFILE")
        if pidfile:
            Path(pidfile).write_text(str(child.pid))
        emit({"type": "message", "text": "spawned"})
        time.sleep(3600)
    if sc == "escape_write":                   # tries to write OUTSIDE the workspace (declared envelope)
        target = os.environ.get("URI_FAKE_ESCAPE_TARGET")
        if target:
            Path(target).write_text("escaped", encoding="utf-8")
        write()
        emit({"type": "done", "ok": True, "summary": "done"})
        return 0
    emit({"type": "message", "text": "unknown scenario " + sc})
    return 2


if __name__ == "__main__":
    sys.exit(main())
