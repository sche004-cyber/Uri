"""GRF-P0-1: the paired (working-system) preparation path applies the same Graphify hint rule as the canonical
decision path (`decision_engine`): the GRAPHIFY_HINT_ENABLED killswitch, only skill/memory_pointer orientation
records, and no hint (never an error) when the index fails.

Pure unit tests: the index, Turn State assembly and decision request builders are replaced by recorders, so no
runtime, provider or store is touched.
"""
from types import SimpleNamespace

import pytest

import uri_core.core.decision_engine as decision_engine
import uri_core.core.graphify_index as graphify_index
import uri_core.core.turn_state as turn_state
from uri_core.core.paired_reasoning import prepare_canonical_context

RECORDS = [
    {"id": "capability:gmail_search", "kind": "capability", "label": "Search Gmail"},
    {"id": "skill:lesson_plan", "kind": "skill", "label": "Lesson plan"},
    {"id": "workflow:weekly_report", "kind": "workflow", "label": "Weekly report"},
    {"id": "memory:m1", "kind": "memory_pointer", "label": "Teaches science"},
    {"id": "service:gmail", "kind": "connected_service", "label": "Gmail"},
]


class FakeIndex:
    def __init__(self, records=None, error=None):
        self.records = {r["id"]: r for r in (records or [])}
        self._subset = list(records or [])
        self.error = error
        self.calls = []

    def relevant_subset(self, goal_text, limit=5):
        self.calls.append((goal_text, limit))
        if self.error:
            raise self.error
        return list(self._subset)


@pytest.fixture
def run(monkeypatch):
    captured = {}

    def fake_assemble(**kw):
        captured.update(kw)
        return SimpleNamespace(data={"user_text": kw["user_text"]})

    monkeypatch.setattr(turn_state, "assemble_turn_state", fake_assemble)
    monkeypatch.setattr(decision_engine, "preselect_candidate_ids", lambda data, directory: [])
    monkeypatch.setattr(decision_engine, "build_decision_request", lambda data, **kw: {"goal": data["user_text"]})

    def go(index):
        monkeypatch.setattr(graphify_index, "build_index", lambda **kw: index)
        binding = SimpleNamespace(server_id="srv", client_id="cli", principal_id="u1", session_id="s1")
        ports = SimpleNamespace(binding=binding,
                                read=lambda store, method, sid: None if store == "sessions" else [])
        request = SimpleNamespace(principal_id="u1", server_id="srv", client_id="cli", session_id="s1",
                                  text="plan a science lesson",
                                  reasoning=SimpleNamespace(provider="p", model="m", model_dump=lambda: {}))
        prepared = prepare_canonical_context(ports, request, SimpleNamespace(user_id="u1"), [])
        return prepared, captured["capability_index_hint"]

    return go


def test_enabled_by_default_and_only_skill_and_memory_records_pass(run, monkeypatch):
    monkeypatch.delenv("GRAPHIFY_HINT_ENABLED", raising=False)
    index = FakeIndex(RECORDS)
    prepared, hint = run(index)
    assert [r["id"] for r in hint] == ["skill:lesson_plan", "memory:m1"]
    assert index.calls == [("plan a science lesson", 5)]
    assert prepared["graphify"] is index          # the index itself is still returned (compatibility)


def test_explicitly_enabled(run, monkeypatch):
    monkeypatch.setenv("GRAPHIFY_HINT_ENABLED", "1")
    _, hint = run(FakeIndex(RECORDS))
    assert {r["kind"] for r in hint} == {"skill", "memory_pointer"}


def test_killswitch_disables_the_hint_and_the_index_is_not_queried(run, monkeypatch):
    monkeypatch.setenv("GRAPHIFY_HINT_ENABLED", "0")
    index = FakeIndex(RECORDS)
    _, hint = run(index)
    assert hint is None
    assert index.calls == []


@pytest.mark.parametrize("kinds", [["capability"], ["capability", "workflow", "connected_service"], []])
def test_rejected_kinds_never_reach_the_brain(run, monkeypatch, kinds):
    monkeypatch.delenv("GRAPHIFY_HINT_ENABLED", raising=False)
    _, hint = run(FakeIndex([r for r in RECORDS if r["kind"] in kinds]))
    assert hint is None                           # None: Turn State reports the hint as unavailable, not empty


def test_a_failing_index_gives_no_hint_and_no_error(run, monkeypatch):
    monkeypatch.delenv("GRAPHIFY_HINT_ENABLED", raising=False)
    _, hint = run(FakeIndex(RECORDS, error=RuntimeError("index broken")))
    assert hint is None


def test_a_malformed_record_gives_no_hint_and_no_error(run, monkeypatch):
    monkeypatch.delenv("GRAPHIFY_HINT_ENABLED", raising=False)
    index = FakeIndex(RECORDS)
    index._subset = ["not-a-record", RECORDS[1]]
    _, hint = run(index)
    assert hint is None


def test_same_rule_as_the_canonical_decision_path(monkeypatch):
    """The canonical path's filter (decision_engine) and the paired path keep identical kinds."""
    import inspect
    canonical_src = inspect.getsource(decision_engine)
    import uri_core.core.paired_reasoning as paired
    paired_src = inspect.getsource(paired)
    assert 'r.get("kind") in ("skill", "memory_pointer")' in canonical_src
    assert 'r.get("kind") in ("skill", "memory_pointer")' in paired_src
    assert "graphify_hint_enabled()" in paired_src
