"""GRAPHIFY-LEAK-1 review repairs.

R1-01: the placeholder Google modules and the throwaway credential secret used by tests/graphify must not reach any
later test in the same pytest run (checked in a child pytest run: graphify tests first, then a probe).
R1-02: a user's Graphify view is shared by concurrent requests. A lookup must not edit the records another lookup or
the capability refresh is reading, and must never raise. Each race is made deterministic: a record's .get("summary")
(read by the relevance scorer while it iterates the records) starts the competing call in another thread and waits
until it has finished or is waiting for the view's lock. Before the repair the competing call changed the dict mid-iteration and the hint came back empty.
"""
import importlib
import os
import subprocess
import sys
import textwrap
import threading
import time
from pathlib import Path

import pytest

from uri_core.core.graphify_index import GraphifyIndex
from uri_core.core.user_memory import MemoryStore

REPO = Path(__file__).resolve().parents[2]
USER_B = "2b8f6a1e-4c3d-4e5f-9a7b-1c2d3e4f5a6b"
HINT_TEXT = "preference user_provided"


@pytest.fixture(scope="module")
def server(request):
    try:
        return request.getfixturevalue("graphify_server")
    except pytest.FixtureLookupError:      # older conftest: it imported the server at collection
        return importlib.import_module("uri_core.app.server")


@pytest.fixture
def ctx(server, tmp_path, monkeypatch):
    primary = MemoryStore(storage_path=str(tmp_path / "primary" / "user_memory.json"))
    primary.add(category="preference", content="primary")
    monkeypatch.setattr(server, "_memory_store", primary)
    monkeypatch.setattr(server, "DEFAULT_INDEX_PATH", str(tmp_path / "graphify_index.json"))
    monkeypatch.setattr(server, "_USER_STATE_ROOT", str(tmp_path / "users"))
    monkeypatch.setattr(server, "_graphify_index", GraphifyIndex())
    old_view = getattr(server._orchestrator, "graphify_index", None)
    monkeypatch.setattr(server, "_user_contexts", {})
    server._GraphifyIndexLoader().start()
    context = server._build_user_context(USER_B)
    yield context
    server._orchestrator.graphify_index = old_view


class _RaceRecord(dict):
    """A skill record that runs `action` once, on the scorer's second pass over the records (the first pass only
    counts term frequencies and tolerates an error; an error in the second pass empties the hint)."""

    def __init__(self, action):
        super().__init__(id="skill:race", kind="skill", summary="unrelated", dependencies=[])
        self.action = action
        self.summary_reads = 0

    def get(self, key, default=None):
        if key == "summary":
            self.summary_reads += 1
            if self.summary_reads == 2 and self.action is not None:
                action, self.action = self.action, None
                action()
        return super().get(key, default)


class _WatchedLock:
    """Stands in for the view's lock and records when another thread waits for it. Views without a lock ignore it."""

    def __init__(self):
        self._lock = threading.RLock()
        self._owner = threading.get_ident()
        self.contended = threading.Event()

    def __enter__(self):
        if threading.get_ident() != self._owner:
            self.contended.set()
        self._lock.acquire()
        return self

    def __exit__(self, *exc):
        self._lock.release()
        return False


def _in_thread(fn, outcome, lock):
    """Runs fn in another thread and returns once it has finished or is waiting for the view's lock."""
    def run():
        try:
            outcome["result"] = fn()
        except BaseException as exc:   # recorded and asserted on below
            outcome["error"] = exc
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 60
    while thread.is_alive() and not lock.contended.is_set() and time.monotonic() < deadline:
        time.sleep(0.005)
    return thread


def _memory_hint(view):
    return {r["id"] for r in view.relevant_subset(HINT_TEXT, limit=500) if r.get("kind") == "memory_pointer"}


def test_a_concurrent_lookup_does_not_break_a_running_lookup(ctx):
    view = ctx.orchestrator.graphify_index
    first = ctx.memory_store.add(category="preference", content="first")
    assert _memory_hint(view) == {f"memory:{first.memory_id}"}
    outcome, threads, lock = {}, [], _WatchedLock()
    view.lock = lock

    def concurrent_lookup():
        ctx.memory_store.add(category="preference", content="second")
        threads.append(_in_thread(lambda: {r["id"] for r in view.list_all() if r.get("kind") == "memory_pointer"},
                                  outcome, lock))

    view.records["skill:race"] = _RaceRecord(concurrent_lookup)
    hint = _memory_hint(view)
    threads[0].join(timeout=60)
    assert f"memory:{first.memory_id}" in hint
    assert "error" not in outcome
    assert len(outcome["result"]) == 2


def test_the_capability_refresh_does_not_break_a_running_lookup(ctx, server):
    view = ctx.orchestrator.graphify_index
    own = ctx.memory_store.add(category="preference", content="own")
    for i in range(40):     # stale capability records the refresh drops, so the record count must change
        view.records[f"capability:stale-{i}"] = {"id": f"capability:stale-{i}", "kind": "capability",
                                                  "summary": "stale", "dependencies": []}
    previous_dispatch = ctx.orchestrator.multi_action_dispatch
    outcome, threads, lock = {}, [], _WatchedLock()
    view.lock = lock

    def concurrent_refresh():
        threads.append(_in_thread(lambda: server.refresh_user_external_lifecycle(USER_B, context=ctx), outcome, lock))

    view.records["skill:race"] = _RaceRecord(concurrent_refresh)
    hint = _memory_hint(view)
    threads[0].join(timeout=60)
    assert f"memory:{own.memory_id}" in hint
    assert "error" not in outcome, repr(outcome.get("error"))
    assert ctx.orchestrator.multi_action_dispatch is not previous_dispatch
    assert not any(k.startswith("capability:stale-") for k in view.records)


def test_a_lookup_never_raises_when_the_memory_store_misbehaves(ctx):
    view = ctx.orchestrator.graphify_index
    others = {k for k in view.records if not k.startswith("memory:")}

    class Garbled:
        def list_all(self):
            return 42      # not iterable: indexing the pointers fails

    view._memory_store_source = lambda: Garbled()
    assert view.get("memory:anything") is None
    assert isinstance(view.list_all(), list)
    assert view.relevant_subset("preference") is not None
    assert others <= set(view.records)


_PROBE = '''
import os
import sys
import types
from unittest import mock


def test_nothing_from_the_graphify_placeholders_survives():
    bad = []
    for name, module in list(sys.modules.items()):
        if isinstance(module, mock.MagicMock):
            bad.append(name)
            continue
        if not name.startswith("uri_core"):
            continue
        for attr, value in list(vars(module).items()):
            if isinstance(value, mock.MagicMock):
                bad.append(f"{name}.{attr}")
            elif (isinstance(value, types.ModuleType) and value.__name__.startswith("uri_core")
                  and sys.modules.get(value.__name__) is not value):
                bad.append(f"{name}.{attr} (stale module)")
    assert not bad, bad
    assert "URI_EXTERNAL_CREDENTIAL_SECRET" not in os.environ
'''


def test_graphify_placeholders_do_not_reach_later_tests(tmp_path):
    probe = tmp_path / "test_zz_probe.py"
    probe.write_text(textwrap.dedent(_PROBE))
    env = {k: v for k, v in os.environ.items() if k != "URI_EXTERNAL_CREDENTIAL_SECRET"}
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--rootdir", str(REPO),
         "tests/graphify/test_graphify_leak_1.py", str(probe)],
        cwd=REPO, env=env, capture_output=True, text=True, timeout=600,
    )
    assert run.returncode == 0, run.stdout[-4000:] + run.stderr[-2000:]
    assert "passed" in run.stdout and "failed" not in run.stdout
