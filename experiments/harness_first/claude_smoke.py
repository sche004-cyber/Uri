"""Small live smoke test of URI's Claude Code harness adapter (M38) on this PC, subscription auth only.

1. Preflight: no API-key or third-party-cloud variables in the environment; record the CLI version.
2. Auth probe: one tiny `claude -p` call; read `apiKeySource` from the stream-json init event. Anything
   other than "none" (subscription / OAuth login) stops the test before any task runs.
3. One URI-mediated run (M38 live-pilot arm B, reused unchanged): Edge declines locally, URI builds the
   capsule, the adapter runs Claude Code under the restrictive posture inside a supervised process in a
   copy-in/copy-out workspace, and URI's own verifier decides the outcome.
Consent: the User asked for this smoke test in the project thread on 2026-10-01 (recorded below).
Usage: python claude_smoke.py --out runs/claude_smoke.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from uri_v1.execution.harness.discovery import probe_version, resolve_command  # noqa: E402

BILLING_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX",
                "ANTHROPIC_BASE_URL")


def auth_probe() -> dict:
    argv = [*resolve_command("claude"), "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
            "--setting-sources", "", "--strict-mcp-config", "--max-budget-usd", "0.05", "--permission-mode", "dontAsk"]
    with tempfile.TemporaryDirectory(prefix="uri-claude-auth-") as d:
        t = time.perf_counter()
        p = subprocess.run(argv, input="Reply with the single word OK.", capture_output=True, text=True, cwd=d,
                           timeout=180, encoding="utf-8")
    init, result = {}, {}
    for line in p.stdout.splitlines():
        try:
            o = json.loads(line)
        except ValueError:
            continue
        if o.get("type") == "system" and o.get("subtype") == "init":
            init = o
        if o.get("type") == "result":
            result = o
    return {"exit": p.returncode, "ms": (time.perf_counter() - t) * 1000, "apiKeySource": init.get("apiKeySource"),
            "model": init.get("model"), "result_text": (result.get("result") or "")[:40],
            "is_error": result.get("is_error"), "stderr_tail": p.stderr[-300:]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    report = {"consent": "User request in project thread 'Harness-first Edge track', 2026-10-01 04:05 UTC: "
                         "small live Claude Code subscription adapter smoke test",
              "billing_env_present": [v for v in BILLING_VARS if os.environ.get(v)]}
    report["version"] = probe_version("claude")
    if report["billing_env_present"]:
        report["status"] = "STOPPED_API_KEY_ENV"
    else:
        report["auth_probe"] = auth_probe()
        src = report["auth_probe"]["apiKeySource"]
        if src != "none":
            report["status"] = f"STOPPED_AUTH_MODE:{src}"
        else:
            report["auth_mode"] = "subscription (apiKeySource=none)"
            sys.path.insert(0, str(ROOT / "scripts"))
            import m38_live_pilot as pilot  # reused unchanged (arm B: URI-mediated)
            with tempfile.TemporaryDirectory(prefix="uri-claude-smoke-") as d:
                t = time.perf_counter()
                try:
                    report["run"] = pilot.arm_b(Path(d))
                except Exception as exc:
                    report["run"] = {"error": f"{type(exc).__name__}: {exc}"[:400]}
                report["run_wall_ms"] = (time.perf_counter() - t) * 1000
            report["status"] = "COMPLETED" if "error" not in report["run"] else "RUN_ERROR"
    Path(a.out).write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(json.dumps(report, indent=1, default=str)[:3000])


if __name__ == "__main__":
    main()
