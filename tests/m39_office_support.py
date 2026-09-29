"""Shared fixtures for M39 office tests: real files, real M36/M37/M38 stores, fake harness."""
from __future__ import annotations

from pathlib import Path
import sys
import uuid

import uri_v1.memory.recorder as memory_recorder
from uri_v1.edge.local_runner import LocalRunner, verifier_entries
from uri_v1.edge.registry import CapabilityRegistry
from uri_v1.edge.service import EdgeService, EdgeTelemetry
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.execution.harness.runner import HarnessRunner
from uri_v1.execution.run_record import RunStore
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers
from uri_v1.memory.retrieval import Retriever
from uri_v1.memory.sources import SourceRegistry
from uri_v1.results.version_ledger import ResultVersionLedger
from uri_v1.office.flow import OfficeSession
from uri_v1.office.writeback import writeback_verifier_entry
from tests.m37_edge_support import make_workbook, script, SALES  # noqa: F401  (re-exported for tests)

USER = str(uuid.UUID(int=9))
ROOT = Path(__file__).resolve().parents[1]
FAKE = ROOT / "fixtures" / "m39_office" / "fake_claude_office.py"


class OfficeEnv:
    """Real M36/M37 stores + Office wiring in temporary roots, for one test."""

    def __init__(self, tmp: Path, monkeypatch, *, with_harness=True, user=USER):
        self.tmp = tmp
        tmp.mkdir(parents=True, exist_ok=True)
        self.root = tmp / "authorized"; self.root.mkdir(exist_ok=True)
        self.scratch = tmp / "scratch"; self.runs = tmp / "runs"
        self.user = user
        self.log = MemoryLog(self.user, tmp / "private")
        self.sources = SourceRegistry(self.log); self.sources.register(self.root)
        self.recorder = Recorder(self.log, self.sources)
        self.retriever = Retriever(self.log, self.sources)
        self.ledger = ResultVersionLedger(self.user, root=str(tmp / "results"))
        self.store = RunStore(self.user, self.runs)
        monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
        entries = dict(verifier_entries(self.runs))
        entries.update(writeback_verifier_entry())
        _bootstrap_verifiers(entries)
        self.registry = CapabilityRegistry(None, qualification_run=True)
        self.runner = LocalRunner(user_id=self.user, scratch_root=self.scratch, run_store=self.store,
                                  recorder=self.recorder, ledger=self.ledger, sources=self.sources)
        self.telemetry = EdgeTelemetry(self.user, tmp / "telemetry")
        self.edge = EdgeService(registry=self.registry, sources=self.sources, runner=self.runner, telemetry=self.telemetry)
        self.harness_runner = self.adapter = None
        if with_harness:
            self.harness_runner = HarnessRunner(user_id=self.user, scratch_root=self.scratch, run_store=self.store,
                                                recorder=self.recorder, ledger=self.ledger, sources=self.sources)
            home = tmp / "home"; home.mkdir(exist_ok=True)
            self.adapter = fake_adapter(home)
        self.session = OfficeSession(log=self.log, sources=self.sources, recorder=self.recorder,
                                     retriever=self.retriever, edge=self.edge, scratch_root=self.scratch,
                                     user_id=self.user, run_store=self.store,
                                     harness_runner=self.harness_runner, adapter=self.adapter)

    def write(self, name, data) -> Path:
        p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
        return p

    def turn(self):
        return uuid.uuid4().hex, uuid.uuid4().hex


def fake_adapter(home: Path, **kw) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter((sys.executable, str(FAKE)), home=home, **kw)


def answer_asks(env, step, names: dict, *, session_id):
    """Answer M39's per-file questions (re-audit R2-1, repair round 3) with the
    given file names, one fresh turn per role, and return the final step.

    On the frozen M36 line a request naming both files cannot bind either one
    in its own turn (frozen `affirmative_around`), so the flow asks for each
    file separately. Only asks are answered here; a Memory clarification
    round or any other step is returned unchanged."""
    while step.kind == "CLARIFY":
        asks = [rb for rb in step.roles.values() if getattr(rb, "ask", False)]
        if not asks:
            return step
        rb = asks[0]
        turn_id, trace_id = env.turn()
        step = env.session.answer(step.task_id, names[rb.ref_key], session_id=session_id, turn_id=turn_id,
                                  trace_id=trace_id, round_id=rb.contract_id)
    return step


def request_names(raw, parsed) -> dict:
    """The file names the request itself used for each role (its parsed spans)."""
    return {role: raw[a:b] for role, (a, b) in parsed.spans.items()}
