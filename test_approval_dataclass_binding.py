import pytest
from uri_core.core.approval_store import ApprovalStore, ApprovalStateError
from uri_core.core.principal_context import PrincipalContext


def test_runtime_dataclass_binding_survives_persistence_and_is_single_use(tmp_path):
    store = ApprovalStore(str(tmp_path / 'approvals.json'))
    principal = PrincipalContext('fixture-user', 'user', None)
    action = store.propose('google_workspace_create',
                           {'request_text': 'Disposable file', 'principal': principal}, 'own-session')
    store.decide(action.action_id, approved=True, session_id='own-session')
    saved = store.get(action.action_id)
    store.consume(action.action_id, capability_id=action.capability_id,
                  arguments=saved.arguments, session_id='own-session')
    with pytest.raises(ApprovalStateError):
        store.consume(action.action_id, capability_id=action.capability_id,
                      arguments=saved.arguments, session_id='own-session')


@pytest.mark.parametrize('mutation', ['arguments', 'principal', 'session', 'capability'])
def test_unchanged_binding_controls_reject_drift(tmp_path, mutation):
    store = ApprovalStore(str(tmp_path / 'approvals.json'))
    principal = PrincipalContext('fixture-user', 'user', None)
    action = store.propose('google_workspace_create',
                           {'request_text': 'Disposable file', 'principal': principal}, 'own-session')
    store.decide(action.action_id, approved=True, session_id='own-session')
    saved = store.get(action.action_id)
    arguments = saved.arguments
    if mutation == 'arguments': arguments['request_text'] = 'Different file'
    if mutation == 'principal': arguments['principal']['role'] = 'admin'
    with pytest.raises(ApprovalStateError):
        store.consume(action.action_id,
                      capability_id='other' if mutation == 'capability' else action.capability_id,
                      arguments=arguments,
                      session_id='other-session' if mutation == 'session' else 'own-session')
    assert store.get(action.action_id).consumed_at is None


def test_existing_mismatched_record_is_not_rebound(tmp_path):
    import json
    path = tmp_path / 'approvals.json'
    store = ApprovalStore(str(path))
    action = store.propose('tool', {'request_text': 'Fixture'}, 'own-session')
    data = json.loads(path.read_text())
    data['actions'][0]['arguments_fingerprint'] = 'old-mismatched-fingerprint'
    path.write_text(json.dumps(data))
    store.decide(action.action_id, approved=True, session_id='own-session')
    with pytest.raises(ApprovalStateError):
        store.consume(action.action_id, capability_id='tool', arguments=action.arguments,
                      session_id='own-session')


def test_brain_discovers_declared_google_content_schema_without_authority():
    from types import SimpleNamespace
    from uri_core.core.decision_engine import build_decision_request
    state = {'turn': {'user_text': 'Create disposable Google slides'}, 'recent_conversation': [],
             'active_pointer': {}, 'capability_summaries': [
                 {'capability_id': 'google_workspace_create', 'source': 'legacy'}],
             'session_facts': [], 'attempt_history': []}
    request = build_decision_request(state, preselected_ids=['google_workspace_create'],
                                     capability_directory=SimpleNamespace())
    schema = request['capability_input_schemas']['google_workspace_create']['google_workspace_create']
    assert {'kind','title'} <= schema['properties'].keys()
    assert not {'principal','session_id','file_id','grants_store'} & schema['properties'].keys()


def test_approval_gate_round_trip_dispatches_once_after_explicit_approval(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock, patch
    from uri_core.core.approval_gate import ApprovalGate
    principal = PrincipalContext('fixture-user', 'user', None)
    dispatcher = Mock()
    dispatcher.execute_tool.return_value = {'status': 'success', 'data': {'status': 'success'}}
    registry = Mock()
    registry.describe_status.return_value = SimpleNamespace(approval_requirement='user_approval_required',
                                                          risk='sensitive', description='Fixture creation')
    gate = ApprovalGate(dispatcher=dispatcher, capability_registry=registry,
                        approval_store=ApprovalStore(str(tmp_path / 'approvals.json')))
    with patch('uri_core.core.approval_gate.CapabilityResolver.is_allowed', return_value=False):
        assert gate.execute_tool('google_workspace_create', session_id='s', principal=principal)['status'] == 'rejected'
    with patch('uri_core.core.approval_gate.CapabilityResolver.is_allowed', return_value=True):
        proposal = gate.execute_tool('google_workspace_create', session_id='s', principal=principal,
                                     kind='slides', title='Disposable fixture')
    assert proposal['status'] == 'awaiting_approval'
    dispatcher.execute_tool.assert_not_called()
    assert gate.decide(proposal['action_id'], approved=True, session_id='other')['status'] == 'error'
    dispatcher.execute_tool.assert_not_called()
    assert gate.decide(proposal['action_id'], approved=True, session_id='s')['status'] == 'success'
    assert gate.decide(proposal['action_id'], approved=True, session_id='s')['status'] == 'error'
    assert dispatcher.execute_tool.call_count == 1


def test_approved_result_link_reaches_only_original_conversation(tmp_path):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from uri_core.core.orchestrator import UriOrchestrator
    from uri_core.core.conversation_history import ConversationHistoryStore
    from uri_core.core.file_store import FileStore
    orchestrator = UriOrchestrator.__new__(UriOrchestrator)
    proposed = SimpleNamespace(arguments={'request_text':'Create disposable fixture'},
                               capability_id='google_workspace_create')
    orchestrator.approval_gate = SimpleNamespace(
        approval_store=SimpleNamespace(get=lambda _: proposed),
        decide=Mock(return_value={'status':'success','data':{'status':'success',
            'name':'Fixture slides','webViewLink':'https://docs.google.com/presentation/d/fixture/edit'}}))
    orchestrator.conversation_history = ConversationHistoryStore(storage_dir=str(tmp_path / 'history'))
    orchestrator.file_store = FileStore(str(tmp_path / 'files'))
    orchestrator._draft_narrative_safely = Mock()
    orchestrator._resume_model_workflow_after_decision = Mock(return_value=None)
    result = orchestrator.decide_action('fixture-action', True, session_id='own-session')
    assert result['status'] == 'success'
    own = orchestrator.conversation_history.get_session('own-session')
    assert 'https://docs.google.com/presentation/d/fixture/edit' in own[0]['response_text']
    assert orchestrator.conversation_history.get_session('other-session') == []
