"""Protocol/interface tests with scripted Brain proposals, not semantic qualification."""
from copy import deepcopy
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from experimental.intent_workflow.controller import IntentController
from experimental.intent_workflow.context import ExistingContext
from experimental.intent_workflow.routes import router_for
from uri_core.core.conversation_history import ConversationHistoryStore
from uri_core.core.graph_store import GraphStore
from uri_core.core.model_reasoning_gateway import ModelReasoningGateway
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.sources import SourceRegistry


def proposal(*, level='C', clear=True, question=None):
    result = {'intent': dict(objective='Complete the selected console', expected_outcome='A reviewable result',
        scope_in=['Selected console'], scope_out=['Production promotion'], constraints=['Preserve frozen sources'],
        assumptions=['The recovered console identity still applies'], acceptance_checks=['User-visible result matches request'],
        uncertainty=[] if clear else ['Target version is uncertain'], context_ids=['decision:1'],
        level=level, higher_reasoning=level == 'C', consequential=False, harness_requested=False,
        sufficiently_understood=clear)}
    if question:
        result['clarification'] = dict(question=question, question_key=question)
    return result


class ScriptedBrain:
    def __init__(self, values):
        self.values, self.requests = list(values), []
    def __call__(self, request):
        self.requests.append(json.loads(request))
        return deepcopy(self.values.pop(0))


def controller(tmp_path, values):
    brain = ScriptedBrain(values)
    def context(user, session, text, record):
        return {'evidence': [{'id': 'decision:1', 'source': 'decision.txt:1', 'status': 'HISTORICAL',
                              'content': 'The previous console was DesktopHarnessTest'}]}
    service = IntentController(tmp_path / 'intent', context=context,
        reasoner=lambda user: ModelReasoningGateway(model_callable=brain),
        executors=lambda user: [{'id': 'codex', 'installed': True, 'eligible': False}])
    return service, brain


def test_clear_simple_does_not_require_audit(tmp_path):
    service, _ = controller(tmp_path, [proposal(level='A')])
    state = service.begin('alice', 'chat', 'Open the folder')
    assert state['status'] == 'READY' and state['questions_asked'] == 0
    assert not state['execution_authorized']


def test_context_precedes_reasoning_and_clear_complex_requires_audit(tmp_path):
    service, brain = controller(tmp_path, [proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    assert state['status'] == 'AUDIT' and state['questions_asked'] == 0
    assert brain.requests[0]['evidence_context']['evidence'][0]['source'] == 'decision.txt:1'
    assert state['audit']['relevant_context'][0]['status'] == 'HISTORICAL'


def test_questions_are_adaptive_and_stop_at_five(tmp_path):
    values = [proposal(clear=False, question=f'Which version axis {i}?') for i in range(6)]
    service, brain = controller(tmp_path, values)
    state = service.begin('alice', 'chat', 'Complete the console')
    for number in range(1, 6):
        assert state['questions_asked'] == number
        state = service.update('alice', state['cycle_id'], state['revision'], answer=f'answer {number}')
    assert state['questions_asked'] == 5 and state['status'] == 'AUDIT'
    assert len(state['answers']) == 5 and state['pending_question'] is None
    assert 'Further clarification' in state['audit']['uncertainty'][-1]
    assert len(brain.requests[-1]['session_context']['answers']) == 5
    fresh = IntentController(tmp_path / 'intent', context=service.context, reasoner=service.reasoner, executors=service.executors)
    assert fresh.get('alice', state['cycle_id'])['questions_asked'] == 5


def test_new_cycle_has_its_own_allowance(tmp_path):
    service, _ = controller(tmp_path, [proposal(clear=False, question='Which one?'), proposal()])
    first = service.begin('alice', 'chat', 'First task')
    second = service.begin('alice', 'chat', 'Different task')
    assert first['cycle_id'] != second['cycle_id'] and second['questions_asked'] == 0


def test_no_repeat_and_correction_preserves_answers_and_count(tmp_path):
    service, _ = controller(tmp_path, [proposal(clear=False, question='Which console?'),
                                      proposal(clear=False, question='Which console?'), proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    state = service.update('alice', state['cycle_id'], state['revision'], answer='DesktopHarnessTest')
    assert state['status'] == 'AUDIT' and state['questions_asked'] == 1
    state = service.accept('alice', state['cycle_id'], state['revision'])
    state = service.update('alice', state['cycle_id'], state['revision'], correction='Only the task preparation controls')
    assert state['questions_asked'] == 1 and len(state['answers']) == 1
    assert state['corrections'] and state['package'] is None and not state['audit_accepted']


def test_acceptance_is_not_execution_or_assumption_confirmation(tmp_path):
    service, _ = controller(tmp_path, [proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    state = service.accept('alice', state['cycle_id'], state['revision'])
    assert state['package']['assumptions'] == state['audit']['assumptions']
    assert state['package']['workspace'] is None and state['package']['permissions'] == []
    assert not state['package']['execution_authorized']
    audit = deepcopy(state['audit'])
    state = service.choose('alice', state['cycle_id'], state['revision'], 'codex')
    state = service.choose('alice', state['cycle_id'], state['revision'], 'uri')
    assert state['audit'] == audit and state['executor'] == 'uri'
    assert not state['execution_authorized']
    assert service.deny('alice', state['cycle_id'], state['revision'])['status'] == 'EXECUTION_DENIED'


def test_latest_turn_preserves_original_answers_and_invalidates_acceptance(tmp_path):
    service, brain = controller(tmp_path, [proposal(clear=False, question='Which console?'), proposal(), proposal()])
    original = 'Complete the console; its identity is not supplied here'
    state = service.begin('alice', 'chat', original)
    assert brain.requests[-1]['session_context']['latest_user_turn'] == {'kind': 'request', 'text': original}
    state = service.update('alice', state['cycle_id'], state['revision'], answer='DesktopHarnessTest')
    packet = brain.requests[-1]['session_context']
    assert packet['latest_user_turn'] == {'kind': 'answer', 'text': 'DesktopHarnessTest'}
    assert packet['request'] == original and packet['answers'][0]['answer'] == 'DesktopHarnessTest'
    answers = deepcopy(packet['answers'])
    state = service.accept('alice', state['cycle_id'], state['revision'])  # Explicitly simulated fixture.
    state = service.update('alice', state['cycle_id'], state['revision'], correction='Preparation controls only')
    packet = brain.requests[-1]['session_context']
    assert packet['latest_user_turn'] == {'kind': 'correction', 'text': 'Preparation controls only'}
    assert packet['answers'] == answers and packet['request'] == original
    assert brain.requests[-1]['evidence_context']['evidence'][0]['status'] == 'HISTORICAL'
    assert not state['audit_accepted'] and state['package'] is None and not state['execution_authorized']


def test_stale_acceptance_and_cross_user_access_are_rejected(tmp_path):
    service, _ = controller(tmp_path, [proposal(), proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    service.update('alice', state['cycle_id'], state['revision'], correction='Only the original console')
    with pytest.raises(ValueError, match='CURRENT_AUDIT_REQUIRED'):
        service.accept('alice', state['cycle_id'], state['revision'])
    with pytest.raises(PermissionError):
        service.get('bob', state['cycle_id'])
    with pytest.raises(ValueError):
        service.get('alice', '../outside')


@pytest.mark.parametrize('mutation,error', [
    (lambda p: p['intent'].update(context_ids=['invented:source']), 'INVENTED_PROVENANCE'),
    (lambda p: p['intent'].update(references=['a file the user never named']), 'UNGROUNDED_REFERENCE'),
    (lambda p: p.update(action={'type': 'execute'}), 'PREPARATION_ONLY'),
    (lambda p: p['intent'].update(sufficiently_understood='yes'), 'AUDIT_INCOMPLETE'),
])
def test_plausible_untrusted_proposals_do_not_gain_authority(tmp_path, mutation, error):
    value = proposal()
    mutation(value)
    service, _ = controller(tmp_path, [value])
    state = service.begin('alice', 'chat', 'Complete the console')
    assert state['status'] == 'AUDIT_REJECTED' and state['error'].split(':', 1)[0] == error
    assert not state['execution_authorized']


def test_context_second_pass_resolves_only_verbatim_reference(tmp_path):
    first = proposal()
    first['intent']['references'] = ['the console']
    service, brain = controller(tmp_path, [first, proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    assert state['reference_requests'] == ['the console'] and len(brain.requests) == 2
    assert state['questions_asked'] == 0


def test_reasoning_unavailable_preserves_user_correction(tmp_path):
    service, _ = controller(tmp_path, [proposal()])
    state = service.begin('alice', 'chat', 'Complete the console')
    service.reasoner = lambda user: ModelReasoningGateway()
    state = service.update('alice', state['cycle_id'], state['revision'], correction='No new console')
    assert state['corrections'] == ['No new console'] and state['status'] == 'REASONING_UNAVAILABLE'
    assert not state['audit_accepted']
    assert 'audit' not in state and state['package'] is None


def test_prior_session_decision_is_available_with_stable_provenance(tmp_path):
    history = ConversationHistoryStore(str(tmp_path / 'history'))
    history.append_turn(session_id='previous', turn_id='decision', user_text='Keep the existing console',
                        response_text='Scope excludes console replacement')
    core = SimpleNamespace(orchestrator=SimpleNamespace(conversation_history=history))
    context = ExistingContext(lambda user: core)
    record = dict(request='Complete the console we discussed', answers=[], corrections=[])
    first = context('alice', 'new-chat', record['request'], record)
    recovered = first['evidence'][0]
    assert recovered['source'] == 'ConversationHistoryStore:previous:decision'
    assert recovered['status'] == 'HISTORICAL' and recovered['sha256']
    for number in range(9):
        history.append_turn(session_id='new-chat', turn_id=str(number), user_text='New detail', response_text='Recorded')
    second = context('alice', 'new-chat', record['request'], record)
    assert recovered in second['evidence']


def test_existing_context_uses_real_memory_rar_arn_and_graph_interfaces(tmp_path):
    history = ConversationHistoryStore(str(tmp_path / 'history'))
    core = SimpleNamespace(orchestrator=SimpleNamespace(conversation_history=history),
                           graph_store=GraphStore(str(tmp_path / 'graph.sqlite3')))
    user_id = '11111111-1111-4111-8111-111111111111'
    log = MemoryLog(user_id, tmp_path / 'private')
    sources = SourceRegistry(log)
    uploads = tmp_path / 'files'
    uploads.mkdir()
    (uploads / 'report.py').write_text('print(1)')
    sources.register(uploads)
    context = ExistingContext(lambda user: core, memory=lambda user: (log, sources))
    record = dict(request='Open report.py', answers=[], corrections=[], reference_requests=['open report.py'])
    found = context(user_id, 'chat', 'open report.py', record)
    assert found['evidence'] and found['reference_resolutions']
    assert found['task_context']['task_facts']['request'] == 'Open report.py'
    missing = context(user_id, 'chat', 'nonexistent', {**record, 'reference_requests': ['nonexistent']})
    assert any('arn_recovery' in item for item in missing['reference_resolutions'])
    assert missing['edge_latency_ms'] is None


def test_http_demo_prepares_selects_denies_without_execution(tmp_path):
    service, brain = controller(tmp_path, [proposal(clear=False, question='Which console?'), proposal(), proposal()])
    app = FastAPI()
    app.include_router(router_for(service, lambda: SimpleNamespace(user_id='alice')))
    client = TestClient(app)
    state = client.post('/desktop/intent/begin', json={'session_id': 'chat', 'request': 'Complete the console we discussed'}).json()
    prefix = '/desktop/intent/' + state['cycle_id']
    state = client.post(prefix + '/respond', json={'revision': state['revision'], 'answer': 'DesktopHarnessTest'}).json()
    state = client.post(prefix + '/respond', json={'revision': state['revision'], 'correction': 'Keep the existing console'}).json()
    state = client.post(prefix + '/accept', json={'revision': state['revision']}).json()
    assert state['package']['user_corrections'] == ['Keep the existing console']
    state = client.post(prefix + '/executor', json={'revision': state['revision'], 'executor': 'codex'}).json()
    assert state['executor'] == 'codex' and not state['execution_authorized']
    assert client.post(prefix + '/run', json={}).status_code == 404
    assert client.post(prefix + '/deny', json={'revision': state['revision']}).json()['status'] == 'EXECUTION_DENIED'
    assert client.post('/desktop/intent/begin', json={'session_id': 'chat', 'request': 'x', 'authorized': True}).status_code == 422


def test_candidate_composition_uses_real_auth_and_brain_requests_default_off(tmp_path):
    script = Path(__file__).resolve().parents[1] / 'scripts/run_intent_workflow_candidate.py'
    code = '''
import runpy, sys, uvicorn
from fastapi.testclient import TestClient
def smoke(app, **kwargs):
    assert kwargs['host'] == '127.0.0.1'
    with TestClient(app) as client:
        assert client.post('/desktop/intent/begin', json={'session_id':'chat','request':'Prepare a task'}).status_code == 401
        created=client.post('/auth/signup',json={'username':'intent_smoke','password':'Disposable-test-293!'})
        assert created.status_code == 200, created.text
        headers={'Authorization':'Bearer '+created.json()['token']}
        result=client.post('/desktop/intent/begin',headers=headers,json={'session_id':'chat','request':'Prepare a task'})
        assert result.status_code == 200, result.text
        state=result.json()
        assert state['status'] == 'REASONING_UNAVAILABLE', state
        assert state['error'] == 'model_not_configured', state
        assert not state['execution_authorized']
uvicorn.run=smoke
script=sys.argv[1]
sys.argv=[script,'--enable-intent-preparation','--state-dir',sys.argv[2]]
runpy.run_path(script,run_name='__main__')
'''
    result = subprocess.run([sys.executable, '-c', code, str(script), str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr[-4000:]


def test_preparation_prompt_is_trusted_composition_and_does_not_change_default():
    from experimental.intent_workflow.controller import DISCOVERY_INSTRUCTIONS
    from uri_core.core.model_reasoning_adapter import OllamaReasoningAdapter, REASONING_SYSTEM_PROMPT
    from uri_core.core.model_providers.base import ModelResponse
    class Provider:
        def complete(self, **kwargs):
            self.kwargs = kwargs
            return ModelResponse(content=json.dumps(proposal()), model='test', provider='fixture')
    provider = Provider()
    adapter = OllamaReasoningAdapter(provider=provider, system_prompt=DISCOVERY_INSTRUCTIONS)
    gateway = ModelReasoningGateway(model_callable=adapter, instruction=DISCOVERY_INSTRUCTIONS)
    result = gateway.reason('Draft a note')
    assert result['status'] == 'proposal_ready'
    assert result['request']['available_capabilities'] == []
    assert result['request']['instruction'] == DISCOVERY_INSTRUCTIONS
    assert REASONING_SYSTEM_PROMPT not in provider.kwargs['system']
    assert adapter.last_completion['model'] == 'test'
    default = ModelReasoningGateway().build_reasoning_request('Draft a note')
    assert 'composing available capabilities' in default['instruction']


@pytest.mark.parametrize('value', [None, 'false', 0])
def test_higher_reasoning_is_never_coerced(tmp_path, value):
    p = proposal(); p['intent']['higher_reasoning'] = value
    service, _ = controller(tmp_path, [p])
    state = service.begin('alice', 'chat', 'Prepare only')
    assert state['status'] == 'AUDIT_REJECTED' and 'audit' not in state
    with pytest.raises(ValueError, match='CURRENT_AUDIT_REQUIRED'):
        service.accept('alice', state['cycle_id'], state['revision'])


def test_rejected_question_does_not_leave_acceptible_interpretation(tmp_path):
    p = proposal(clear=False); p['clarification'] = {'question': 'Which?', 'question_key': None}
    service, _ = controller(tmp_path, [p])
    state = service.begin('alice', 'chat', 'Prepare only')
    assert state['status'] == 'AUDIT_REJECTED' and 'audit' not in state
