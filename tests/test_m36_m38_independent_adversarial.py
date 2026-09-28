"""Fresh independent adversarial probes for the provisional M36/M37/M38 batch."""
from __future__ import annotations

import threading
import time

import pytest

from tests.m37_edge_support import SALES, Env, make_workbook
from tests.m38_harness_support import escalated, fake_adapter
from uri_v1.execution.harness.contracts import ElevationGrant, Limits
from uri_v1.execution.verify import process_alive
from uri_v1.memory.contracts import negated
from tests.m37_edge_support import intake


@pytest.mark.parametrize("glyph", ["\u02bb", "\u201b", "\u2032", "\u2035", "\u275b", "\u275c"])
def test_additional_apostrophe_variants_fail_closed_for_elevation(glyph):
    text = f"don{glyph}t allow network for this run"
    assert negated(text)
    with pytest.raises(ValueError, match="EXPLICIT_ELEVATION_REQUIRED"):
        ElevationGrant.from_user(intake(text), "network", "run-1")


@pytest.mark.parametrize("source", [
    '''from openpyxl import Workbook\nout=Workbook(); ws=out.active; ws.title="Summary"; ws.append(["Total"]); ws.append([999]); out.save("summary.xlsx")\n''',
    '''import pandas as pd\nfrom openpyxl import Workbook\npd.read_csv("sales.csv")\nout=Workbook(); ws=out.active; ws.title="Summary"; ws.append(["Total"]); ws.append([999]); out.save("summary.xlsx")\n''',
    '''from pathlib import Path\nfrom openpyxl import load_workbook, Workbook\nwb=load_workbook(Path("sales.xlsx"))\nout=Workbook(); ws=out.active; ws.title="Summary"; ws.append(["Total"]); ws.append([999]); out.save("summary.xlsx")\n''',
])
def test_unproven_workbook_access_never_enters_local_execution(tmp_path, monkeypatch, source):
    env = Env(tmp_path, monkeypatch)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", source)
    result = env.edge.handle(env.task("SCRIPT_WORKBOOK_REPAIR"))
    assert result.route == "ESCALATE"
    assert result.local is None
    assert "WORKBOOK_ACCESS_UNPROVEN" in result.decision.findings["diagnosis"]["script"]["dynamic"]


def test_cancel_kills_windows_process_tree_and_never_succeeds(tmp_path, monkeypatch):
    env, request, runner, home = escalated(tmp_path, monkeypatch)
    pid_file = tmp_path / "cancel-child.pid"
    monkeypatch.setenv("URI_FAKE_SCENARIO", "hang_with_child")
    monkeypatch.setenv("URI_FAKE_CHILD_PID", str(pid_file))
    cancel = threading.Event()

    def trigger():
        deadline = time.monotonic() + 5
        while not pid_file.exists() and time.monotonic() < deadline:
            time.sleep(0.02)
        cancel.set()

    threading.Thread(target=trigger, daemon=True).start()
    outcome = runner.run(request, fake_adapter(home), session_id="session", cancel=cancel,
                         limits=Limits(timeout_s=30, inactivity_s=30))
    assert outcome.claimed_outcome == "outcome_unknown"
    assert outcome.metrics["cancelled"] and not outcome.verified
    if pid_file.exists():
        assert not process_alive(int(pid_file.read_text()))
