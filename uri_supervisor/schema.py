"""SQLite ledger schema (version 1).

Mechanical invariants live in triggers so no code path (including a stale attempt or a buggy
caller) can bypass them:
  A  no durable admission            -> attempt cannot enter SPAWNING
  B  no durable effect intent        -> attempt cannot enter SPAWNING; stale fences cannot declare
  C  no sufficient evidence          -> task cannot become COMPLETE
  D  retries must reuse key/params   -> retry intents must equal the original
  U  UNCERTAIN/NEEDS_USER exits need NEW URI-observed evidence or a recorded human decision
  F  stale-fence writes are refused  -> authoritative attempt-scoped inserts need the current fence
  K  SUM(held claims per pool) <= capacity, enforced inside the claiming transaction
Append-only tables reject UPDATE and DELETE.
"""

STATES = ("QUEUED", "RUNNING", "RECOVERING", "COMPLETE", "RETRY_SAFE", "UNCERTAIN", "FAILED", "NEEDS_USER")
OP_CLASSES = ("read", "idem_write", "local_write", "external")

# (from, to, basis_required)
TRANSITIONS = [
    ("QUEUED", "RUNNING", 0), ("QUEUED", "FAILED", 0), ("QUEUED", "NEEDS_USER", 0),
    ("RUNNING", "RECOVERING", 0), ("RUNNING", "COMPLETE", 0),
    ("RECOVERING", "COMPLETE", 0), ("RECOVERING", "RETRY_SAFE", 0), ("RECOVERING", "UNCERTAIN", 0),
    ("RECOVERING", "FAILED", 0), ("RECOVERING", "NEEDS_USER", 0),
    ("RETRY_SAFE", "RUNNING", 0), ("RETRY_SAFE", "FAILED", 0), ("RETRY_SAFE", "NEEDS_USER", 0),
    ("UNCERTAIN", "NEEDS_USER", 0),  # escalation only; releases nothing
    ("UNCERTAIN", "COMPLETE", 1), ("UNCERTAIN", "RETRY_SAFE", 1), ("UNCERTAIN", "FAILED", 1),
    ("NEEDS_USER", "COMPLETE", 1), ("NEEDS_USER", "RETRY_SAFE", 1), ("NEEDS_USER", "FAILED", 1),
]

APPEND_ONLY = ("event", "admission", "effect_intent", "effect_observation", "stream_event", "stream_interpretation",
               "evidence", "postcondition", "postcondition_result", "completion_record", "recovery_decision",
               "user_decision", "scheduler_epoch")

_STALE = ("SELECT RAISE(ABORT,'STALE_FENCE') WHERE NOT EXISTS (SELECT 1 FROM task t JOIN attempt a "
          "ON a.task_id=t.task_id AND a.attempt_id=NEW.attempt_id WHERE t.task_id=NEW.task_id "
          "AND t.current_fence=NEW.attempt_id AND a.status<>'FENCED');")

_STATE_LIST = ",".join("'%s'" % s for s in STATES)

SQL = """
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE scheduler_epoch(
  epoch INTEGER PRIMARY KEY AUTOINCREMENT, instance_id TEXT NOT NULL UNIQUE,
  started_at_us INTEGER NOT NULL, owner_pid INTEGER, owner_create_time INTEGER);
CREATE TABLE event(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, task_id TEXT, attempt_id INTEGER,
  occurred_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL, ref_table TEXT, ref_id INTEGER, payload TEXT);
CREATE INDEX event_task ON event(task_id, seq);

CREATE TABLE resource_pool(
  name TEXT PRIMARY KEY, capacity INTEGER NOT NULL CHECK(capacity>=0), kind TEXT NOT NULL DEFAULT 'generic',
  breaker_state TEXT NOT NULL DEFAULT 'closed' CHECK(breaker_state IN ('closed','open','half_open')),
  breaker_failures INTEGER NOT NULL DEFAULT 0, breaker_until_wall_us INTEGER, breaker_until_mono_ns INTEGER,
  breaker_epoch INTEGER, probe_attempt_id INTEGER, breaker_reason TEXT, updated_at_us INTEGER NOT NULL);

CREATE TABLE executor_registration(
  registration_id INTEGER PRIMARY KEY AUTOINCREMENT, executor_id TEXT NOT NULL, version TEXT,
  spec_json TEXT NOT NULL, capabilities_json TEXT NOT NULL, claims_json TEXT NOT NULL,
  preemptible INTEGER NOT NULL DEFAULT 0, safe_points_json TEXT NOT NULL DEFAULT '[]',
  quota_pools_json TEXT NOT NULL DEFAULT '[]',
  valid_from_us INTEGER NOT NULL, valid_until_us INTEGER, recorded_at_us INTEGER NOT NULL, superseded_at_us INTEGER);
CREATE INDEX registration_exec ON executor_registration(executor_id, registration_id);

CREATE TABLE task(
  task_seq INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL UNIQUE, principal TEXT NOT NULL,
  request_json TEXT NOT NULL, request_sha256 TEXT NOT NULL, requirements_json TEXT NOT NULL DEFAULT '{}',
  timezone TEXT, base_priority INTEGER NOT NULL DEFAULT 0, enqueue_round INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN (__STATES__)),
  reason_code TEXT, reason_detail TEXT, current_fence INTEGER, attempt_count INTEGER NOT NULL DEFAULT 0,
  max_attempts INTEGER NOT NULL DEFAULT 3, created_at_us INTEGER NOT NULL, state_changed_at_us INTEGER NOT NULL,
  enter_evidence_hwm INTEGER NOT NULL DEFAULT 0, enter_decision_hwm INTEGER NOT NULL DEFAULT 0,
  basis_kind TEXT, basis_ref INTEGER, completion_ref INTEGER);
CREATE INDEX task_state ON task(state, task_seq);

CREATE TABLE authorization(
  auth_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES task(task_id), scope_json TEXT NOT NULL,
  issued_by TEXT NOT NULL, valid_from_us INTEGER NOT NULL, valid_until_us INTEGER, recorded_at_us INTEGER NOT NULL,
  superseded_at_us INTEGER, superseded_by INTEGER);

CREATE TABLE allowed_transition(from_state TEXT NOT NULL, to_state TEXT NOT NULL, basis_required INTEGER NOT NULL,
  PRIMARY KEY(from_state,to_state));

CREATE TABLE attempt(
  attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL REFERENCES task(task_id), attempt_no INTEGER NOT NULL,
  executor_id TEXT NOT NULL, registration_id INTEGER NOT NULL REFERENCES executor_registration(registration_id),
  executor_version TEXT, status TEXT NOT NULL CHECK(status IN ('ADMITTED','SPAWNING','RUNNING','ENDED','FENCED')),
  epoch INTEGER NOT NULL, pid INTEGER, pid_create_time INTEGER, job_name TEXT, argv_sha256 TEXT, session_id TEXT,
  resume_of INTEGER, at_safe_point INTEGER NOT NULL DEFAULT 0,
  admitted_at_us INTEGER NOT NULL, spawned_at_us INTEGER, ended_at_us INTEGER, fenced_at_us INTEGER,
  exit_code INTEGER, end_reason TEXT, UNIQUE(task_id, attempt_no));

CREATE TABLE admission(
  admission_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER NOT NULL UNIQUE,
  auth_id INTEGER NOT NULL, epoch INTEGER NOT NULL, registration_id INTEGER NOT NULL, round INTEGER NOT NULL,
  claims_json TEXT NOT NULL, admitted_at_us INTEGER NOT NULL);

CREATE TABLE claim(
  claim_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER NOT NULL,
  pool TEXT NOT NULL REFERENCES resource_pool(name), amount INTEGER NOT NULL CHECK(amount>0), epoch INTEGER NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('held','released','revoked')), lease_ns INTEGER NOT NULL,
  lease_deadline_mono_ns INTEGER NOT NULL, acquired_at_us INTEGER NOT NULL, ended_at_us INTEGER, end_reason TEXT);
CREATE INDEX claim_pool ON claim(pool, state);

CREATE TABLE effect_intent(
  intent_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER NOT NULL,
  op_class TEXT NOT NULL CHECK(op_class IN ('read','idem_write','local_write','external')), operation TEXT NOT NULL,
  target TEXT, params_hash TEXT NOT NULL, idempotency_key TEXT, retry_of INTEGER, pre_state_json TEXT,
  executor_id TEXT, executor_session TEXT, declared_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL);
CREATE INDEX intent_task ON effect_intent(task_id, intent_id);

CREATE TABLE effect_observation(
  obs_id INTEGER PRIMARY KEY AUTOINCREMENT, intent_id INTEGER NOT NULL REFERENCES effect_intent(intent_id),
  task_id TEXT NOT NULL, attempt_id INTEGER, status TEXT NOT NULL CHECK(status IN ('APPLIED','ABSENT','PARTIAL','UNKNOWN')),
  basis TEXT NOT NULL, evidence_id INTEGER, observed_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL,
  recorded_by TEXT NOT NULL CHECK(recorded_by IN ('attempt','supervisor','recovery')));

CREATE TABLE stream_event(
  stream_event_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER NOT NULL,
  stream TEXT NOT NULL CHECK(stream IN ('stdout','stderr')), line_no INTEGER NOT NULL, raw BLOB NOT NULL,
  raw_sha256 TEXT NOT NULL, complete INTEGER NOT NULL, received_at_us INTEGER NOT NULL, fence_current INTEGER NOT NULL,
  UNIQUE(attempt_id, stream, line_no));
CREATE TABLE stream_interpretation(
  interp_id INTEGER PRIMARY KEY AUTOINCREMENT, stream_event_id INTEGER NOT NULL UNIQUE REFERENCES stream_event(stream_event_id),
  parser_id TEXT NOT NULL, parse_status TEXT NOT NULL, event_type TEXT, semantics TEXT NOT NULL, extracted TEXT NOT NULL);

CREATE TABLE evidence(
  evidence_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER,
  source TEXT NOT NULL CHECK(source IN ('executor_report','uri_observed','uri_verified','user')), kind TEXT NOT NULL,
  subject TEXT, payload TEXT NOT NULL, stream_event_id INTEGER, occurred_at_us INTEGER NOT NULL,
  recorded_at_us INTEGER NOT NULL, recorded_by TEXT NOT NULL CHECK(recorded_by IN ('attempt','supervisor','recovery')));
CREATE INDEX evidence_task ON evidence(task_id, evidence_id);

CREATE TABLE postcondition(
  postcondition_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, kind TEXT NOT NULL, spec_json TEXT NOT NULL,
  required INTEGER NOT NULL DEFAULT 1, declared_at_us INTEGER NOT NULL);
CREATE TABLE postcondition_result(
  result_id INTEGER PRIMARY KEY AUTOINCREMENT, postcondition_id INTEGER NOT NULL REFERENCES postcondition(postcondition_id),
  task_id TEXT NOT NULL, attempt_id INTEGER, status TEXT NOT NULL CHECK(status IN ('PASS','FAIL','INDETERMINATE')),
  evidence_id INTEGER NOT NULL REFERENCES evidence(evidence_id), checked_at_us INTEGER NOT NULL);

CREATE TABLE completion_record(
  completion_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER,
  kind TEXT NOT NULL CHECK(kind IN ('verified','user_accepted')), basis_json TEXT NOT NULL, recorded_at_us INTEGER NOT NULL);

CREATE TABLE uncertainty(
  uncertainty_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER, intent_id INTEGER,
  reason_code TEXT NOT NULL, detail TEXT, opened_at_us INTEGER NOT NULL, resolved_at_us INTEGER,
  resolution_kind TEXT, resolution_ref INTEGER);

CREATE TABLE recovery_decision(
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, attempt_id INTEGER NOT NULL,
  epoch INTEGER NOT NULL, outcome TEXT NOT NULL CHECK(outcome IN ('COMPLETE','RETRY_SAFE','UNCERTAIN','FAILED','NEEDS_USER')),
  action TEXT NOT NULL CHECK(action IN ('NONE','RETRY_FRESH','RETRY_SAME_KEY','RESUME_SESSION','ESCALATE')),
  reason_code TEXT NOT NULL, evidence_json TEXT NOT NULL, decided_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL,
  UNIQUE(task_id, attempt_id));

CREATE TABLE user_decision(
  decision_id INTEGER PRIMARY KEY AUTOINCREMENT, task_id TEXT NOT NULL, uncertainty_id INTEGER,
  choice TEXT NOT NULL CHECK(choice IN ('retry','abandon','accept_as_complete')), rationale TEXT, principal TEXT NOT NULL,
  decided_at_us INTEGER NOT NULL, recorded_at_us INTEGER NOT NULL);

-- ---------- triggers ----------
CREATE TRIGGER task_transition BEFORE UPDATE OF state ON task WHEN OLD.state<>NEW.state BEGIN
  SELECT RAISE(ABORT,'ILLEGAL_TRANSITION') WHERE NOT EXISTS
    (SELECT 1 FROM allowed_transition WHERE from_state=OLD.state AND to_state=NEW.state);
  SELECT RAISE(ABORT,'UNCERTAIN_EXIT_REQUIRES_EVIDENCE_OR_DECISION') WHERE
    OLD.state IN ('UNCERTAIN','NEEDS_USER') AND NEW.state NOT IN ('UNCERTAIN','NEEDS_USER') AND NOT (
      (NEW.basis_kind='evidence' AND EXISTS(SELECT 1 FROM evidence e WHERE e.evidence_id=NEW.basis_ref
         AND e.task_id=NEW.task_id AND e.evidence_id>OLD.enter_evidence_hwm AND e.source IN ('uri_observed','uri_verified')
         AND e.kind IN ('postcondition_check','effect_absent','external_reconcile')))
      OR (NEW.basis_kind='user_decision' AND EXISTS(SELECT 1 FROM user_decision d WHERE d.decision_id=NEW.basis_ref
         AND d.task_id=NEW.task_id AND d.decision_id>OLD.enter_decision_hwm)));
  SELECT RAISE(ABORT,'COMPLETE_REQUIRES_COMPLETION_RECORD') WHERE NEW.state='COMPLETE' AND NOT EXISTS
    (SELECT 1 FROM completion_record c WHERE c.completion_id=NEW.completion_ref AND c.task_id=NEW.task_id);
  SELECT RAISE(ABORT,'RETRY_BUDGET_EXHAUSTED') WHERE NEW.state='RETRY_SAFE' AND NEW.attempt_count>=NEW.max_attempts;
END;
CREATE TRIGGER task_fence_monotonic BEFORE UPDATE OF current_fence ON task WHEN NEW.current_fence IS NOT NULL BEGIN
  SELECT RAISE(ABORT,'FENCE_NOT_LATEST') WHERE NEW.current_fence<>
    (SELECT MAX(attempt_id) FROM attempt WHERE task_id=NEW.task_id);
END;
CREATE TRIGGER task_no_delete BEFORE DELETE ON task BEGIN SELECT RAISE(ABORT,'TASK_IMMUTABLE_HISTORY'); END;
CREATE TRIGGER task_identity BEFORE UPDATE OF task_id, principal, request_json, request_sha256, created_at_us ON task
  BEGIN SELECT RAISE(ABORT,'TASK_IDENTITY_IMMUTABLE'); END;

CREATE TRIGGER attempt_status BEFORE UPDATE OF status ON attempt WHEN OLD.status<>NEW.status BEGIN
  SELECT RAISE(ABORT,'ILLEGAL_ATTEMPT_TRANSITION') WHERE NOT (
    (OLD.status='ADMITTED' AND NEW.status IN ('SPAWNING','FENCED')) OR
    (OLD.status='SPAWNING' AND NEW.status IN ('RUNNING','ENDED','FENCED')) OR
    (OLD.status='RUNNING' AND NEW.status IN ('ENDED','FENCED')) OR
    (OLD.status='ENDED' AND NEW.status='FENCED'));
  SELECT RAISE(ABORT,'NO_DURABLE_ADMISSION') WHERE NEW.status='SPAWNING' AND NOT EXISTS
    (SELECT 1 FROM admission WHERE attempt_id=NEW.attempt_id);
  SELECT RAISE(ABORT,'NO_DURABLE_EFFECT_INTENT') WHERE NEW.status='SPAWNING' AND NOT EXISTS
    (SELECT 1 FROM effect_intent WHERE attempt_id=NEW.attempt_id);
  SELECT RAISE(ABORT,'SPAWN_CLAIMS_NOT_HELD') WHERE NEW.status='SPAWNING' AND NOT EXISTS
    (SELECT 1 FROM claim WHERE attempt_id=NEW.attempt_id AND state='held');
  SELECT RAISE(ABORT,'SPAWN_NOT_CURRENT_FENCE') WHERE NEW.status='SPAWNING' AND NOT EXISTS
    (SELECT 1 FROM task WHERE task_id=NEW.task_id AND current_fence=NEW.attempt_id AND state='RUNNING');
END;
CREATE TRIGGER attempt_identity_once BEFORE UPDATE OF pid, pid_create_time, job_name ON attempt
  WHEN OLD.pid IS NOT NULL AND (NEW.pid IS NOT OLD.pid OR NEW.pid_create_time IS NOT OLD.pid_create_time OR NEW.job_name IS NOT OLD.job_name)
  BEGIN SELECT RAISE(ABORT,'PROCESS_IDENTITY_IMMUTABLE'); END;
CREATE TRIGGER attempt_no_delete BEFORE DELETE ON attempt BEGIN SELECT RAISE(ABORT,'ATTEMPT_IMMUTABLE_HISTORY'); END;

CREATE TRIGGER claim_capacity BEFORE INSERT ON claim WHEN NEW.state='held' BEGIN
  SELECT RAISE(ABORT,'POOL_CAPACITY_EXCEEDED') WHERE
    (SELECT COALESCE(SUM(amount),0) FROM claim WHERE pool=NEW.pool AND state='held')+NEW.amount >
    (SELECT capacity FROM resource_pool WHERE name=NEW.pool);
END;
CREATE TRIGGER claim_transition BEFORE UPDATE ON claim BEGIN
  SELECT RAISE(ABORT,'CLAIM_IMMUTABLE_FIELDS') WHERE NEW.pool<>OLD.pool OR NEW.amount<>OLD.amount OR NEW.task_id<>OLD.task_id
    OR NEW.attempt_id<>OLD.attempt_id OR NEW.epoch<>OLD.epoch;
  SELECT RAISE(ABORT,'CLAIM_NOT_RESURRECTABLE') WHERE OLD.state<>'held' AND NEW.state<>OLD.state;
END;
CREATE TRIGGER claim_no_delete BEFORE DELETE ON claim BEGIN SELECT RAISE(ABORT,'CLAIM_HISTORY_IMMUTABLE'); END;
CREATE TRIGGER pool_capacity_floor BEFORE UPDATE OF capacity ON resource_pool BEGIN
  SELECT RAISE(ABORT,'CAPACITY_BELOW_HELD') WHERE NEW.capacity <
    (SELECT COALESCE(SUM(amount),0) FROM claim WHERE pool=NEW.name AND state='held');
END;

CREATE TRIGGER intent_fence BEFORE INSERT ON effect_intent BEGIN __STALE__ END;
CREATE TRIGGER intent_retry_equal BEFORE INSERT ON effect_intent WHEN NEW.retry_of IS NOT NULL BEGIN
  SELECT RAISE(ABORT,'RETRY_PARAMS_MISMATCH') WHERE NOT EXISTS (SELECT 1 FROM effect_intent o WHERE o.intent_id=NEW.retry_of
    AND o.task_id=NEW.task_id AND o.op_class=NEW.op_class AND o.params_hash=NEW.params_hash
    AND o.idempotency_key IS NEW.idempotency_key);
END;
CREATE TRIGGER intent_idem_key BEFORE INSERT ON effect_intent WHEN NEW.op_class='idem_write' AND NEW.idempotency_key IS NULL BEGIN
  SELECT RAISE(ABORT,'IDEMPOTENT_WRITE_REQUIRES_KEY');
END;
CREATE TRIGGER evidence_fence BEFORE INSERT ON evidence WHEN NEW.recorded_by='attempt' BEGIN __STALE__ END;
CREATE TRIGGER evidence_executor_source BEFORE INSERT ON evidence WHEN NEW.source='executor_report' AND NEW.recorded_by='supervisor' BEGIN
  SELECT RAISE(ABORT,'EXECUTOR_EVIDENCE_NEEDS_ATTEMPT_OR_RECOVERY');
END;
CREATE TRIGGER observation_fence BEFORE INSERT ON effect_observation WHEN NEW.recorded_by='attempt' BEGIN __STALE__ END;

CREATE TRIGGER pcr_evidence_kind BEFORE INSERT ON postcondition_result WHEN NEW.status='PASS' BEGIN
  SELECT RAISE(ABORT,'PASS_REQUIRES_VERIFIED_EVIDENCE') WHERE NOT EXISTS (
    SELECT 1 FROM evidence e JOIN postcondition p ON p.postcondition_id=NEW.postcondition_id
    WHERE e.evidence_id=NEW.evidence_id AND e.task_id=NEW.task_id AND (e.source='uri_verified'
       OR (p.kind='terminal_success' AND e.source='executor_report' AND e.kind='terminal_success_claim')));
END;
CREATE TRIGGER completion_verified BEFORE INSERT ON completion_record WHEN NEW.kind='verified' BEGIN
  SELECT RAISE(ABORT,'NO_REQUIRED_POSTCONDITION') WHERE NOT EXISTS
    (SELECT 1 FROM postcondition WHERE task_id=NEW.task_id AND required=1);
  SELECT RAISE(ABORT,'POSTCONDITION_NOT_PROVEN') WHERE EXISTS (
    SELECT 1 FROM postcondition p WHERE p.task_id=NEW.task_id AND p.required=1 AND NOT EXISTS (
      SELECT 1 FROM postcondition_result r WHERE r.postcondition_id=p.postcondition_id AND r.status='PASS'
        AND r.result_id=(SELECT MAX(r2.result_id) FROM postcondition_result r2 WHERE r2.postcondition_id=p.postcondition_id)
        AND (p.kind<>'terminal_success' OR NOT EXISTS
             (SELECT 1 FROM effect_intent i WHERE i.task_id=NEW.task_id AND i.op_class<>'read'))));
END;
CREATE TRIGGER completion_user BEFORE INSERT ON completion_record WHEN NEW.kind='user_accepted' BEGIN
  SELECT RAISE(ABORT,'NO_USER_ACCEPTANCE') WHERE NOT EXISTS
    (SELECT 1 FROM user_decision WHERE task_id=NEW.task_id AND choice='accept_as_complete');
END;
CREATE TRIGGER uncertainty_resolve BEFORE UPDATE ON uncertainty BEGIN
  SELECT RAISE(ABORT,'UNCERTAINTY_IMMUTABLE') WHERE OLD.resolved_at_us IS NOT NULL OR NEW.task_id<>OLD.task_id
    OR NEW.reason_code<>OLD.reason_code OR NEW.opened_at_us<>OLD.opened_at_us;
END;
CREATE TRIGGER uncertainty_no_delete BEFORE DELETE ON uncertainty BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER registration_versioned BEFORE UPDATE ON executor_registration BEGIN
  SELECT RAISE(ABORT,'REGISTRATION_IMMUTABLE') WHERE NEW.spec_json<>OLD.spec_json OR NEW.claims_json<>OLD.claims_json
    OR NEW.capabilities_json<>OLD.capabilities_json OR NEW.executor_id<>OLD.executor_id OR NEW.valid_from_us<>OLD.valid_from_us;
END;
CREATE TRIGGER registration_no_delete BEFORE DELETE ON executor_registration BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
CREATE TRIGGER authorization_versioned BEFORE UPDATE ON authorization BEGIN
  SELECT RAISE(ABORT,'AUTHORIZATION_IMMUTABLE') WHERE NEW.scope_json<>OLD.scope_json OR NEW.valid_from_us<>OLD.valid_from_us
    OR NEW.task_id<>OLD.task_id OR OLD.superseded_at_us IS NOT NULL;
END;
CREATE TRIGGER authorization_no_delete BEFORE DELETE ON authorization BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;
"""

SQL = SQL.replace("__STATES__", _STATE_LIST).replace("__STALE__", _STALE)


def append_only_sql():
    out = []
    for t in APPEND_ONLY:
        out.append(f"CREATE TRIGGER {t}_no_update BEFORE UPDATE ON {t} BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;")
        out.append(f"CREATE TRIGGER {t}_no_delete BEFORE DELETE ON {t} BEGIN SELECT RAISE(ABORT,'APPEND_ONLY'); END;")
    return "\n".join(out)
