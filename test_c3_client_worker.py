"""C3 private store/journal/worker tests; no existing account/data used."""
import copy
import io
import json
from pathlib import Path
import secrets
import struct
import subprocess
import sys
import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
import pytest

from uri_core.client_contracts import Binding, ClientMutationSet, ReadQuery, canonical, digest
from uri_core.client_runtime.frames import FrameError, read_frame, write_frame
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.client_runtime.persistence import ClientPersistence, PersistenceError
from uri_core.core.client_state_ports import ClientStatePorts
from uri_core.core.runtime_identity import RuntimeManifest, child_environment, provision

ROOT = Path(__file__).resolve().parent


def uid():
    return str(uuid.uuid4())


@pytest.fixture
def clients():
    base = ROOT / "work/c1" / ("c3_test_" + uuid.uuid4().hex)
    server = provision(ROOT, base / "server", Path(sys.executable), 18034, "c2-paired-core")
    principal = uid()
    a = ClientManifest(provision_client(server, base / "a", principal, ["remember_fact"]))
    b = ClientManifest(provision_client(server, base / "b", principal, []))
    return a, b, server


def mutations(worker, session, changes):
    queries = [ReadQuery(store=store, method=read_method, args=args) for store, read_method, args, method, kwargs in changes]
    snapshot = worker.snapshot(session, queries)
    scope = {k: getattr(snapshot, k) for k in ("server_id", "client_id", "principal_id", "session_id")}
    ports = ClientStatePorts(snapshot, Binding(**scope).model_dump())
    for store, read_method, args, method, kwargs in changes:
        reads = sorted([r.model_dump() for r in snapshot.reads if r.query.store == store], key=lambda r: digest(r["query"]))
        ports.propose(store, method, kwargs=kwargs, base_version=reads[0]["store_version"], previous_digest=digest(reads))
    return ports.mutation_set(uid(), uid())


def memory_change(content="client a secret-free memory"):
    return [("memory", "list_all", [], "add", {"category": "preference", "content": content})]


@pytest.mark.parametrize("data,code", [
    (b"\x00", "FRAME_TRUNCATED"), (struct.pack(">I", 0), "FRAME_LIMIT"),
    (struct.pack(">I", 2 * 1024 * 1024 + 1), "FRAME_LIMIT"),
    (struct.pack(">I", 8) + b"{}", "FRAME_TRUNCATED"),
    (struct.pack(">I", 1) + b"{", "FRAME_INVALID"),
    (struct.pack(">I", 2) + b"[]", "FRAME_OBJECT_REQUIRED"),
])
def test_frame_negative_cases(data, code):
    with pytest.raises(FrameError, match=code): read_frame(io.BytesIO(data))


def test_frame_roundtrip_partial_reads():
    stream = io.BytesIO();write_frame(stream, {"command": "close"})
    class Slow(io.BytesIO):
        def read(self, size): return super().read(min(size, 1))
    assert read_frame(Slow(stream.getvalue())) == {"command": "close"}
    assert read_frame(io.BytesIO()) is None


def test_two_client_roots_private_data_graph_files_and_approvals(clients):
    a, b, server = clients
    wa, wb = ClientPersistence(a), ClientPersistence(b)
    session = uid()
    change = mutations(wa, session, memory_change())
    wa.consent(change)
    receipt = wa.commit(change)
    assert receipt["outcome"] == "COMMITTED"
    assert wa.commit(change) == receipt
    assert wb.snapshot(session, [ReadQuery(store="memory", method="list_all")]).reads[0].result == []
    wa.stores["files"].save(filename="a.txt", content=b"client a", session_id=session)
    assert wb.stores["files"].list_for_session(session) == []
    wa.stores["approvals"].propose(capability_id="remember_fact", arguments={"content":"a"}, session_id=session)
    assert wb.stores["approvals"].list_pending() == []
    node = wa.stores["graph"].upsert_node(entity_type="person", canonical_name="A")
    assert wb.stores["graph"].list_nodes() == []
    assert str(a.data["client_root"]) != str(b.data["client_root"])
    server_state = Path(server).parent
    assert not (server_state / "private").exists()
    assert not any(p.name == "graph.sqlite3" for p in server_state.rglob("*"))


def test_consent_scope_source_freshness_and_cas_conflicts(clients):
    a, b, _ = clients
    worker = ClientPersistence(a)
    change = mutations(worker, uid(), memory_change())
    with pytest.raises(PersistenceError, match="CONSENT_REQUIRED"): worker.commit(change)
    changed = change.model_copy(update={"client_id": b.data["client_id"]})
    with pytest.raises(PersistenceError, match="MUTATION_SCOPE"): worker.consent(changed)
    worker.consent(change)
    stale = mutations(worker, change.session_id, memory_change("another"));worker.consent(stale)
    worker.commit(change)
    with pytest.raises(PersistenceError, match="VERSION_CONFLICT"): worker.commit(stale)
    fresh = mutations(worker, uid(), memory_change("third"));worker.consent(fresh)
    worker.stores["memory"].add(category="preference", content="external local edit")
    with pytest.raises(PersistenceError, match="SOURCE_CHANGED"): worker.commit(fresh)


def test_multi_store_failure_and_interrupted_intent_recover_without_replay(clients):
    a, b, _ = clients
    worker = ClientPersistence(a)
    session = uid()
    changes = memory_change() + [("memory_settings", "load", [], "update", {"values":{"never_a_setting":True}})]
    value = mutations(worker, session, changes);worker.consent(value)
    with pytest.raises(PersistenceError, match="COMMIT_ROLLED_BACK"):worker.commit(value)
    assert worker.snapshot(session, [ReadQuery(store="memory", method="list_all")]).reads[0].result == []
    value = mutations(worker, session, memory_change());worker.consent(value)
    def crash(index): raise SystemExit("synthetic crash")
    with pytest.raises(SystemExit):worker.commit(value, fault=crash)
    restarted = ClientPersistence(a)
    assert restarted.snapshot(session, [ReadQuery(store="memory", method="list_all")]).reads[0].result == []
    with pytest.raises(PersistenceError, match="OPERATION_ROLLED_BACK"):restarted.commit(value)


def test_conflicting_replay_and_foreign_file_scope(clients):
    a, b, _ = clients
    worker = ClientPersistence(a);session=uid()
    value = mutations(worker, session, memory_change());worker.consent(value);worker.commit(value)
    foreign = mutations(worker, session, memory_change("different")).model_copy(update={"operation_id":value.operation_id})
    worker.consent(foreign)
    with pytest.raises(PersistenceError, match="IDEMPOTENCY_CONFLICT"): worker.commit(foreign)
    stored = worker.stores["files"].save(filename="other.txt", content=b"different session", session_id=uid())
    with pytest.raises(PersistenceError, match="FILE_SESSION_SCOPE"):
        worker.snapshot(session, [ReadQuery(store="files", method="get", args=[stored.file_id])])


def test_restore_hash_corruption_fails_closed(clients):
    a,b,_=clients;worker=ClientPersistence(a)
    change=mutations(worker,uid(),memory_change());worker.consent(change)
    with pytest.raises(SystemExit):worker.commit(change,fault=lambda _:(_ for _ in ()).throw(SystemExit()))
    backup=worker.journal/change.operation_id
    next(p for p in backup.rglob('*') if p.is_file()).write_bytes(b'corrupted backup')
    with pytest.raises(PersistenceError,match='RESTORE_HASH_MISMATCH'):ClientPersistence(a)


def test_profile_projection_session_replacement_file_bytes_and_method_argument_scope(clients):
    a,b,_=clients;worker=ClientPersistence(a);session=uid()
    snapshot=worker.snapshot(session,[ReadQuery(store='profile',method='load_or_create'),
        ReadQuery(store='sessions',method='get_session',args=[session]),
        ReadQuery(store='files',method='list_for_session',args=[session]),
        ReadQuery(store='connections',method='get_service_descriptor',args=['gmail'])])
    binding={k:getattr(snapshot,k) for k in ('server_id','client_id','principal_id','session_id')}
    ports=ClientStatePorts(snapshot,binding)
    original=ports.read('sessions','get_session',session)
    original['task']='bounded changed session'
    reads=[r.model_dump() for r in snapshot.reads if r.query.store=='sessions']
    ports.propose('sessions','save_session',args=[session],base_version=0,
                  previous_digest=digest(reads),replacement=original)
    import base64,hashlib
    content=b'client-owned file bytes'
    reads=[r.model_dump() for r in snapshot.reads if r.query.store=='files']
    ports.propose('files','save',kwargs={'filename':'result.txt','session_id':session,
        'content':{'encoding':'base64','data':base64.b64encode(content).decode(),'sha256':hashlib.sha256(content).hexdigest()}},
        base_version=0,previous_digest=digest(reads))
    value=ports.mutation_set(uid(),uid());worker.consent(value);worker.commit(value)
    restarted=ClientPersistence(a)
    check=restarted.snapshot(session,[ReadQuery(store='sessions',method='get_session',args=[session])])
    assert check.reads[0].result['task']=='bounded changed session'
    assert restarted.stores['files'].list_for_session(session)
    with pytest.raises(Exception):
        ports.read('connections','get_status',b.data['client_id'],'gmail')


def test_real_worker_signed_identity_stdio_duplicate_and_safe_errors(clients):
    a,b,_=clients;m=a.data
    env=child_environment(Path(m['client_root']),Path(m['interpreter']))
    cmd=[m['interpreter'],'-B','-I',m['worker_entrypoint'],'--manifest',str(a.path)]
    process=subprocess.Popen(cmd,cwd=m['client_root'],env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        nonce=secrets.token_hex(32);write_frame(process.stdin,{'command':'identity','nonce':nonce})
        response=read_frame(process.stdout)
        assert response and response['result']=='OK',process.stderr.read() if process.poll() is not None else response
        identity=response['value'];signature=identity.pop('signature')
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(m['client_public_key'])).verify(bytes.fromhex(signature),canonical(identity))
        assert identity['nonce']==nonce and identity['manifest_digest']==a.digest
        duplicate=subprocess.run(cmd,cwd=m['client_root'],env=env,input=b'',capture_output=True,timeout=15)
        assert duplicate.returncode!=0
        from scripts.uri_client_launcher import status
        assert status(a)['pid']==identity['pid']
        write_frame(process.stdin,{'command':'snapshot','session_id':uid(),'queries':[{'store':'memory','method':'list_all'}]})
        assert read_frame(process.stdout)['value']['reads'][0]['result']==[]
        write_frame(process.stdin,{'command':'private_bad_command','token':'never-echo-sentinel'})
        response=read_frame(process.stdout)
        assert response['result']=='REFUSED' and 'never-echo-sentinel' not in json.dumps(response)
        write_frame(process.stdin,{'command':'close'})
        assert read_frame(process.stdout)['result']=='CLOSED'
        assert process.wait(15)==0
    finally:
        # Closing this explicitly-created worker's private stdin is the normal
        # owned lifecycle cleanup; no foreign PID or production signal.
        if process.stdin and not process.stdin.closed:process.stdin.close()
        if process.poll() is None:process.wait(15)


def test_windows_powershell_client_launcher_preserves_binary_frames(clients):
    a,b,_=clients
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
             str(ROOT/'scripts/uri_client.ps1'),'-Manifest',str(a.path),'-Action','launch','-Headless']
    nonce=secrets.token_hex(32)
    frames=io.BytesIO();write_frame(frames,{'command':'identity','nonce':nonce});write_frame(frames,{'command':'close'})
    proc=subprocess.run(command,input=frames.getvalue(),capture_output=True,timeout=25)
    assert proc.returncode==0,proc.stderr.decode('utf-8','replace')
    stream=io.BytesIO(proc.stdout)
    identity=read_frame(stream)
    assert identity['result']=='OK' and identity['value']['nonce']==nonce
    assert read_frame(stream)['result']=='CLOSED'
    # Validate is tested separately below using explicit arguments; no binary
    # stdin channel or worker is involved in this diagnostic action.
    validated=subprocess.run(command[:command.index('-Action')]+['-Action','validate'],capture_output=True,timeout=15)
    assert validated.returncode==0 and json.loads(validated.stdout)['result']=='VALID'


@pytest.mark.parametrize('field,value',[('client_root','C:/Users/cheta/Development/uri-agent'),('interpreter','C:/Windows/python.exe'),('server_url','http://127.0.0.1:8021'),('source_digest','0'*64),('unrecognized','x')])
def test_manifest_negatives_and_existing_root_rejection(clients,field,value):
    a,b,server=clients
    raw=copy.deepcopy(a.data);raw[field]=value
    a.path.write_text(json.dumps(raw))
    with pytest.raises(Exception):ClientManifest(a.path)
    with pytest.raises(Exception):provision_client(server,Path(b.data['client_root']),b.data['principal_id'],[])
