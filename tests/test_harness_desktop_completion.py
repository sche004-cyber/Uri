import json
from pathlib import Path
import sys
import time

import pytest

from uri_v1.desktop_harness.controller import HarnessController
from uri_v1.desktop_harness.registry import AntigravityAdapter, HarnessRegistry
from uri_v1.desktop_harness.service import DesktopHarnessService, SubscriptionCLIAdapter
import uri_v1.memory.recorder as memory_recorder


def query(executable, args):
    if args == ['auth', 'status', '--json']:
        return json.dumps({'loggedIn': True, 'authMethod': 'claude.ai', 'email': 'secret@example.invalid'})
    if args == ['plugin', 'list', '--json']:
        return json.dumps([{'id': 'harmless@test', 'enabled': True, 'installPath': 'private-path'}])
    return None


@pytest.fixture
def controller(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_recorder, '_VERIFIERS', memory_recorder.MappingProxyType({}))
    adapter = SubscriptionCLIAdapter((sys.executable, str(Path(__file__).resolve().parents[1] /
        'fixtures/m38_harness/fake_claude.py')))
    service = DesktopHarnessService(tmp_path, adapter)
    return HarnessController(service, HarnessRegistry(adapter, query=query))


USER = '00000000-0000-0000-0000-000000000007'


def start(controller):
    approval = controller.prepare(USER, 'claude_code')['approval_id']
    return controller.start(USER, approval, True)['task_id']


def settle(controller, task_id):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        record = controller.get(USER, task_id)
        if record['status'] != 'RUNNING':
            return record
        time.sleep(.05)
    pytest.fail('Task did not settle')


def test_discovery_does_not_authorize_native_plugins(controller):
    rows = controller.providers()['providers']
    assert controller.records == {}
    assert rows[0]['eligible'] is True
    plugin = rows[0]['capabilities'][0]
    assert plugin['available'] and not plugin['authorized'] and not plugin['tested'] and plugin['blocked']
    assert 'private-path' not in json.dumps(rows) and 'secret@example.invalid' not in json.dumps(rows)


@pytest.mark.parametrize('provider', ['antigravity', 'codex', '', 'other'])
def test_ineligible_selection_never_submits(controller, provider):
    with pytest.raises(PermissionError):
        controller.prepare(USER, provider)
    assert controller.service.pending == {} and controller.records == {}
    with pytest.raises(PermissionError, match='CONTAINMENT_UNQUALIFIED'):
        AntigravityAdapter().execute('ignored')


def test_selection_owner_approval_and_verified_result(controller):
    approval = controller.prepare(USER, 'claude_code')['approval_id']
    with pytest.raises(PermissionError):
        controller.start('another-user', approval, True)
    with pytest.raises(PermissionError):
        controller.start(USER, approval, False)
    task_id = controller.start(USER, approval, True)['task_id']
    with pytest.raises(PermissionError):
        controller.start(USER, approval, True)
    record = settle(controller, task_id)
    assert record['provider'] == 'claude_code'
    assert record['status'] == 'SUCCEEDED' and record['receipt']['verified']
    assert not record['receipt']['write_back']
    assert controller.providers()['brain_configuration_changed'] is False
    with pytest.raises(PermissionError):
        controller.get('another-user', task_id)
    with pytest.raises(PermissionError):
        controller.cancel('another-user', task_id)
    assert json.loads((controller.root / (task_id + '.json')).read_text())['status'] == 'SUCCEEDED'


def test_cancellation_settles_real_process(controller, monkeypatch):
    monkeypatch.setenv('URI_FAKE_SCENARIO', 'hang_chatty')
    task_id = start(controller)
    time.sleep(.25)
    controller.cancel(USER, task_id)
    result = settle(controller, task_id)
    assert result['status'] == 'CANCELLED'
    assert result['receipt']['cancelled'] and not result['receipt']['verified']


def test_restart_checkpoints_unknown_without_replay(controller):
    task_id = 'a' * 32
    record = {'task_id': task_id, 'user_id': USER, 'provider': 'claude_code', 'status': 'RUNNING'}
    controller._save(record)
    restarted = HarnessController(controller.service, controller.registry)
    assert restarted.get(USER, task_id)['status'] == 'INTERRUPTED'
    assert restarted.get(USER, task_id)['potentially_non_idempotent']
    assert restarted.cancels == {}


def test_quota_requires_explicit_recovery_preserves_work(controller, monkeypatch):
    def interrupted(*args, **kwargs):
        return {'error_family': 'QUOTA', 'cancelled': False, 'verified': False,
                'verification_status': 'VERIFIED', 'result': 'Quota interrupted'}
    monkeypatch.setattr(controller.service, '_run', interrupted)
    task_id = start(controller)
    result = settle(controller, task_id)
    assert result['status'] == 'QUOTA_INTERRUPTED' and result['verified_completed_work']
    assert result['potentially_non_idempotent']
    with pytest.raises(PermissionError):
        controller.prepare(USER, 'claude_code')
    with pytest.raises(PermissionError):
        controller.recover(USER, task_id, 'wait', False)
    with pytest.raises(PermissionError):
        controller.recover(USER, task_id, 'local', True)
    with pytest.raises(PermissionError):
        controller.recover(USER, task_id, 'choose', True)
    restarted = HarnessController(controller.service, HarnessRegistry(controller.service.adapter, query=query))
    assert 'claude_code' in restarted.registry.quota_blocked
    controller.recover(USER, task_id, 'wait', True)
    assert len(controller.records) == 1
    assert controller.prepare(USER, 'claude_code')


def test_current_auth_required(controller):
    controller.registry.query = lambda *args: None
    controller.providers(refresh=True)
    with pytest.raises(PermissionError):
        controller.prepare(USER, 'claude_code')


def test_native_assistant_rate_limit_with_generic_terminal_failure():
    from uri_v1.desktop_harness.service import classify_cli_errors
    events = [{'type': 'assistant', 'is_api_error_message': True, 'error': 'rate_limit'},
              {'type': 'result', 'subtype': 'success', 'is_error': True, 'result': 'Failed'}]
    assert classify_cli_errors(events) == 'QUOTA'
    events[-1]['is_error'] = False
    assert classify_cli_errors(events) is None
    assert classify_cli_errors([{'type': 'assistant', 'message': 'Please check quota'},
        {'type': 'result', 'is_error': False}]) is None


def test_new_routes_require_auth_strict_payloads_and_owner(controller):
    from fastapi import FastAPI, Header, HTTPException
    from fastapi.testclient import TestClient
    from types import SimpleNamespace
    from uri_v1.desktop_harness.routes import router_for
    app = FastAPI()
    def principal(authorization=Header(None)):
        if authorization not in ('Bearer alice', 'Bearer bob'):
            raise HTTPException(401)
        return SimpleNamespace(user_id=USER if authorization == 'Bearer alice' else 'bob')
    app.include_router(router_for(controller.service, principal, controller))
    client = TestClient(app)
    headers = {'Authorization': 'Bearer alice'}
    for path in ('providers', 'tasks', 'tasks/missing'):
        assert client.get('/desktop/harness-test/' + path).status_code == 401
    assert client.post('/desktop/harness-test/tasks/prepare', json={'provider': 'claude_code'}).status_code == 401
    assert client.post('/desktop/harness-test/tasks/prepare', headers=headers,
        json={'provider': 'claude_code', 'network': True}).status_code == 422
    assert client.post('/desktop/harness-test/tasks/prepare', headers=headers,
        json={'provider': 'antigravity'}).status_code == 403
    aid = client.post('/desktop/harness-test/tasks/prepare', headers=headers,
        json={'provider': 'claude_code'}).json()['approval_id']
    assert client.post(f'/desktop/harness-test/tasks/{aid}/start', headers=headers,
        json={'authorized': 'true'}).status_code == 422
    task_id = client.post(f'/desktop/harness-test/tasks/{aid}/start', headers=headers,
        json={'authorized': True}).json()['task_id']
    assert client.get(f'/desktop/harness-test/tasks/{task_id}', headers={'Authorization': 'Bearer bob'}).status_code == 404
    assert client.get('/desktop/harness-test/tasks', headers={'Authorization': 'Bearer bob'}).json()['tasks'] == []
    settle(controller, task_id)
