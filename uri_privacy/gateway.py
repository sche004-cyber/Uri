"""The privacy gateway (plan 2.6): call `prepare()` immediately before data leaves URI, `restore()` on local output.

prepare() classifies, looks up the policy action for every finding at the destination, applies live grants, then
either refuses (nothing may be sent) or returns the text with only what the destination needs. Every decision,
including refusals, is audited without values. Any internal error, an audit failure, an unknown destination or a
non-text input is a refusal: the gateway never fails open.
"""
from __future__ import annotations

import logging
import os
import threading
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from . import classify as C
from . import policy as P
from .audit import PrivacyAudit
from .grants import GrantStore
from .vault import MemoryVaultStore, PersistentVaultStore, VaultError

log = logging.getLogger("uri_privacy")
REDACTED = "[redacted]"
DEFAULT_SCOPE_TTL_S = 3600


class PrivacyRefused(Exception):
    """Nothing may be sent. `code` is safe to show and log; `needs` lists (category, destination) a grant could cover."""

    def __init__(self, code, needs=()):
        super().__init__(code)
        self.code = code
        self.needs = tuple(needs)


@dataclass
class Egress:
    text: str
    destination: str
    categories: dict                    # category -> count found
    actions: dict                       # category -> action applied
    scope: str | None = None            # set when references were created (restore with it)
    grant_ids: list = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return any(a in (P.PSEUDONYMIZE, P.REDACT) for a in self.actions.values())


class PrivacyGateway:
    def __init__(self, *, audit=None, grants=None, vault=None, requesters=(), purposes=()):
        self.audit = audit or PrivacyAudit()
        self.grants = grants or GrantStore()
        self.vault = vault or MemoryVaultStore()
        # Trusted identifiers: the registry plus what the wiring code that builds this gateway adds.
        self.requesters = P.KNOWN_REQUESTERS | frozenset(requesters)
        self.purposes = P.KNOWN_PURPOSES | frozenset(purposes)
        self.audit.trust(self.requesters, self.purposes)

    # -- egress -------------------------------------------------------------------------------------------------------
    def prepare(self, text, *, requester, destination, purpose, task_id=None, scope=None, protected_terms=(),
                reversible=True, ttl_s=DEFAULT_SCOPE_TTL_S) -> Egress:
        meta = {"requester": requester, "task_id": task_id, "purpose": purpose,
                "destination": str(getattr(destination, "value", destination)), "policy": P.POLICY_ID}
        try:
            self._check_identity(meta)
            result = self._decide(text, meta, scope, protected_terms, reversible, ttl_s)
        except PrivacyRefused as exc:
            self._audit_refusal(meta, exc)
            raise
        except Exception as exc:                                    # noqa: BLE001 - fail closed on anything unexpected
            log.warning("privacy gateway internal error (%s); egress refused", type(exc).__name__)
            err = PrivacyRefused("PRIVACY_INTERNAL_ERROR")
            self._audit_refusal(meta, err)
            raise err from None
        return result

    def _check_identity(self, meta):
        if meta["requester"] not in self.requesters:
            raise PrivacyRefused("PRIVACY_REQUESTER_UNKNOWN")
        if meta["purpose"] not in self.purposes:
            raise PrivacyRefused("PRIVACY_PURPOSE_UNKNOWN")

    def _audit_refusal(self, meta, exc):
        try:
            self.audit.write(**meta, decision=P.REFUSE, categories=getattr(exc, "categories", None), grant_ids=[],
                             outcome="REFUSED", code=exc.code)
        except Exception:                                           # noqa: BLE001 - refusal stands either way
            log.warning("privacy audit write failed for a refusal")

    def _decide(self, text, meta, scope, protected_terms, reversible, ttl_s) -> Egress:
        if not isinstance(text, str):
            raise PrivacyRefused("PRIVACY_INPUT_NOT_TEXT")
        try:
            dest = P.Destination(meta["destination"])
        except ValueError:
            raise PrivacyRefused("PRIVACY_DESTINATION_UNKNOWN") from None
        # Unicode, encodings and look-alikes are handled inside classify() (folding with an exact span map).
        cls = C.classify(text, protected_terms)
        if cls.residual_encoding and dest not in P.LOCAL:
            raise PrivacyRefused("PRIVACY_ENCODING_UNRESOLVED")     # deeper than the folding decodes (FB1 R1-04)
        counts = cls.categories()

        # One action per category present; a grant can lower a grantable action to ALLOW.
        actions, grant_ids, needs = {}, [], []
        for cat in counts:
            act = P.action(cat, dest)
            if act != P.ALLOW and P.grantable(cat, dest):
                gid = self.grants.match(requester=meta["requester"], category=cat, purpose=meta["purpose"],
                                        destination=dest)
                if gid:
                    act = P.ALLOW
                    if gid not in grant_ids:
                        grant_ids.append(gid)
            if act == P.PSEUDONYMIZE and not reversible:
                act = P.REDACT
            if act == P.REQUIRE_GRANT:
                needs.append((cat, dest.value))
            actions[cat] = act
        cats = dict(sorted(counts.items()))
        if any(a == P.REFUSE for a in actions.values()):
            e = PrivacyRefused("PRIVACY_REFUSED")
            e.categories = cats
            raise e
        if needs:
            e = PrivacyRefused("PRIVACY_GRANT_REQUIRED", needs)
            e.categories = cats
            raise e
        out, scope_id = self._rewrite(text, cls, actions, dest, scope, ttl_s, meta["requester"])
        if dest == P.Destination.LOG and cls.credential_kinds:
            from uri_assist.redact import redact_text
            out = redact_text(out, Counter())
        if dest == P.Destination.WEB_SEARCH:
            out = " ".join(out.split())
        # Re-check what will actually be sent (review S1-01): rewriting or whitespace collapse must never assemble a
        # value the policy does not allow at this destination. Anything left over is a refusal, not a second rewrite.
        # Unchanged output is the input already classified above (deterministic), every category of which was allowed,
        # so the second pass only runs when something was rewritten or collapsed.
        if dest not in P.LOCAL and out != text:
            residual = C.classify(out, protected_terms).categories()
            if any(actions.get(c, P.action(c, dest)) != P.ALLOW for c in residual):
                e = PrivacyRefused("PRIVACY_REFUSED")
                e.categories = cats
                raise e
        # Grants are used only once the rewrite succeeded (review S1-06), right before the decision is recorded.
        if grant_ids and not self.grants.consume(grant_ids):
            raise PrivacyRefused("PRIVACY_GRANT_RACE")              # used up or revoked between match and use
        self.audit.write(**meta, decision=_summary(actions), categories=cats, grant_ids=grant_ids,
                         outcome="SANITIZED" if any(a != P.ALLOW for a in actions.values()) else "ALLOWED", code=None)
        return Egress(out, dest.value, cats, actions, scope_id, grant_ids)

    @staticmethod
    def _span_action(f, actions):
        """The strictest action over every category merged into this span (review S1-02): a grant for one category never
        releases another category in the same span."""
        return max((actions.get(c, P.REFUSE) for c in f.all_categories), key=lambda a: P.STRICTNESS[a])

    def _rewrite(self, text, cls, actions, dest, scope, ttl_s, requester):
        plan = [(f, self._span_action(f, actions)) for f in cls.findings]
        rewrite = [(f, a) for f, a in plan if a in (P.PSEUDONYMIZE, P.REDACT)]
        if not rewrite:
            return text, None
        sc = None
        if any(a == P.PSEUDONYMIZE for _, a in rewrite):
            sc = self.vault.open(scope or ("s-" + uuid.uuid4().hex), ttl_s, requester=requester)
        parts, pos = [], 0
        for f, a in rewrite:
            parts.append(text[pos:f.start])
            # A visible placeholder, never an empty string: removing a value must not join its neighbours (S1-01).
            parts.append(sc.token_for(f.category, text[f.start:f.end]) if a == P.PSEUDONYMIZE else REDACTED)
            pos = f.end
        parts.append(text[pos:])
        if sc is not None:
            self.vault.save(sc)
        return "".join(parts), (sc.scope_id if sc is not None else None)

    # -- local reconstruction -------------------------------------------------------------------------------------------
    def restore(self, text, scope, *, requester, destination=P.Destination.LOCAL_TOOL, task_id=None) -> str:
        """Resolve this scope's references, only for a local destination. Foreign tokens stay as they are."""
        meta = {"requester": requester, "task_id": task_id, "purpose": "restore",
                "destination": str(getattr(destination, "value", destination)), "policy": P.POLICY_ID}
        try:
            self._check_identity(meta)
            if not isinstance(text, str):
                raise PrivacyRefused("PRIVACY_INPUT_NOT_TEXT")
            if P.Destination(meta["destination"]) not in P.LOCAL:
                raise PrivacyRefused("PRIVACY_RESTORE_NOT_LOCAL")
            sc = self.vault.get(scope) if isinstance(scope, str) else None
            if sc is None:
                raise PrivacyRefused("PRIVACY_SCOPE_UNKNOWN")
            if sc.requester != meta["requester"]:
                raise PrivacyRefused("PRIVACY_SCOPE_OWNER_MISMATCH")
            out, restored, foreign = sc.restore(text)
        except PrivacyRefused as exc:
            self._audit_refusal(meta, exc)
            raise
        except Exception as exc:                                    # noqa: BLE001 - fail closed and audited (S1-07)
            code = exc.code if isinstance(exc, VaultError) else "PRIVACY_RESTORE_FAILED"
            err = PrivacyRefused(code)
            self._audit_refusal(meta, err)
            raise err from None
        self.audit.write(**meta, decision="RESTORE", categories={"restored": restored, "foreign": foreign},
                         grant_ids=[], outcome="RESTORED", code="FOREIGN_TOKENS" if foreign else None)
        return out

    def close_scope(self, scope) -> None:
        try:
            self.vault.close(scope)
        except VaultError as exc:
            raise PrivacyRefused(exc.code) from None


def _summary(actions: dict) -> str:
    if not actions:
        return P.ALLOW
    return max(actions.values(), key=lambda a: P.STRICTNESS[a])


_default = None
_default_lock = threading.Lock()


def default_gateway() -> PrivacyGateway:
    """Process-wide gateway. With URI_PRIVACY_HOME set, audit, grants and persisted references live there."""
    global _default
    with _default_lock:
        if _default is None:
            home = os.environ.get("URI_PRIVACY_HOME")
            if home:
                h = Path(home)
                _default = PrivacyGateway(audit=PrivacyAudit(h / "audit.jsonl"), grants=GrantStore(h / "grants.json"),
                                          vault=MemoryVaultStore())
            else:
                _default = PrivacyGateway()
        return _default


def persistent_vault(home) -> PersistentVaultStore:
    return PersistentVaultStore(home)
