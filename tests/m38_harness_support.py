"""Shared M38 fixtures: an Edge escalation from real files, and a harness runner on real M36 stores."""
from __future__ import annotations

from pathlib import Path
import sys

from tests.m37_edge_support import SALES, Env, make_workbook, script
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.execution.harness.runner import HarnessRunner

ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "fixtures" / "m38_harness" / "fake_claude.py"


def fake_adapter(home: Path, **kw) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter((sys.executable, str(FAKE)), home=home, **kw)


def escalated(tmp: Path, monkeypatch, *, column="Amt"):
    """Real Edge escalation: the script's column literal has no unique local remap."""
    env = Env(tmp, monkeypatch)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script(column=column))
    result = env.edge.handle(env.task("SCRIPT_WORKBOOK_REPAIR"))
    assert result.route == "ESCALATE", result
    runner = HarnessRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder,
                           ledger=env.ledger, sources=env.sources)
    home = tmp / "home"; home.mkdir(exist_ok=True)
    return env, result.escalation, runner, home
