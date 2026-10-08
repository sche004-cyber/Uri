"""Deterministic fake Claude-Code-shaped harness for offline C4 tests (not a real model)."""
import json, os, subprocess, sys, time
from pathlib import Path

def emit(o): sys.stdout.write(json.dumps(o) + "\n"); sys.stdout.flush()

def main():
    if "--version" in sys.argv: print("9.9.9 (fake)"); return 0
    argv_out = os.environ.get("URI_FAKE_ARGV_OUT")
    if argv_out: Path(argv_out).write_text(json.dumps(sys.argv[1:]))
    sys.stdin.read()
    sc = os.environ.get("URI_FAKE_SCENARIO", "honest")
    if sys.argv[1:2] == ["exec"]:   # Codex-shaped events
        emit({"type": "thread.started", "thread_id": "fake-thread"})
        if sc == "honest":
            Path("out.txt").write_text("hello from codex-shaped harness\n")
            emit({"type": "item.completed", "item": {"type": "agent_message", "text": "done"}})
            emit({"type": "turn.completed", "usage": {"input_tokens": 3, "output_tokens": 2}})
            return 0
        emit({"type": "turn.failed", "error": {"message": "usage limit reached"}}); return 1
    emit({"type": "system", "subtype": "init"})
    if sc != "quota":   # "quota": the limit hits on the first model call, before any tool is requested
        emit({"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Write", "input": {}}]}})
    if sc == "honest":
        Path("out.txt").write_text("hello from harness\n")
        emit({"type": "result", "subtype": "success", "is_error": False, "result": "done",
              "usage": {"input_tokens": 10, "output_tokens": 5}, "total_cost_usd": 0.001})
    elif sc == "false_claim":
        emit({"type": "result", "subtype": "success", "is_error": False, "result": "done (nothing written)"})
    elif sc in ("quota", "quota_after_tool"):   # quota_after_tool: a Write was requested, THEN the limit hit
        emit({"type": "result", "subtype": "error_during_execution", "is_error": True,
              "result": "Claude usage limit reached. Rate limit resets later."})
        return 1
    elif sc == "hang_with_child":
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(3600)"])
        Path(os.environ["URI_FAKE_CHILD_PID"]).write_text(str(child.pid)); time.sleep(3600)
    return 0

sys.exit(main())
