"""Reproduction (read-only, scratch): does user B's per-user Graphify view carry the primary user's memory pointers,
and can they reach user B's Brain hint? Drives the real server.py startup loader and _build_user_context."""
import os
from uri_core.app import server
from uri_core.core.user_memory import MemoryStore
from uri_core.core.graphify_index import GraphifyIndex


def test_primary_users_memory_pointers_reach_another_users_view(tmp_path, monkeypatch):
    primary = MemoryStore(storage_path=str(tmp_path / "primary" / "user_memory.json"))
    entry = primary.add(category="preference", content="primary user's private preference text")
    monkeypatch.setattr(server, "_memory_store", primary)
    monkeypatch.setattr(server, "DEFAULT_INDEX_PATH", str(tmp_path / "graphify_index.json"))
    monkeypatch.setattr(server, "_USER_STATE_ROOT", str(tmp_path / "users"))
    server._GraphifyIndexLoader().start()
    assert f"memory:{entry.memory_id}" in server._graphify_index.records          # global index has it
    ctx = server._build_user_context("2b8f6a1e-4c3d-4e5f-9a7b-1c2d3e4f5a6b")
    orch = getattr(ctx, "orchestrator", None)
    view = orch.graphify_index
    assert isinstance(view, GraphifyIndex)
    leaked = [k for k in view.records if k == f"memory:{entry.memory_id}"]
    rec = view.records.get(f"memory:{entry.memory_id}")
    print("USER_B_VIEW_HAS_PRIMARY_POINTER", bool(leaked), rec and {k: rec.get(k) for k in ("kind", "summary", "pointer")})
    subset = view.relevant_subset("what is my preference", limit=5)
    hint = [r for r in subset if r.get("kind") in ("skill", "memory_pointer")]
    print("HINT_FOR_USER_B", [(r.get("entry_id") or r.get("id"), r.get("summary")) for r in hint])
    assert "primary user's private preference text" not in repr(view.records)   # content never copied
