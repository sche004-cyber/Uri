"""Fake Claude Code for M39 offline qualification (no network, no model, no cost).

Generic over filenames (unlike fixtures/m38_harness/fake_claude.py, which is
hardcoded to report.py/sales.xlsx): it finds the one `*.py` and the one
`*.xlsx`/`*.xlsm` file in its working directory and acts on them according to
URI_FAKE_SCENARIO. Emits real `claude -p --output-format stream-json` event
shapes so the real `ClaudeCodeAdapter.parse` is exercised unmodified.
"""
import glob
import json
import os
from pathlib import Path
import sys
import time


def emit(obj):
    sys.stdout.write(json.dumps(obj) + "\n"); sys.stdout.flush()


def result(ok=True, subtype="success", text="Done."):
    emit({"type": "result", "subtype": subtype, "is_error": not ok, "result": text, "session_id": "fake-session-m39",
          "num_turns": 2, "total_cost_usd": 0.01,
          "usage": {"input_tokens": 900, "output_tokens": 200, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
          "modelUsage": {"fake-model": {}}})


def _script():
    names = sorted(glob.glob("*.py"))
    return Path(names[0]) if names else None


def main():
    if "--version" in sys.argv:
        print("2.1.283 (Fake Claude Code, M39)"); return 0
    prompt = sys.stdin.read()
    scenario = os.environ.get("URI_FAKE_SCENARIO", "honest")
    find = os.environ.get("URI_FAKE_FIND", "")
    replace = os.environ.get("URI_FAKE_REPLACE", "")
    emit({"type": "system", "subtype": "init", "session_id": "fake-session-m39", "tools": ["Read", "Edit"]})
    emit({"type": "assistant", "message": {"model": "fake-model", "content": [{"type": "tool_use", "name": "Read", "input": {}}]}})
    script = _script()
    if scenario == "honest" and script is not None and find:
        script.write_text(script.read_text().replace(find, replace))
    elif scenario == "false_claim":
        pass  # claims success below, changes nothing
    elif scenario == "empty_script" and script is not None:
        script.write_text("# harness removed the script's logic\n")
    elif scenario == "error":
        result(False, "error_during_execution", "Could not complete."); return 1
    emit({"type": "assistant", "message": {"model": "fake-model", "content": [{"type": "tool_use", "name": "Edit", "input": {}}]}})
    result()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
