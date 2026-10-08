"""User-selected, asynchronous qualification runs and conservative checkpoints."""
import json
import os
from pathlib import Path
import threading
import time
import uuid

from .registry import HarnessRegistry

FINAL = {'SUCCEEDED', 'FAILED', 'QUOTA_INTERRUPTED', 'CANCELLED', 'INTERRUPTED'}


class HarnessController:
    def __init__(self, service, registry=None):
        self.service = service
        self.registry = registry or HarnessRegistry(service.adapter)
        self.root = service.root / 'checkpoints'
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.records, self.cancels = {}, {}
        self.selections = {}
        for path in self.root.glob('*.json'):
            data = json.loads(path.read_text(encoding='utf-8'))
            if data['status'] not in FINAL:
                data.update(status='INTERRUPTED', potentially_non_idempotent=True,
                            result='Core restarted; outcome unknown. No automatic replay.',
                            recovery_choices=['choose', 'wait', 'local', 'stop'],
                            recommendation='Retain work; verify incomplete operations before a new approval')
                self._save(data)
            self.records[data['task_id']] = data
            if data['status'] == 'QUOTA_INTERRUPTED' and data.get('recovery_action') != 'wait':
                self.registry.quota_blocked.add(data['provider'])

    def _save(self, record):
        destination = self.root / (record['task_id'] + '.json')
        temp = destination.with_suffix('.tmp')
        with temp.open('w', encoding='utf-8') as stream:
            json.dump(record, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp, destination)

    def providers(self, refresh=False):
        with self.lock:
            rows = self.registry.snapshot(refresh)
            for row in rows:
                row['running_sessions'] = sum(r['provider'] == row['id'] and r['status'] not in FINAL
                    for r in self.records.values())
            return {'providers': rows, 'brain_configuration_changed': False,
                    'state': 'PROVISIONAL', 'general_tasks_supported': False}

    def prepare(self, user_id, provider):
        with self.lock:
            row = next((r for r in self.registry.snapshot() if r['id'] == provider), None)
            if row is None or not row['eligible']:
                raise PermissionError('HARNESS_INELIGIBLE')
            prepared = self.service.prepare(user_id)
            aid = prepared['approval_id']
            # Expired preparations are removed alongside service pending entries.
            self.selections = {k: v for k, v in self.selections.items() if k in self.service.pending}
            self.selections[aid] = (user_id, provider)
            return dict(prepared, provider=provider, model='native default',
                        workspace='URI-owned disposable fixture copy', permissions=row['permissions'])

    def start(self, user_id, approval_id, authorized):
        with self.lock:
            selected = self.selections.get(approval_id)
            if selected is None or selected[0] != user_id or authorized is not True:
                raise PermissionError('APPROVAL_REQUIRED')
            provider = selected[1]
            if not next(r for r in self.registry.snapshot() if r['id'] == provider)['eligible']:
                raise PermissionError('HARNESS_INELIGIBLE')
            if any(r['status'] not in FINAL for r in self.records.values()):
                raise PermissionError('RUN_BUSY')
            # Consume using the same authority checks as the legacy endpoint, before spawning.
            self.service.consume_approval(user_id, approval_id, authorized)
            self.selections.pop(approval_id)
            task_id = uuid.uuid4().hex
            record = {'task_id': task_id, 'user_id': user_id, 'provider': provider,
                'status': 'RUNNING', 'created_at': time.time(), 'receipt': None,
                'result': 'Executing disposable repair', 'potentially_non_idempotent': True,
                'recovery_choices': [], 'verified_completed_work': False,
                'progress': 'Native execution; final result is independently verified by URI'}
            self._save(record)
            self.records[task_id] = record
            cancel = self.cancels[task_id] = threading.Event()
            threading.Thread(target=self._execute, args=(record, approval_id, cancel), daemon=True).start()
            return self._public(record)

    def _execute(self, record, approval_id, cancel):
        try:
            # Both entry points share the service's execution semaphore.
            if not self.service.execution_slot.acquire(blocking=False):
                raise PermissionError('RUN_BUSY')
            try:
                receipt = self.service._run(record['user_id'], approval_id, cancel=cancel)
            finally:
                self.service.execution_slot.release()
            family = receipt.get('error_family')
            status = ('QUOTA_INTERRUPTED' if family == 'QUOTA' else 'CANCELLED' if receipt.get('cancelled') else
                      'SUCCEEDED' if receipt['verified'] else 'FAILED')
            with self.lock:
                record.update(receipt=receipt, status=status, result=receipt['result'],
                    verified_completed_work=(receipt.get('verification_status') == 'VERIFIED'
                                             and not receipt.get('safety_flags')),
                    potentially_non_idempotent=status != 'SUCCEEDED')
                if family == 'QUOTA':
                    self.registry.quota_blocked.add(record['provider'])
        except Exception:
            with self.lock:
                record.update(status='INTERRUPTED', result='Execution unavailable or interrupted; outcome unknown. No replay.')
        finally:
            with self.lock:
                if record['status'] != 'SUCCEEDED':
                    record['recovery_choices'] = ['choose', 'wait', 'local', 'stop']
                    record['recommendation'] = 'Retain work and wait; no alternative is qualified for this fixed repair'
                record['progress'] = 'Settled; inspect verification outcome' if record['status'] != 'INTERRUPTED' else 'Outcome unknown'
                self._save(record)
                self.cancels.pop(record['task_id'], None)

    def _owned(self, user_id, task_id):
        record = self.records.get(task_id)
        if record is None or record['user_id'] != user_id:
            raise PermissionError('TASK_NOT_FOUND')
        return record

    @staticmethod
    def _public(record):
        return {k: v for k, v in record.items() if k != 'user_id'}

    def get(self, user_id, task_id):
        with self.lock:
            return self._public(self._owned(user_id, task_id))

    def list_tasks(self, user_id):
        with self.lock:
            records = [self._public(r) for r in self.records.values() if r['user_id'] == user_id]
            return {'tasks': sorted(records, key=lambda r: r.get('created_at', 0), reverse=True)[:20]}

    def cancel(self, user_id, task_id):
        with self.lock:
            record = self._owned(user_id, task_id)
            if task_id in self.cancels:
                self.cancels[task_id].set()
                record['progress'] = 'Cancellation requested; waiting for process-tree termination'
                self._save(record)
            return self._public(record)

    def recover(self, user_id, task_id, action, authorized):
        with self.lock:
            record = self._owned(user_id, task_id)
            if authorized is not True or record['status'] not in FINAL or action not in record['recovery_choices']:
                raise PermissionError('RECOVERY_NOT_AUTHORIZED')
            # Recovery is not replay, transfer, provider switch or a new execution grant.
            if action == 'local':
                raise PermissionError('LOCAL_REPAIR_UNQUALIFIED')
            if action == 'choose' and not any(r['eligible'] and r['id'] != record['provider']
                                             for r in self.registry.snapshot()):
                raise PermissionError('NO_QUALIFIED_ALTERNATIVE')
            record['recovery_action'] = action
            record['recovery_result'] = ('Work retained. Refresh availability, prepare a new disposable run and approve again.'
                if action == 'wait' else 'Work retained. No task was transferred or replayed.')
            # Persist authorization before changing the submission gate.
            self._save(record)
            if action == 'wait':
                self.registry.quota_blocked.discard(record['provider'])
            return self._public(record)
