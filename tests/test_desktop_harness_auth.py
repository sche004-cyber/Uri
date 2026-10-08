"""Real Core HTTP auth exercised in a separate process and disposable installation."""
from pathlib import Path
import subprocess
import sys


def test_real_core_registration_login_logout_and_restoration(tmp_path):
    code = '''
import os,sys
sys.path.insert(0, sys.argv[1]); os.chdir(sys.argv[2])
os.environ['URI_EXTERNAL_CREDENTIAL_SECRET'] = 'disposable-test-encryption-secret-only'
from fastapi.testclient import TestClient
from uri_core.app import server
from uri_core.core.auth_session import AuthSessionStore
from uri_core.core.user_accounts import UserAccountStore
with TestClient(server.app) as client:
    assert client.get('/auth/me').json()['authenticated'] is False
    result = client.post('/auth/signup', json={'username':'qualification_probe','password':'Disposable-test-293!'} )
    assert result.status_code == 200, result.status_code
    token = result.json()['token']
    headers = {'Authorization': 'Bearer '+token}
    assert client.get('/auth/me',headers=headers).status_code == 200
    assert client.get('/connections',headers=headers).status_code == 200
    assert client.post('/auth/login',json={'username':'qualification_probe','password':'wrong-password'}).status_code == 401
    restored_accounts = UserAccountStore()
    restored_sessions = AuthSessionStore()
    assert restored_accounts.authenticate('qualification_probe','Disposable-test-293!') is not None
    assert restored_sessions.resolve(token) is not None
    server._auth_session_store = restored_sessions
    assert client.get('/auth/me',headers=headers).status_code == 200
    assert client.post('/auth/logout',headers=headers).status_code == 200
    assert client.get('/auth/me',headers=headers).status_code == 401
    assert AuthSessionStore().resolve(token) is None
    again=client.post('/auth/login',json={'username':'qualification_probe','password':'Disposable-test-293!'})
    assert again.status_code == 200
    assert again.json()['token'] != token
print('Core auth: registration/login/logout/session restoration passed')
'''
    result = subprocess.run([sys.executable, '-c', code, str(Path(__file__).resolve().parents[1]), str(tmp_path)],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
