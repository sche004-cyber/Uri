"""Read-only adapters for existing context interfaces; no replacement resolvers."""
from dataclasses import asdict
import hashlib
import json
import subprocess
import sys
import time
import uuid

from uri_core.core.arn.integration import trigger_not_found_recovery
from uri_core.core.context_builder import build_task_context
from uri_core.core.graph_context import build_graph_context
from uri_core.core.graph_engine import graph_query
from uri_core.core.graphify_index import build_index
from uri_core.core.turn_state import assemble_turn_state
from uri_v1.memory.contracts import MemoryQuery
from uri_v1.memory.retrieval import Retriever
from uri_v1.memory.uri_adapter.envelope import MemoryAdapter, URIIntake
from uri_v1.turn.rar_deterministic import resolve_rar_deterministic_extended


class ExistingContext:
    def __init__(self, user_context, *, memory=None, bridge=None):
        self.user_context, self.memory, self.bridge = user_context, memory, bridge

    def __call__(self, user_id, session_id, text, record):
        started = time.perf_counter()
        core = self.user_context(user_id)
        brain = core.orchestrator
        history = getattr(brain, 'conversation_history', None)
        evidence, gaps, resolutions = [], [], []
        if history:
            # Read bounded transcripts from this user's existing store, including prior
            # sessions. The Brain decides relevance; a transcript is never authority.
            sessions = [session_id] + [item['session_id'] for item in history.list_sessions(limit=4)
                                       if item['session_id'] != session_id]
            for sid in sessions:
                turns = history.get_session(sid)
                for turn in turns[-8:] if sid == session_id else turns[-2:]:
                    digest = hashlib.sha256(json.dumps(turn, sort_keys=True).encode()).hexdigest()
                    identity = turn.get('turn_id') or digest
                    evidence.append(dict(id=f'history:{sid}:{identity}:{digest}', status='HISTORICAL',
                                         source=f'ConversationHistoryStore:{sid}:{identity}',
                                         sha256=digest, content=turn))
        index = build_index(skill_memory=getattr(brain, 'skill_memory', None),
                            memory_store=getattr(core, 'memory_store', None),
                            capability_directory=getattr(brain, 'capability_directory', None))
        hints = index.relevant_subset(text)
        expressions = record.get('reference_requests') or [text]
        graph_nodes = []
        for expression in expressions:
            if getattr(core, 'graph_store', None):
                graph_nodes.extend(graph_query(core.graph_store, name_contains=expression, limit=8))
            if self.memory:
                log, sources = self.memory(user_id)
                intake = URIIntake().capture(user_id, session_id, uuid.uuid4().hex, uuid.uuid4().hex,
                                            expression, spans={'file': (0, len(expression))})
                result = Retriever(log, sources).retrieve(MemoryQuery(user_id, session_id, expression, intake=intake))
                projection = MemoryAdapter(sources).project(result)
                for candidate in result.candidates:
                    evidence.append(dict(id='memory:' + candidate.source.source_id, status='SOURCE_CANDIDATE',
                                         source=candidate.locator, sha256=candidate.source.content_sha256,
                                         content=asdict(candidate.source)))
                if projection.query:
                    trace = resolve_rar_deterministic_extended(projection.query)
                    resolutions.append(asdict(trace.resolution))
                else:
                    gaps.append('Memory/RAR projection unavailable: ' + str(projection.degraded))
                if not result.candidates:
                    recovery = trigger_not_found_recovery(goal=record['request'], source='URI-Memory', query=expression, result=[])
                    resolutions.append({'arn_recovery': recovery.to_dict() if hasattr(recovery, 'to_dict') else asdict(recovery)})
        for number, node in enumerate(graph_nodes[:16]):
            evidence.append(dict(id=f'graph:{number}', status='GRAPH_RECORD', source='GraphStore', content=node))
        if self.bridge:
            try:
                evidence.extend(self.bridge())
            except (OSError, ValueError, subprocess.SubprocessError):
                gaps.append('Context Bridge freshness/retrieval unavailable; no checkpoint facts assumed.')
        else:
            gaps.append('Context Bridge not enabled in this composition.')
        # Retain prior context as explicitly historical, never silently reaffirm it.
        known = {item['id'] for item in evidence}
        for item in record.get('context', {}).get('evidence', []):
            if item['id'] not in known:
                evidence.append({**item, 'status': 'PREVIOUS_RETRIEVAL_NOT_REVALIDATED'})
        graph = build_graph_context(entities=graph_nodes[:16])
        turn = assemble_turn_state(user_text=text, session_id=session_id, conversation_history_store=history,
                                   graph_context=graph, capability_index_hint=hints).data
        facts = {'request': record['request'], 'user_answers': record['answers'], 'user_corrections': record['corrections']}
        return dict(evidence=list({e['id']: e for e in evidence}.values())[:64],
                    turn_state=turn, task_context=build_task_context('intent_preparation', facts, {}),
                    reference_resolutions=resolutions, unavailable=gaps,
                    context_duration_ms=round((time.perf_counter() - started) * 1000, 2),
                    edge_latency_ms=None, edge_note='No specialist qualified for general intent has been selected.')


def bridge_source(directory):
    """Operator-selected experiment only; no client-supplied paths or executor invocation."""
    script = directory / 'context_bridge.py'
    def retrieve():
        def call(*args):
            proc = subprocess.run([sys.executable, str(script), 'capsule', *args], cwd=directory,
                                  capture_output=True, text=True, encoding='utf8', timeout=30, check=True)
            return json.loads(proc.stdout)
        if call('verify').get('fresh') is not True:
            raise ValueError('BRIDGE_STALE')
        evidence = []
        for cid in ('C1', 'C2', 'C3', 'C4', 'C5', 'C6', 'C7'):
            for number, item in enumerate(call('show', '--claim', cid)['evidence']):
                evidence.append(dict(id=f'bridge:{cid}:{number}', status='HASH_BOUND_SOURCE_EXCERPT',
                                     source=f"{item['path']}:{item['line_start']}", sha256=item['sha256'],
                                     content=item['excerpt']))
        return evidence
    return retrieve
