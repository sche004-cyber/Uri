"""Fixed, disposable qualification task; no paths, prompts or elevations from clients."""
from pathlib import Path
import hashlib
import json
import threading
import time
import uuid

from openpyxl import Workbook

from uri_v1.edge.contracts import EscalationRequest, TaskClass, TaskInput
from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.execution.harness.contracts import Limits
from uri_v1.execution.harness.contracts import HarnessError
from uri_v1.execution.harness.discovery import Inventory
from uri_v1.execution.harness.runner import HarnessRunner
from uri_v1.execution.run_record import RunStore
from uri_v1.execution.verify import VERIFIER_ID, VERIFIER_TYPE, VERIFIER_VERSION, make_memory_verifier
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers
from uri_v1.memory.sources import SourceRegistry
from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.results.version_ledger import ResultVersionLedger

TASK = 'Repair the Amount column reference in report.py in a disposable workspace'
CORRECT = b'from openpyxl import load_workbook\nwb = load_workbook("sales.xlsx")\nheader = [c.value for c in wb["Sales"][1]]\ncol = header.index("Amount")\n'
BROKEN = CORRECT.replace(b'"Amount"', b'"Amt"')


def classify_cli_errors(events):
    """Classify explicit native errors, only when the terminal result failed."""
    family = None
    failed = False
    for event in events:
        if not isinstance(event, dict):
            continue
        if event.get('type') == 'assistant' and event.get('is_api_error_message') is True:
            code = event.get('error')
            if code in ('rate_limit', 'quota_exceeded'):
                family = 'QUOTA'
            elif code in ('authentication_failed', 'unauthorized') and family != 'QUOTA':
                family = 'AUTHENTICATION'
        if event.get('type') in ('result', 'error') and (
                event.get('is_error') is True or event.get('type') == 'error'):
            failed = True
            detail = json.dumps(event).lower()
            if any(marker in detail for marker in ('rate_limit', 'rate limit', 'usage limit', 'hit your limit', 'quota')):
                family = 'QUOTA'
            elif family != 'QUOTA' and any(marker in detail for marker in ('not logged in', 'authentication', 'unauthorized')):
                family = 'AUTHENTICATION'
    return family if failed else None


class SubscriptionCLIAdapter(ClaudeCodeAdapter):
    """Reuse M38 flags; CLI alone reads its login. No credential or descriptor discovery."""
    AUTH_VARS = ()

    def inventory(self):
        return Inventory(self.harness_type, (), 'CLI_MANAGED_UNVERIFIED', ())

    def invocation(self, capsule, bundle, inventory=None):
        argv, env, prompt = super().invocation(capsule, bundle, inventory)
        # Official Windows matching uses /c/Users/... rather than C:\Users\...
        # Keep the exact M38 workspace boundary; adapt serialization only.
        scope = str(Path(capsule.workspace_files).resolve())
        normalized = permission_scope(scope)
        rules = {f'{tool}(//{scope.lstrip("/")}/**)': f'{tool}({normalized}/**)'
                 for tool in self.FILE_TOOLS}
        return [rules.get(arg, arg) for arg in argv], env, prompt

    def parse(self, proc, capsule, harness_version):
        self.permission_denial_count = 0
        self.api_key_source = 'unreported'
        self.error_family = None
        events = []
        for line in Path(proc.log_path).read_bytes().splitlines():
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue
            events.append(event)
            if event.get('type') == 'system' and event.get('subtype') == 'init':
                if 'apiKeySource' in event:
                    self.api_key_source = ('none' if event['apiKeySource'] == 'none'
                                           else 'api-key-source-reported')
            if event.get('type') == 'result' and isinstance(event.get('permission_denials'), list):
                self.permission_denial_count = len(event['permission_denials'])
        self.error_family = classify_cli_errors(events)
        return super().parse(proc, capsule, harness_version)


def permission_scope(path):
    value = path.replace('\\', '/')
    if len(value) > 2 and value[1:3] == ':/':
        return '//' + value[0].lower() + value[2:]
    if value.startswith('//'):
        raise HarnessError('NETWORK_WORKSPACE_REFUSED')
    return '//' + value.lstrip('/')


def recompute(task_class, workspace, candidate):
    # No execution of untrusted Python. Check the exact bounded task result.
    return task_class == 'DESKTOP_FIXED_REPAIR' and candidate.read_bytes().replace(b'\r\n', b'\n') == CORRECT


class DesktopHarnessService:
    def __init__(self, root, adapter=None):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.adapter = adapter or SubscriptionCLIAdapter()
        self.pending = {}
        self.lock = threading.Lock()
        self.execution_slot = threading.BoundedSemaphore(1)
        # Frozen process-wide registry: never reset or replace an existing registry.
        _bootstrap_verifiers({VERIFIER_ID: (VERIFIER_TYPE, VERIFIER_VERSION,
            make_memory_verifier(self.root / 'runs', recompute=recompute))})

    def prepare(self, user_id):
        with self.lock:
            self.pending = {key: value for key, value in self.pending.items()
                            if time.monotonic() - value[1] <= 600}
            if len(self.pending) >= 32:
                raise ValueError('TEST_CAPACITY_REACHED')
            approval_id = uuid.uuid4().hex
            self.pending[approval_id] = (user_id, time.monotonic())
        return {'approval_id': approval_id, 'task': TASK,
                'posture': 'copy-in; no shell, network tools, capabilities or write-back',
                'verification': 'exact repaired file bytes; no script execution',
                'state': 'PROVISIONAL', 'expires_in_s': 600}

    def execute(self, user_id, approval_id, authorized):
        self.consume_approval(user_id, approval_id, authorized)
        if not self.execution_slot.acquire(blocking=False):
            raise PermissionError('RUN_BUSY_APPROVAL_CONSUMED')
        try:
            return self._run(user_id, approval_id)
        finally:
            self.execution_slot.release()

    def consume_approval(self, user_id, approval_id, authorized):
        with self.lock:
            pending = self.pending.get(approval_id)
            if pending is None or pending[0] != user_id:
                raise PermissionError('APPROVAL_NOT_FOUND')
            if authorized is not True:
                raise PermissionError('EXPLICIT_APPROVAL_REQUIRED')
            if time.monotonic() - pending[1] > 600:
                self.pending.pop(approval_id)
                raise PermissionError('APPROVAL_EXPIRED')
            self.pending.pop(approval_id)  # consume before any side effect; never retry execution
    def _run(self, user_id, approval_id, cancel=None):
        started = time.monotonic()
        trace = uuid.uuid4().hex
        base = self.root / 'fixtures' / user_id / trace
        base.mkdir(parents=True)
        (base / 'report.py').write_bytes(BROKEN)
        wb = Workbook(); ws = wb.active; ws.title = 'Sales'
        ws.append(['Region', 'Amount']); ws.append(['North', 10]); wb.save(base / 'sales.xlsx')
        log = MemoryLog(user_id, self.root / 'private')
        sources = SourceRegistry(log); sources.register(base)
        recorder = Recorder(log, sources)
        intake = URIIntake().capture(user_id, approval_id, trace, uuid.uuid4().hex, TASK, spans={})
        task_id, opened = recorder.open_task(intake, TASK)
        if not opened.persisted:
            raise ValueError('TASK_RECORD_FAILED')
        refs = {loc.relpath: sources.fingerprint(loc) for loc in sources.scan().locators}
        criteria = AcceptanceCriteria(1, (
            {'kind': 'only_changed', 'paths': ['report.py']},
            {'kind': 'report_recomputes', 'path': 'report.py', 'task_class': 'DESKTOP_FIXED_REPAIR'}))
        escalation = EscalationRequest(task_id, TaskClass.SCRIPT_WORKBOOK_REPAIR,
            tuple(TaskInput(role, refs[name].source_id, refs[name].content_sha256)
                  for role, name in [('script', 'report.py'), ('workbook', 'sales.xlsx')]),
            criteria.to_dict(), criteria.sha256,
            {},
            ('Change only header.index("Amt") to header.index("Amount"). Do not execute any code.',), trace)
        runner = HarnessRunner(user_id=user_id, scratch_root=self.root / 'scratch',
            run_store=RunStore(user_id, self.root / 'runs'), recorder=recorder,
            ledger=ResultVersionLedger(user_id, root=str(self.root / 'results')), sources=sources)
        outcome = runner.run(escalation, self.adapter, session_id=approval_id,
                             limits=Limits(timeout_s=120, inactivity_s=60, max_budget_usd=None), cancel=cancel)
        execution_ok = (outcome.claimed_outcome == 'completed_claimed'
                        and outcome.metrics['exit_code'] == 0
                        and not outcome.metrics['timed_out']
                        and not outcome.metrics['inactivity_killed']
                        and not outcome.metrics['cancelled']
                        and getattr(self.adapter, 'api_key_source', 'unreported') != 'api-key-source-reported')
        test_passed = outcome.verified and execution_ok
        # Return URI's receipt only, never CLI transcripts, session handles or auth metadata.
        return {'state': 'PROVISIONAL', 'run_id': outcome.run_id,
                'verified': test_passed, 'verification_status': outcome.verification_status,
                'execution_ok': execution_ok,
                'permission_denial_count': getattr(self.adapter, 'permission_denial_count', None),
                'api_key_source': getattr(self.adapter, 'api_key_source', 'unreported'),
                'claimed_outcome': outcome.claimed_outcome, 'safety_flags': list(outcome.safety_flags),
                'harness_duration_ms': outcome.metrics['duration_ms'],
                'core_duration_ms': round((time.monotonic() - started) * 1000, 1),
                'exit_code': outcome.metrics['exit_code'], 'timed_out': outcome.metrics['timed_out'],
                'inactivity_killed': outcome.metrics['inactivity_killed'],
                'cancelled': outcome.metrics['cancelled'],
                'error_family': getattr(self.adapter, 'error_family', None),
                'tool_calls': outcome.metrics.get('tool_calls', 'unknown'),
                'result': ('Amount column reference repaired' if test_passed else
                           'Quota interrupted; work retained. Explicit recovery required.' if getattr(self.adapter, 'error_family', None) == 'QUOTA' else
                           'Desktop harness test did not pass'),
                'expected_result_sha256': hashlib.sha256(CORRECT).hexdigest(),
                'write_back': False}
