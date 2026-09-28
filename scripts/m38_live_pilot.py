"""M38 live pilot (VG-1 instrument check, NOT a VG-1 qualification).

One real task outside the Edge's local envelope ("make report.py work with
sales.xlsx", where the script's column literal has no unique local remap), run
with the real Claude Code CLI:

  Arm A  direct harness: raw request, the task files plus unrelated files, the
         harness's normal file and shell tools, no URI context.
  Arm B  URI-mediated: Edge escalation -> capsule (unresolved remainder, local
         findings, acceptance) -> restrictive default posture.

Both arms are judged by the same URI verifier and hashed acceptance criteria.
Token and cost figures are only what Claude Code reports. n is tiny; results
are indicative only. Writes docs/plans/M38_LIVE_PILOT_RESULTS.json.
"""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.m37_edge_qualification import _Patch  # noqa: E402
from tests.m37_edge_support import SALES, Env, acceptance, make_workbook, script  # noqa: E402
from uri_v1.edge.contracts import TaskClass  # noqa: E402
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter  # noqa: E402
from uri_v1.execution.harness.contracts import ClaimedOutcome, Limits  # noqa: E402
from uri_v1.execution.harness.discovery import resolve_command  # noqa: E402
from uri_v1.execution.harness.process import harness_env, supervise  # noqa: E402
from uri_v1.execution.harness.runner import HarnessRunner  # noqa: E402
from uri_v1.execution.lineage import record_and_verify  # noqa: E402
from uri_v1.execution.workspace import Workspace, WorkspaceInput, new_run_id  # noqa: E402

RESULTS = ROOT / "docs/plans/M38_LIVE_PILOT_RESULTS.json"
BUDGET = 1.0
RAW_REQUEST = "Make report.py work with sales.xlsx."
DISTRACTORS = {
    "sales_2024.xlsx": None,
    "notes.md": "# Notes\nQuarterly numbers are in the sales workbook. Ask Priya about the regions.\n",
    "helpers.py": "def fmt(x):\n    return f'{x:,.2f}'\n",
    "old_report.py": "import csv\nprint('deprecated')\n",
}


def setup(tmp: Path):
    env = Env(tmp, _Patch())
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script(column="Amt"))
    make_workbook(env.root / "sales_2024.xlsx", {"Sales": (("Region", "Amt"), (("North", 1),))})
    for name, text in DISTRACTORS.items():
        if text is not None: env.write(name, text)
    return env


def usage_of(claims) -> dict:
    return {k: claims.usage.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                             "cache_creation_input_tokens", "cost_usd", "num_turns", "tool_calls", "duration_ms")}


def arm_a(tmp: Path) -> dict:
    env = setup(tmp)
    task = env.task(TaskClass.SCRIPT_WORKBOOK_REPAIR, accept=acceptance(allowed=("report.py", "summary.xlsx")))
    names = ["sales.xlsx", "report.py", *DISTRACTORS]
    ws = Workspace.create(user_id=env.user, scratch_root=env.scratch, sources=env.sources, run_id=new_run_id(),
                          inputs=[WorkspaceInput("script" if n == "report.py" else "workbook" if n == "sales.xlsx" else "other",
                                                 env.ref(n).source_id, env.ref(n).content_sha256) for n in names])
    adapter = ClaudeCodeAdapter("claude")
    probe = adapter.probe()
    env.store.append(ws.run_id, "RUN_STARTED", {"executor": "HARNESS", "task_id": task.task_id, "trace_id": task.trace_id,
                                                "workspace_dir": str(ws.base), "manifest": [e.__dict__ for e in ws.manifest],
                                                "manifest_sha256": ws.manifest_sha256, "acceptance": task.acceptance.to_dict(),
                                                "acceptance_sha256": task.acceptance.sha256, "arm": "A_DIRECT"})
    argv = [*resolve_command("claude"), "-p", "--output-format", "stream-json", "--verbose", "--no-session-persistence",
            "--setting-sources", "", "--permission-mode", "dontAsk", "--allowedTools", "Read", "Edit", "Write", "Glob", "Grep", "Bash",
            "--strict-mcp-config", "--max-budget-usd", str(BUDGET)]
    proc = supervise(argv, cwd=ws.files, env=harness_env(), stdin_bytes=RAW_REQUEST.encode(), timeout_s=900, inactivity_s=300,
                     log_path=ws.bundle / "harness.log")
    # Reuse the adapter's parser; the capsule argument only supplies the session binding.
    cap = type("C", (), {"workspace_files": str(ws.files)})()
    claims = adapter.parse(proc, cap, probe.get("version"))
    lin = record_and_verify(recorder=env.recorder, ledger=env.ledger, store=env.store, workspace=ws, run_id=ws.run_id,
                            task_id=task.task_id, action_label="direct harness run (arm A)", session_id="session",
                            trace_id=task.trace_id, claimed_failed=claims.claimed_outcome is ClaimedOutcome.FAILED,
                            executor_claim=claims.to_claim())
    run = env.store.get(ws.run_id)
    return {"arm": "A_DIRECT", "verification_status": lin.verification_status, "claimed_outcome": claims.claimed_outcome.value,
            "changed": [c["relpath"] for c in lin.uri_computed_diff["changes"]], "instructions_bytes": len(RAW_REQUEST.encode()),
            "files_visible": len(names), "usage": usage_of(claims),
            "failed_checks": [i["kind"] for i in run["verifications"][-1]["items"] if i["status"] != "PASS"] if run["verifications"] else []}


def arm_b(tmp: Path) -> dict:
    env = setup(tmp)
    result = env.edge.handle(env.task(TaskClass.SCRIPT_WORKBOOK_REPAIR, accept=acceptance(allowed=("report.py", "summary.xlsx"))))
    assert result.route == "ESCALATE", result.route
    runner = HarnessRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder,
                           ledger=env.ledger, sources=env.sources)
    out = runner.run(result.escalation, ClaudeCodeAdapter("claude"), session_id="session",
                     limits=Limits(timeout_s=900, inactivity_s=300, max_budget_usd=BUDGET))
    run = env.store.get(out.run_id)
    return {"arm": "B_URI_MEDIATED", "verification_status": out.verification_status, "claimed_outcome": out.claimed_outcome,
            "changed": [c["relpath"] for c in run["result"]["uri_computed_diff"]["changes"]],
            "instructions_bytes": out.metrics["capsule_instructions_bytes"], "files_visible": out.metrics["input_files"],
            "edge_reason": result.decision.reason.value, "safety_flags": list(out.safety_flags),
            "usage": {k: out.metrics.get(k) for k in ("input_tokens", "output_tokens", "cache_read_input_tokens",
                                                      "cache_creation_input_tokens", "cost_usd", "num_turns", "tool_calls", "duration_ms")},
            "failed_checks": [i["kind"] for i in run["verifications"][-1]["items"] if i["status"] != "PASS"] if run["verifications"] else []}


def main(repeats: int = 2):
    if not resolve_command("claude"):
        RESULTS.write_text(json.dumps({"status": "UNAVAILABLE", "reason": "claude CLI not installed"}, indent=1) + "\n"); return 0
    rows = []
    for i in range(repeats):
        for fn in (arm_a, arm_b):
            with tempfile.TemporaryDirectory(prefix="m38live-") as d:
                try:
                    rows.append(dict(fn(Path(d)), repeat=i))
                except Exception as exc:  # recorded, never hidden
                    rows.append({"arm": fn.__name__, "repeat": i, "error": f"{type(exc).__name__}: {exc}"[:300]})
            print(json.dumps(rows[-1]))
    out = {"schema_version": "m38.live-pilot.v1", "status": "PILOT_NOT_QUALIFICATION", "task": RAW_REQUEST,
           "codex": "UNAVAILABLE (codex CLI not installed in this environment)", "budget_usd_per_run": BUDGET, "rows": rows}
    RESULTS.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 2))
