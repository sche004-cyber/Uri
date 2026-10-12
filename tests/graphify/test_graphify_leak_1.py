"""GRAPHIFY-LEAK-1: another user's memory pointers reached a user's Brain hint.

Every user's Graphify view was a copy of the shared index, whose `memory:` pointers come from the install's primary
user. Now each view takes its memory pointers only from its own user's memory store, read again on every lookup.
Drives the real server startup loader and _build_user_context with temporary paths. The leak cases fail on e07b71c6.
"""
import pytest

from uri_core.app import server
from uri_core.core.graphify_index import GraphifyIndex
from uri_core.core.user_memory import MemoryStore

USER_B = "2b8f6a1e-4c3d-4e5f-9a7b-1c2d3e4f5a6b"
USER_C = "7c1d2e3f-5a6b-4c7d-8e9f-0a1b2c3d4e5f"
PRIMARY_TEXT = "primary user's private preference text"


@pytest.fixture
def env(tmp_path, monkeypatch):
    primary = MemoryStore(storage_path=str(tmp_path / "primary" / "user_memory.json"))
    entry = primary.add(category="preference", content=PRIMARY_TEXT)
    monkeypatch.setattr(server, "_memory_store", primary)
    monkeypatch.setattr(server, "DEFAULT_INDEX_PATH", str(tmp_path / "graphify_index.json"))
    monkeypatch.setattr(server, "_USER_STATE_ROOT", str(tmp_path / "users"))
    monkeypatch.setattr(server, "_graphify_index", GraphifyIndex())
    monkeypatch.setattr(server.UriOrchestrator, "graphify_index", None, raising=False)
    old_view = getattr(server._orchestrator, "graphify_index", None)
    monkeypatch.setattr(server, "_user_contexts", {})
    server._GraphifyIndexLoader().start()
    yield {"primary": primary, "primary_key": f"memory:{entry.memory_id}"}
    server._orchestrator.graphify_index = old_view


def _view(user_id):
    return server._build_user_context(user_id).orchestrator.graphify_index


def _memory_keys(view):
    return {r["id"] for r in view.list_all() if r.get("kind") == "memory_pointer"}


def _hint_keys(view, text="what is my preference", limit=5):
    return {r["id"] for r in view.relevant_subset(text, limit=limit) if r.get("kind") == "memory_pointer"}


def test_the_shared_index_holds_the_primary_pointer(env):
    assert env["primary_key"] in server._graphify_index.records


def test_another_users_view_has_no_primary_pointer(env):
    view = _view(USER_B)
    assert env["primary_key"] not in view.records
    assert env["primary_key"] not in _memory_keys(view)
    assert view.get(env["primary_key"]) is None
    assert env["primary_key"] not in _hint_keys(view)
    assert env["primary_key"] not in _hint_keys(view, "preference user_provided", limit=500)
    assert PRIMARY_TEXT not in repr(view.records)


def test_a_users_own_memory_appears_even_when_added_after_the_view_was_built(env):
    ctx = server._build_user_context(USER_B)
    view = ctx.orchestrator.graphify_index
    assert _memory_keys(view) == set()
    own = ctx.memory_store.add(category="preference", content="b likes tea")
    assert _memory_keys(view) == {f"memory:{own.memory_id}"}
    assert f"memory:{own.memory_id}" in _hint_keys(view, "preference user_provided", limit=500)   # the scorer reads the fresh pointer
    assert view.get(f"memory:{own.memory_id}")["pointer"]["lookup_key"] == own.memory_id
    assert "b likes tea" not in repr(view.records)


def test_a_deleted_memory_leaves_the_view(env):
    ctx = server._build_user_context(USER_B)
    own = ctx.memory_store.add(category="preference", content="b likes tea")
    assert f"memory:{own.memory_id}" in _memory_keys(ctx.orchestrator.graphify_index)
    ctx.memory_store.delete(own.memory_id)
    assert _memory_keys(ctx.orchestrator.graphify_index) == set()


def test_two_users_never_see_each_others_pointers(env):
    ctx_b = server._build_user_context(USER_B)
    ctx_c = server._build_user_context(USER_C)
    b = ctx_b.memory_store.add(category="preference", content="b")
    c = ctx_c.memory_store.add(category="preference", content="c")
    assert _memory_keys(ctx_b.orchestrator.graphify_index) == {f"memory:{b.memory_id}"}
    assert _memory_keys(ctx_c.orchestrator.graphify_index) == {f"memory:{c.memory_id}"}


def test_a_users_view_never_changes_the_shared_index(env):
    ctx = server._build_user_context(USER_B)
    ctx.memory_store.add(category="preference", content="b")
    before = dict(server._graphify_index.records)
    _memory_keys(ctx.orchestrator.graphify_index)
    ctx.orchestrator.graphify_index.relevant_subset("preference")
    assert server._graphify_index.records == before


def test_other_scopes_are_still_shared(env):
    shared = {k for k in server._graphify_index.records if not k.startswith("memory:")}
    view = _view(USER_B)
    assert shared <= set(view.records)


def test_the_no_login_view_shows_its_own_store_and_stays_current(env):
    view = server._orchestrator.graphify_index
    assert env["primary_key"] in _memory_keys(view)
    later = env["primary"].add(category="preference", content="later")
    assert f"memory:{later.memory_id}" in _memory_keys(view)


def test_the_no_login_view_follows_a_replaced_store(env, tmp_path, monkeypatch):
    other = MemoryStore(storage_path=str(tmp_path / "other" / "user_memory.json"))
    o = other.add(category="preference", content="o")
    monkeypatch.setattr(server, "_memory_store", other)
    assert _memory_keys(server._orchestrator.graphify_index) == {f"memory:{o.memory_id}"}


def test_a_broken_memory_store_gives_no_pointers_and_no_error(env):
    class Broken:
        def list_all(self):
            raise OSError("disk gone")
    ctx = server._build_user_context(USER_B)
    ctx.orchestrator.graphify_index._memory_store_source = lambda: Broken()
    assert _memory_keys(ctx.orchestrator.graphify_index) == set()
    ctx.orchestrator.graphify_index._memory_store_source = lambda: (_ for _ in ()).throw(RuntimeError("x"))
    assert ctx.orchestrator.graphify_index.relevant_subset("preference") is not None


def test_the_brain_hint_for_another_user_has_no_primary_pointer(env):
    from uri_core.core.decision_engine import build_turn_state_and_directory
    ctx = server._build_user_context(USER_B)
    state, _ = build_turn_state_and_directory(orchestrator=ctx.orchestrator, session_id=None,
                                              user_text="preference user_provided", principal=None)
    assert env["primary_key"] not in repr(state)
