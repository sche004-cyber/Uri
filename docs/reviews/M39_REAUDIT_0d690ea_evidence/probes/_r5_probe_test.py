"""Re-audit probes on M39 0d690ea. Run from repo root: python -m pytest <this> -q -rA -s"""
import hashlib, json, sys
from pathlib import Path
import pytest
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter, CodexCliAdapter
from uri_v1.office import request as req
from uri_v1.office.view import render
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text
FAKE = Path(__file__).with_name("_r5_fake.py")
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None

def setup(tmp, monkeypatch, adapter_cls=ClaudeCodeAdapter, with_harness=True):
    env = OfficeEnv(tmp, monkeypatch, with_harness=with_harness)
    if adapter_cls is not None and with_harness:
        env.session.adapter = adapter_cls((sys.executable, str(FAKE)), home=env.tmp / "home")
    make_workbook(env.root / "sales.xlsx", SALES); env.write("report.py", script_text(column="Amt"))
    raw = "make report.py work with sales.xlsx"; parsed = req.parse(raw); t, tr = env.turn()
    step = answer_asks(env, env.session.start(raw, session_id="s", turn_id=t, trace_id=tr, parsed=parsed),
                       request_names(raw, parsed), session_id="s")
    return env, step

def run(tmp, monkeypatch, mode):
    env, step = setup(tmp, monkeypatch)
    assert step.kind == "ESCALATION_PROPOSAL", step
    monkeypatch.setenv("URI_PROBE_MODE", mode); monkeypatch.setenv("URI_PROBE_ROOT", str(env.root))
    before = {n: sha(env.root / n) for n in ("sales.xlsx", "report.py")}
    t, tr = env.turn()
    res = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="s", turn_id=t, trace_id=tr)
    text = render(res)
    status = env.log.load().task(step.task_id).payload.get("status") if env.log.load().task(step.task_id) else None
    out = {"mode": mode, "kind": res.kind, "flags": list(getattr(res, "safety_flags", ()) or ()),
           "originals_changed_field": list(getattr(res, "originals_changed", ()) or ()),
           "originals_changed_real": [n for n in before if sha(env.root / n) != before[n]],
           "root_files": sorted(p.name for p in env.root.iterdir()), "task_status": status, "render": text}
    print("R5PROBE>>>", json.dumps(out)); return env, res, out

@pytest.mark.parametrize("mode", ["write_sibling", "write_sibling_and_fix", "delete_original", "write_original_nofix",
                                  "write_both_originals", "rewrite_same_bytes", "honest"])
def test_harness_modes(tmp_path, monkeypatch, mode):
    env, res, out = run(tmp_path, monkeypatch, mode)
    if mode == "honest":
        assert res.kind == "AWAITING_APPROVAL"; return
    # never a false success
    assert res.kind != "AWAITING_APPROVAL" or mode == "rewrite_same_bytes"
    # whenever a real original changed, the reply must not say nothing was written
    if out["originals_changed_real"]:
        assert "Nothing was written" not in out["render"]
        assert "Warning: your original file(s) were changed" in out["render"]

def test_escalation_screen_codex(tmp_path, monkeypatch):
    env, step = setup(tmp_path, monkeypatch, adapter_cls=CodexCliAdapter)
    text = render(step); print("R5SCREEN_CODEX>>>", json.dumps(text))
    assert "Harness: Codex CLI." in text and "external model provider" in text and "never the network" not in text

def test_escalation_screen_not_installed(tmp_path, monkeypatch):
    env, step = setup(tmp_path, monkeypatch, adapter_cls=None)
    env.session.adapter = ClaudeCodeAdapter(("/nonexistent/claude-binary",), home=env.tmp / "home")
    text = render(step); t, tr = env.turn()
    res = env.session.confirm_escalation(step.task_id, "yes", session_id="s", turn_id=t, trace_id=tr)
    print("R5SCREEN_UNINSTALLED>>>", json.dumps({"screen": text, "after": res.kind, "render": render(res)}))
    assert res.kind == "HARNESS_UNAVAILABLE"
