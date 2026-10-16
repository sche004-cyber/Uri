"""Approval generalization (plan §5.1): migration of an M1/M2 database, plan and output cards bound by hash, replay
and cross-key refusals, A2UI action registry parity with the Dart mirror, and the no-overwrite output writer."""
import errno
import json
import re
import sqlite3
from pathlib import Path

import pytest

from uri_a2ui import actions as A
from uri_office import safe_write
from uri_office.approvals import Approvals
from uri_office.errors import OfficeError

ROOT = Path(__file__).resolve().parents[2]
PLAN = {"capability": "save_as_pdf", "title": "Save letter.docx as PDF?",
        "steps": [{"id": "convert", "kind": "E", "label": "Convert"}],
        "inputs": [{"name": "letter.docx", "kind": "docx", "sha256": "a" * 64}],
        "outputs": [{"name": "letter.pdf", "kind": "pdf"}]}


def action(surface, button, name, key):
    msgs = surface.messages()
    bound = msgs[2]["updateDataModel"]["value"]["bound"]
    return {"name": name, "surfaceId": surface.surface_id, "sourceComponentId": button,
            "context": {"surface_digest": bound["surface"]["digest"], key: bound[key]}}


def test_m1_database_migrates_and_chain_still_verifies(tmp_path):
    db = sqlite3.connect(str(tmp_path / "office.db"))
    db.executescript("""
CREATE TABLE surface(surface_id TEXT PRIMARY KEY, owner TEXT NOT NULL, workbook_id TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('OPEN','CLOSED')), record_json TEXT NOT NULL, body_json TEXT NOT NULL,
  change_sha256 TEXT NOT NULL, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE event(seq INTEGER PRIMARY KEY AUTOINCREMENT, at REAL NOT NULL, kind TEXT NOT NULL,
  payload_json TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
INSERT INTO surface VALUES ('old','owner','wb1','CLOSED','{}','{}','x',1,1);""")
    db.commit()
    db.close()
    a = Approvals(tmp_path, "owner")
    a.audit("office.opened", {"workbook_id": "wb1"})
    row = a.db.execute("SELECT subject_kind FROM surface WHERE surface_id='old'").fetchone()
    assert row[0] == "workbook"
    a2 = Approvals(tmp_path, "owner")                       # second start: no second ALTER
    assert a2.verify_chain()["ok"]


def test_plan_card_runs_once_and_refuses_cross_key(tmp_path):
    a = Approvals(tmp_path, "owner")
    s = a.propose_plan("w" * 20, PLAN)
    seen = []
    r = a.action(action(s, "apply", "office.run_plan", "plan_sha256"), lambda body: seen.append(body) or {"ok": 1})
    assert r["status"] == "applied" and r["subject_kind"] == "plan" and seen[0]["plan"] == PLAN
    with pytest.raises(OfficeError) as e:                    # replay
        a.action(action(s, "apply", "office.run_plan", "plan_sha256"), lambda body: {})
    assert e.value.code == "UNKNOWN_SURFACE"
    assert a.verify_chain()["ok"]


def test_plan_hash_cannot_be_used_with_change_actions(tmp_path):
    a = Approvals(tmp_path, "owner")
    s = a.propose_plan("w" * 20, PLAN)
    msg = action(s, "apply", "office.run_plan", "plan_sha256")
    msg["name"] = "office.apply_change"
    with pytest.raises(OfficeError):
        a.action(msg, lambda body: {})


def test_tampered_plan_body_is_refused(tmp_path):
    a = Approvals(tmp_path, "owner")
    s = a.propose_plan("w" * 20, PLAN)
    body = json.loads(a.db.execute("SELECT body_json FROM surface").fetchone()[0])
    body["plan"]["outputs"][0]["name"] = "evil.pdf"
    a.db.execute("UPDATE surface SET body_json=?", (json.dumps(body),))
    with pytest.raises(OfficeError) as e:
        a.action(action(s, "apply", "office.run_plan", "plan_sha256"), lambda body: {})
    assert e.value.code == "CHANGE_MISMATCH"


def test_output_card_binds_destination_and_warnings(tmp_path):
    a = Approvals(tmp_path, "owner")
    out = [{"name": "letter.pdf", "sha256": "b" * 64, "pages": 2, "size": 1000}]
    s = a.propose_outputs("w" * 20, out, r"C:\Users\me\letter.pdf", [{"id": "f-1", "message": "Page 2 is blank."}],
                          True)
    text = json.dumps(s.messages())
    assert "letter.pdf" in text and "Page 2 is blank." in text and "never replaced" in text
    r = a.action(action(s, "reject", "office.reject_change", "change_sha256"), lambda body: {})
    assert r["status"] == "declined" and r["subject_kind"] == "output_files"


def test_new_actions_are_registered_and_mirrored_in_dart():
    dart = (ROOT / "uri_ui" / "lib" / "living" / "a2ui" / "a2ui_contract.dart").read_text(encoding="utf-8")
    block = dart[dart.index("const a2uiActions"):dart.index("};", dart.index("const a2uiActions"))]
    dart_names = set(re.findall(r"^\s*'([a-z_.]+)': \{", block, re.M))
    assert dart_names == set(A.ACTIONS)
    for name in ("office.run_plan", "office.discard_plan"):
        assert A.ACTIONS[name]["context"] == {"plan_sha256": "sha256"} and A.ACTIONS[name]["confirms"]


def test_no_second_a2ui_hub_brain_client_or_approval_store():
    """U16 (refinement 10): O2 files add no new Brain client, A2UI renderer/hub or approval store."""
    o2 = ("capabilities", "contracts", "content", "docs", "engine_hub", "engines", "intent", "jobobject", "recent",
          "render", "safe_write", "sanitize", "validate", "workerproc", "workflows")
    files = [ROOT / "uri_office" / f"{n}.py" for n in o2] + list((ROOT / "uri_office" / "workers").glob("*.py"))
    for p in files:
        t = p.read_text(encoding="utf-8")
        assert "brain_client" not in t, p
        assert "sqlite3" not in t, p
        assert "A2uiHub" not in t, p


# ---- safe_write ------------------------------------------------------------------------------------------------
def test_publish_copy_never_replaces_and_checks_hash(tmp_path):
    import hashlib
    src = tmp_path / "o.pdf"
    src.write_bytes(b"%PDF-data")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    dest = tmp_path / "out" / "o.pdf"
    dest.parent.mkdir()
    assert safe_write.publish_copy(src, dest, sha)["saved_to"] == "o.pdf"
    with pytest.raises(OfficeError) as e:
        safe_write.publish_copy(src, dest, sha)
    assert e.value.code == "DESTINATION_EXISTS"
    with pytest.raises(OfficeError) as e:
        safe_write.publish_copy(src, tmp_path / "out" / "x.pdf", "0" * 64)
    assert e.value.code == "TARGET_CHANGED" and not (tmp_path / "out" / "x.pdf").exists()
    assert sorted(p.name for p in dest.parent.iterdir()) == ["o.pdf"]


def test_publish_copy_disk_full_leaves_nothing(tmp_path, monkeypatch):
    """Fault injection (simulated ENOSPC), not a real full disk."""
    import hashlib
    src = tmp_path / "o.pdf"
    src.write_bytes(b"%PDF-data")
    sha = hashlib.sha256(src.read_bytes()).hexdigest()
    real = safe_write.os.fsync

    def full(fd):
        raise OSError(errno.ENOSPC, "No space left on device")
    monkeypatch.setattr(safe_write.os, "fsync", full)
    with pytest.raises(OfficeError) as e:
        safe_write.publish_copy(src, tmp_path / "d.pdf", sha)
    monkeypatch.setattr(safe_write.os, "fsync", real)
    assert e.value.code == "DISK_FULL"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["o.pdf"]
