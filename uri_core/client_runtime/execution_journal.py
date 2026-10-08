"""C4 owned-worker execution intent journal; deliberately no native runner.

After acknowledgement loss or restart, inspection/reconciliation is required;
an existing operation never grants another process launch. This is separate
from C3's reversible store-mutation journal: side effects cannot be rolled back
by restoring JSON files.
"""
import sqlite3
from contextlib import closing
from pathlib import Path

from uri_core.client_contracts import digest
from uri_core.execution_contracts import SignedTicket, ExecutionReceipt


class ExecutionJournalError(ValueError):
    pass


class ExecutionJournal:
    def __init__(self, client_root, validate_ticket=None):
        self.root = Path(client_root).resolve()
        self.validate_ticket = validate_ticket
        self.path = self.root / "control/execution-journal.sqlite3"
        # Caller is the exact client worker already holding its lifetime mutex.
        if self.path.is_symlink() or (self.root / "control").resolve() != self.root / "control" or not self.path.resolve().is_relative_to(self.root):
            raise ExecutionJournalError("JOURNAL_SCOPE")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._db()) as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version not in (0, 1):
                raise ExecutionJournalError("JOURNAL_VERSION_UNSUPPORTED")
            db.execute("CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, ticket_digest TEXT NOT NULL, state TEXT NOT NULL, receipt_digest TEXT, binding_digest TEXT NOT NULL)")
            db.execute("PRAGMA user_version=1")
            db.commit()

    def _db(self):
        db = sqlite3.connect(self.path)
        db.execute("PRAGMA synchronous=FULL")
        return db

    def intent(self, value):
        ticket = SignedTicket.model_validate(value).ticket
        if self.validate_ticket is None or self.validate_ticket(value) is not True:
            raise ExecutionJournalError("TICKET_VALIDATION_REQUIRED")
        td = digest(ticket.model_dump())
        with closing(self._db()) as db, db:
            try:
                db.execute("INSERT INTO operations VALUES (?,?,?,NULL,?)", (ticket.operation_id, td, "claim_requested", self._binding(ticket)))
            except sqlite3.IntegrityError:
                row = db.execute("SELECT ticket_digest,state FROM operations WHERE id=?", (ticket.operation_id,)).fetchone()
                raise ExecutionJournalError("OPERATION_RECONCILIATION_REQUIRED" if row[0] == td else "OPERATION_CONFLICT") from None
        return {"state": "claim_requested", "dispatch": False}

    def acknowledge(self, value, acknowledgement):
        ticket = SignedTicket.model_validate(value).ticket
        if (not isinstance(acknowledgement, dict) or set(acknowledgement) != {"state", "version", "dispatch"}
                or acknowledgement["state"] != "claimed" or type(acknowledgement["version"]) is not int
                or acknowledgement["version"] != 1 or acknowledgement["dispatch"] is not True):
            raise ExecutionJournalError("CLAIM_ACKNOWLEDGEMENT_REFUSED")
        with closing(self._db()) as db, db:
            cursor = db.execute("UPDATE operations SET state='claimed' WHERE id=? AND ticket_digest=? AND state='claim_requested'",
                                (ticket.operation_id, digest(ticket.model_dump())))
            if cursor.rowcount != 1:
                raise ExecutionJournalError("OPERATION_RECONCILIATION_REQUIRED")
        # This grants no native execution by itself: qualified runner, ticket
        # signature/fresh scope and online claim are independent prerequisites.
        return {"state": "claimed"}

    def settle(self, value):
        receipt = ExecutionReceipt.model_validate(value)
        rd = digest(receipt.model_dump())
        with closing(self._db()) as db, db:
            row = db.execute("SELECT ticket_digest,state,receipt_digest,binding_digest FROM operations WHERE id=?", (receipt.operation_id,)).fetchone()
            if row is None or row[0] != receipt.ticket_digest or row[3] != self._binding(receipt):
                raise ExecutionJournalError("RECEIPT_SCOPE")
            if row[2] is not None:
                if row[2] != rd:
                    raise ExecutionJournalError("RECEIPT_CONFLICT")
                return {"state": row[1]}
            if row[1] not in {"claimed", "execution_uncertain"}:
                raise ExecutionJournalError("RECEIPT_WITHOUT_CLAIM")
            db.execute("UPDATE operations SET state=?,receipt_digest=? WHERE id=?", (receipt.outcome, rd, receipt.operation_id))
        return {"state": receipt.outcome}

    @staticmethod
    def _binding(value):
        return digest({k: getattr(value, k) for k in ("server_id", "client_id", "principal_id", "session_id",
            "turn_id", "operation_id", "verifier_id", "implementation_digest")})

    def recover(self):
        with closing(self._db()) as db, db:
            db.execute("UPDATE operations SET state='execution_uncertain' WHERE state IN ('claim_requested','claimed')")
            rows = db.execute("SELECT id,state FROM operations").fetchall()
        return [{"operation_id": op, "state": state, "dispatch": False} for op, state in rows]
