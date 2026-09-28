"""Process-start wiring for the Office demonstrator (M39 §4.2 bootstrap.py).

Builds a real M36 log/sources/recorder, S11 ledger, run store, M37 Edge
service and (optionally) an M38 harness runner + real Claude Code adapter, all
under one user-scoped root, and freezes the trusted verifier bootstrap once
(M37's `verifier_entries` plus this package's write-back verifier).

SAFETY NOTE (disclosed, not fixed here): the real harness path this module can
build (`build_session(..., with_harness=True)`) depends on M38's
`ClaudeCodeAdapter`/`HarnessRunner`, which currently has an open, unrepaired
containment/secret-isolation defect (see `flow.py` module docstring and
`docs/plans/M39_IMPLEMENTATION_REPORT.md`). `build_session` still constructs
it (the plan needs the wiring to exist for the future live smoke, Q-O3), but
callers must not point it at real user files or a real API key until that
defect is repaired and re-qualified. `with_harness=False` (the default) never
constructs it.
"""
from __future__ import annotations

from pathlib import Path
import uuid

from uri_v1.edge.local_runner import LocalRunner, verifier_entries
from uri_v1.edge.registry import default_registry
from uri_v1.edge.service import EdgeService, EdgeTelemetry
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.execution.harness.runner import HarnessRunner
from uri_v1.execution.run_record import RunStore
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers
from uri_v1.memory.retrieval import Retriever
from uri_v1.memory.sources import SourceRegistry
from uri_v1.results.version_ledger import ResultVersionLedger

from .flow import OfficeSession
from .writeback import writeback_verifier_entry

_VERIFIERS_FROZEN = False


def _freeze_verifiers(run_root, *, python=None):
    global _VERIFIERS_FROZEN
    if _VERIFIERS_FROZEN:
        return
    entries = dict(verifier_entries(run_root, python=python))
    entries.update(writeback_verifier_entry())
    _bootstrap_verifiers(entries)
    _VERIFIERS_FROZEN = True


def build_session(user_id: str, data_dir, *, authorized_root, with_harness: bool = False,
                  harness_home=None, harness_executable="claude") -> OfficeSession:
    """`data_dir` is a private per-user application data directory (never the
    user's own document root). `authorized_root` is the one folder this run is
    authorized to read/write documents in (M36 `SourceRegistry.register`)."""
    data_dir = Path(data_dir)
    scratch_root = data_dir / "scratch"
    runs_root = data_dir / "runs"
    telemetry_root = data_dir / "edge"
    for d in (data_dir, scratch_root, runs_root, telemetry_root):
        d.mkdir(parents=True, exist_ok=True)

    log = MemoryLog(user_id, data_dir / "private")
    sources = SourceRegistry(log)
    sources.register(Path(authorized_root))
    recorder = Recorder(log, sources)
    retriever = Retriever(log, sources)

    _freeze_verifiers(runs_root)
    store = RunStore(user_id, runs_root)
    ledger = ResultVersionLedger(user_id, root=str(data_dir / "results"))
    runner = LocalRunner(user_id=user_id, scratch_root=scratch_root, run_store=store, recorder=recorder,
                         ledger=ledger, sources=sources)
    telemetry = EdgeTelemetry(user_id, telemetry_root)
    edge = EdgeService(registry=default_registry(), sources=sources, runner=runner, telemetry=telemetry)

    harness_runner = adapter = None
    if with_harness:
        harness_runner = HarnessRunner(user_id=user_id, scratch_root=scratch_root, run_store=store, recorder=recorder,
                                       ledger=ledger, sources=sources)
        adapter = ClaudeCodeAdapter(harness_executable, home=Path(harness_home or Path.home()))

    return OfficeSession(log=log, sources=sources, recorder=recorder, retriever=retriever, edge=edge,
                         scratch_root=scratch_root, user_id=user_id, harness_runner=harness_runner, adapter=adapter)


def new_user_id() -> str:
    return str(uuid.uuid4())
