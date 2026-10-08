import json
import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient

import uri_v1.memory.recorder as memory_recorder
from uri_v1.desktop_harness.routes import router_for
from uri_v1.desktop_harness.service import DesktopHarnessService, SubscriptionCLIAdapter


@pytest.fixture
def bridge(tmp_path, monkeypatch):
    monkeypatch.setattr(memory_recorder, '_VERIFIERS', memory_recorder.MappingProxyType({}))
    adapter = SubscriptionCLIAdapter((sys.executable, str(Path(__file__).resolve().parents[1] /
        'fixtures/m38_harness/fake_claude.py')))
    service = DesktopHarnessService(tmp_path, adapter)
    app = FastAPI()
    def principal(authorization=Header(None)):
        users = {'Bearer alice': '00000000-0000-0000-0000-000000000007',
                 'Bearer bob': '00000000-0000-0000-0000-000000000008'}
        if authorization not in users:
            raise HTTPException(401)
        return SimpleNamespace(user_id=users[authorization])
    app.include_router(router_for(service, principal))
    return TestClient(app), service


def prepare(client):
    return client.post('/desktop/harness-test/prepare', headers={'Authorization': 'Bearer alice'}).json()['approval_id']


def approve(client, approval_id, user='alice', body=None):
    return client.post(f'/desktop/harness-test/{approval_id}/approve',
        headers={'Authorization': f'Bearer {user}'}, json={'authorized': True} if body is None else body)


def test_auth_approval_isolation_and_consumption(bridge):
    client, service = bridge
    assert client.post('/desktop/harness-test/prepare').status_code == 401
    aid = prepare(client)
    assert approve(client, aid, 'bob').status_code == 403
    assert approve(client, aid, body={'authorized': False}).status_code == 403
    assert approve(client, aid, body={'authorized': 'true'}).status_code == 422
    assert approve(client, aid, body={'authorized': True, 'network': True}).status_code == 422
    result = approve(client, aid)
    assert result.status_code == 200, result.text
    assert result.json()['verified'] is True, result.text
    assert result.json()['write_back'] is False
    assert approve(client, aid).status_code == 403
    assert 'fake-session' not in result.text
    print(json.dumps(result.json()))


@pytest.mark.parametrize('scenario', ['false_claim', 'extra_file', 'symlink_escape'])
def test_false_claims_never_verify(bridge, monkeypatch, scenario):
    client, _ = bridge
    monkeypatch.setenv('URI_FAKE_SCENARIO', scenario)
    if scenario == 'symlink_escape':
        target = bridge[1].root / 'outside.py'
        target.write_text('# disposable containment target')
        monkeypatch.setenv('URI_FAKE_ORIGINAL', str(target))
    response = approve(client, prepare(client))
    assert response.status_code == 200, response.text
    assert response.json()['verified'] is False


def test_expired_approval_and_sanitized_failure(bridge, monkeypatch):
    client, service = bridge
    aid = prepare(client)
    user, stamp = service.pending[aid]
    service.pending[aid] = (user, stamp - 601)
    assert approve(client, aid).status_code == 403
    def failure(*args, **kwargs):
        raise RuntimeError('secret-auth-token')
    monkeypatch.setattr(service.adapter, 'probe', failure)
    aid = prepare(client)
    response = approve(client, aid)
    assert response.status_code == 503
    assert 'secret-auth-token' not in response.text
    assert approve(client, aid).status_code == 403


def test_subscription_adapter_never_discovers_credentials(monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY', 'brain-key')
    monkeypatch.setenv('CLAUDE_CODE_OAUTH_TOKEN', 'do-not-forward')
    from uri_v1.execution.harness.process import harness_env
    adapter = SubscriptionCLIAdapter()
    assert adapter.AUTH_VARS == ()
    assert adapter.inventory().items == ()
    assert 'ANTHROPIC_API_KEY' not in harness_env(adapter.AUTH_VARS)
    assert 'CLAUDE_CODE_OAUTH_TOKEN' not in harness_env(adapter.AUTH_VARS)


def test_crashed_cli_with_corrected_file_is_not_desktop_success(bridge, monkeypatch):
    client, _ = bridge
    monkeypatch.setenv('URI_FAKE_SCENARIO', 'symlink_escape')
    monkeypatch.delenv('URI_FAKE_ORIGINAL', raising=False)  # fixture repairs then crashes before result
    response = approve(client, prepare(client))
    assert response.status_code == 200, response.text
    assert response.json()['verified'] is False
    assert response.json()['execution_ok'] is False
    assert response.json()['exit_code'] != 0


def test_opt_in_routes_are_classified(bridge):
    from uri_v1.desktop_harness.routes import ROUTE_CLASSIFICATIONS
    client, _ = bridge
    routes = {(method.upper(), path) for path, methods in client.app.openapi()['paths'].items()
              if path.startswith('/desktop/harness-test') for method in methods}
    assert routes == set(ROUTE_CLASSIFICATIONS)
    assert set(ROUTE_CLASSIFICATIONS.values()) == {'USER'}


def test_windows_scope_is_exact_and_never_broadened():
    from uri_v1.desktop_harness.service import permission_scope
    assert permission_scope(r'C:\Users\test\scratch\files') == '//c/Users/test/scratch/files'
    assert permission_scope('/tmp/scratch/files') == '//tmp/scratch/files'
    with pytest.raises(Exception, match='NETWORK_WORKSPACE_REFUSED'):
        permission_scope(r'\\server\share\files')
