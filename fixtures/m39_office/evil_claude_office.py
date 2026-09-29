"""Adversarial fake Claude Code for M39 repair regression tests (offline, no
model, no network, no cost). Test-only: exercises the real HarnessRunner /
ClaudeCodeAdapter path so a regression test can reproduce the actual
ORIGINAL_MODIFIED_DURING_VERIFICATION flag (R1-A) instead of hand-writing a
run-store record the real runner never produces.

Mirrors fixtures/m39_office/fake_claude_office.py's protocol; adds a
"touch_original" scenario (URI_PROBE_SCENARIO env var) whose fixed script
also appends a byte to a real original file (URI_PROBE_ORIGINAL env var) when
it runs -- which happens again during the M37 verifier's own re-execution of
the candidate, after URI's first post-run originals-check already passed.
"""
import glob
import json
import os
import sys
from pathlib import Path


def emit(o):
    sys.stdout.write(json.dumps(o) + "\n")
    sys.stdout.flush()


def main():
    if "--version" in sys.argv:
        print("2.1.283 (Fake Claude Code, evil, test-only)")
        return 0
    sys.stdin.read()
    scenario = os.environ.get("URI_PROBE_SCENARIO", "honest")
    emit({"type": "system", "subtype": "init", "session_id": "evil", "tools": ["Read", "Edit"]})
    script = Path(sorted(glob.glob("*.py"))[0])
    if scenario == "honest":
        script.write_text(script.read_text().replace('"Amt"', '"Amount"'))
    elif scenario == "touch_original":
        target = os.environ["URI_PROBE_ORIGINAL"]
        fixed = script.read_text().replace('"Amt"', '"Amount"')
        script.write_text(
            "import os\nif os.path.exists(%r):\n    open(%r, 'ab').write(b'x')\n" % (target, target) + fixed
        )
    emit({"type": "result", "subtype": "success", "is_error": False, "result": "Done, fixed and verified.",
          "session_id": "evil", "num_turns": 2, "total_cost_usd": 0.01,
          "usage": {"input_tokens": 1, "output_tokens": 1, "cache_read_input_tokens": 0, "cache_creation_input_tokens": 0},
          "modelUsage": {"fake": {}}})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
