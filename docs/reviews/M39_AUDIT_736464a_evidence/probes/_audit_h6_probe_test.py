"""Independent audit probes (thread h6lbhn) on M39 736464a: adversarial harness behaviour.
Run from repo root: python -m pytest <this file> -q -rA -s"""
import hashlib, json, sys, uuid
from pathlib import Path
import pytest
from openpyxl import load_workbook
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.office import request as req
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text
FAKE = Path(__file__).with_name("_audit_h6_fake.py")
RESULTS = {}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run_flow(tmp, monkeypatch, probe, extra_env=()):
    env = OfficeEnv(tmp, monkeypatch, with_harness=True)
    env.session.adapter = ClaudeCodeAdapter((sys.executable, str(FAKE)), home=env.tmp / "home")
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))
    before = {n: sha(env.root / n) for n in ("sales.xlsx", "report.py")}
    raw = "make report.py work with sales.xlsx"; parsed = req.parse(raw)
    t, tr = env.turn()
    step = env.session.start(raw, session_id="s", turn_id=t, trace_id=tr, parsed=parsed)
    step = answer_asks(env, step, request_names(raw, parsed), session_id="s")
    assert step.kind == "ESCALATION_PROPOSAL", step
    monkeypatch.setenv("URI_PROBE_MODE", probe)
    for k, v in extra_env: monkeypatch.setenv(k, v)
    t, tr = env.turn()
    res = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="s", turn_id=t, trace_id=tr)
    out = {"probe": probe, "after_run": res.kind, "verification": getattr(res, "verification_status", None),
           "relpaths": list(getattr(res, "relpaths", ()) or ())}
    if res.kind == "AWAITING_APPROVAL":
        t, tr = env.turn()
        done = env.session.approve_writeback(step.task_id, "approve", session_id="s", turn_id=t, trace_id=tr,
                                             run_id=res.run_id, relpaths=res.relpaths)
        out["after_approve"] = done.kind; out["reason"] = getattr(done, "reason", None)
    out["originals_changed"] = [n for n in before if sha(env.root / n) != before[n]]
    out["extra_files_in_root"] = sorted(p.name for p in env.root.iterdir() if p.name not in ("sales.xlsx", "report.py"))
    RESULTS[probe] = out; print(json.dumps(out))
    return env, out

def test_tamper_workbook_is_not_verified(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "tamper_workbook")
    assert out["after_run"] != "AWAITING_APPROVAL" and out["originals_changed"] == []

def test_extra_file_not_written_back(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "extra_file")
    assert "evil.py" not in out["extra_files_in_root"]
    assert out["after_run"] != "AWAITING_APPROVAL" or "evil.py" not in out["relpaths"]

def test_hardcoded_output_disclosed_limit(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "hardcode")
    # Expected per plan: structural checks only; record what happens (disclosed caveat).

def test_symlink_candidate(tmp_path, monkeypatch):
    target = tmp_path / "outside_target.py"
    env, out = run_flow(tmp_path, monkeypatch, "symlink_out", (("URI_PROBE_TARGET", str(target)),))
    rp = env.root / "report.py"
    out["original_is_symlink"] = rp.is_symlink()
    out["original_has_outside_marker"] = "OUTSIDE_CONTENT_MARKER" in rp.read_text()
    print(json.dumps(out))
    assert not rp.is_symlink()

def test_harness_writes_original_directly(tmp_path, monkeypatch):
    target = tmp_path / "authorized" / "report.py"
    env, out = run_flow(tmp_path, monkeypatch, "write_original", (("URI_PROBE_TARGET", str(target)),))
    # record; a concurrent change to the original must at least block write-back
    assert out.get("after_approve") != "COMPLETED" or "report.py" in out["originals_changed"]

def test_claim_text_does_not_verify(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "claim_verified_text")
    assert out["after_run"] == "HARNESS_FAILED" and out["originals_changed"] == []

def test_control_honest(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "honest_control")
    runs = list((env.runs).rglob("*.json"))
    print("RUNFILES", [str(p.relative_to(env.runs)) for p in runs][:10])
    for p in runs:
        t = p.read_text()
        if "stderr" in t or "safety" in t or "reason" in t: print("RUN", p.name, t[:1500])

def test_write_original_view(tmp_path, monkeypatch):
    from uri_v1.office import view
    target = tmp_path / "authorized" / "report.py"
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    env.session.adapter = ClaudeCodeAdapter((sys.executable, str(FAKE)), home=env.tmp / "home")
    make_workbook(env.root / "sales.xlsx", SALES); env.write("report.py", script_text(column="Amt"))
    raw = "make report.py work with sales.xlsx"; parsed = req.parse(raw); t, tr = env.turn()
    step = answer_asks(env, env.session.start(raw, session_id="s", turn_id=t, trace_id=tr, parsed=parsed), request_names(raw, parsed), session_id="s")
    monkeypatch.setenv("URI_PROBE_MODE", "write_original"); monkeypatch.setenv("URI_PROBE_TARGET", str(target))
    t, tr = env.turn()
    res = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="s", turn_id=t, trace_id=tr)
    print("VIEW_WRITE_ORIGINAL>>>", json.dumps({"kind": res.kind, "flags": list(getattr(res, "safety_flags", ()) or ()),
          "render": view.render(res) if hasattr(view, "render") else None, "original_tail": target.read_text()[-50:]}))

def test_hardcode_keeps_input_read(tmp_path, monkeypatch):
    env, out = run_flow(tmp_path, monkeypatch, "hardcode2")

def test_debug_hardcode(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    env.session.adapter = ClaudeCodeAdapter((sys.executable, str(FAKE)), home=env.tmp / "home")
    make_workbook(env.root / "sales.xlsx", SALES); env.write("report.py", script_text(column="Amt"))
    raw = "make report.py work with sales.xlsx"; parsed = req.parse(raw); t, tr = env.turn()
    step = answer_asks(env, env.session.start(raw, session_id="s", turn_id=t, trace_id=tr, parsed=parsed), request_names(raw, parsed), session_id="s")
    monkeypatch.setenv("URI_PROBE_MODE", "hardcode2"); t, tr = env.turn()
    res = env.session.confirm_escalation(step.task_id, "yes, run it", session_id="s", turn_id=t, trace_id=tr)
    print("DBG>>>", {k: v for k, v in vars(res).items() if k not in ("roles",)} if hasattr(res, "__dict__") else res)
    for p in sorted(env.tmp.rglob("*")):
        if p.is_file() and p.suffix in (".json", ".jsonl") and "run" in str(p): print("F", p, p.read_text()[:800])

@pytest.mark.parametrize("raw,answers", [
    ("make REPORT.PY work with SALES.XLSX", {"script": "REPORT.PY", "workbook": "SALES.XLSX"}),
    ("make ｒｅｐｏｒｔ.py work with sales.xlsx", {"script": "ｒｅｐｏｒｔ.py", "workbook": "sales.xlsx"}),
    ("make report.py work with sales.xlsx", {"script": "report.py ", "workbook": " sales.xlsx"}),
    ("make report.py work with sales.xlsx", {"script": "sales.xlsx", "workbook": "report.py"}),
    ("make report.py work with sales.xlsx", {"script": "report_old.py", "workbook": "sales.xlsx"}),
])
def test_case_and_width_variants(tmp_path, monkeypatch, raw, answers):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    env.write("report_old.py", script_text(column="amount"))
    parsed = req.parse(raw)
    out = {"raw": raw, "answers": answers, "parse_ok": parsed.ok, "parse_reason": getattr(parsed, "reason", None)}
    if parsed.ok:
        t, tr = env.turn()
        step = env.session.start(raw, session_id="s", turn_id=t, trace_id=tr, parsed=parsed)
        seen = []
        for _ in range(4):
            asks = [rb for rb in step.roles.values() if getattr(rb, "ask", False)] if step.kind == "CLARIFY" else []
            if not asks: break
            rb = asks[0]; seen.append(rb.ref_key); t, tr = env.turn()
            step = env.session.answer(step.task_id, answers[rb.ref_key], session_id="s", turn_id=t, trace_id=tr, round_id=rb.contract_id)
        out["asked"] = seen
        out["kind"] = step.kind; out["relpaths"] = list(getattr(step, "relpaths", ()) or ())
        head = env.log.load().task(step.task_id)
        ids = {l.source_id: l for l in env.sources.scan().locators}
        out["bound"] = sorted(str(getattr(ids.get(r["source_id"]), "relpath", r["source_id"])) for r in head.payload.get("references", []))
    print("CASEPROBE>>>", json.dumps(out, ensure_ascii=False))
