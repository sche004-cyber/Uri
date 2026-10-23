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
import unicodedata
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
    def __init__(self, *, audit=None, grants=None, vault=None):
        self.audit = audit or PrivacyAudit()
        self.grants = grants or GrantStore()
        self.vault = vault or MemoryVaultStore()

    # -- egress -------------------------------------------------------------------------------------------------------
    def prepare(self, text, *, requester, destination, purpose, task_id=None, scope=None, protected_terms=(),
                reversible=True, ttl_s=DEFAULT_SCOPE_TTL_S) -> Egress:
        meta = {"requester": str(requester), "task_id": task_id, "purpose": str(purpose),
                "destination": str(getattr(destination, "value", destination)), "policy": P.POLICY_ID}
        try:
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

    def _audit_refusal(self, meta, exc):
        try:
            self.audit.write(**meta, decision=P.REFUSE, categories=getattr(exc, "categories", None), grant_ids=[],
                             outcome="REFUSED", code=exc.code)
        except Exception:                                           # noqa: BLE001 - refusal stands either way
            log.warning("privacy audit write failed for a refusal")

    def _decide(self, text, meta, scope, protected_terms, reversible, ttl_s) -> Egress:
        if not isinstance(text, str):
            raise PrivacyRefused("PRIVACY_INPUT_NOT_TEXT")
        if not meta["requester"] or not meta["purpose"]:
            raise PrivacyRefused("PRIVACY_REQUEST_INCOMPLETE")
        try:
            dest = P.Destination(meta["destination"])
        except ValueError:
            raise PrivacyRefused("PRIVACY_DESTINATION_UNKNOWN") from None
        # Compatibility characters and format controls can hide separators from the
        # ASCII credential/card detectors. Refuse ambiguous external text rather
        # than trying to rewrite spans measured against a different string.
        if dest not in P.LOCAL and not text.isascii():
            folded = "".join(ch for ch in unicodedata.normalize("NFKC", text)
                             if unicodedata.category(ch) != "Cf")
            if folded != text:
                folded_counts = C.classify(folded, protected_terms).categories()
                raw_counts = C.classify(text, protected_terms).categories()
                if any(folded_counts[c] > raw_counts[c] for c in C.CATEGORIES):
                    raise PrivacyRefused("PRIVACY_REFUSED")
        cls = C.classify(text, protected_terms)
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
        if grant_ids and not self.grants.consume(grant_ids):
            raise PrivacyRefused("PRIVACY_GRANT_RACE")              # used up or revoked between match and use

        out, scope_id = self._rewrite(text, cls, actions, dest, scope, ttl_s, meta["requester"])
        if dest == P.Destination.LOG and cls.credential_kinds:
            from uri_assist.redact import redact_text
            out = redact_text(out, Counter())
        if dest == P.Destination.WEB_SEARCH:
            out = " ".join(out.split())
        self.audit.write(**meta, decision=_summary(actions), categories=cats, grant_ids=grant_ids,
                         outcome="SANITIZED" if any(a != P.ALLOW for a in actions.values()) else "ALLOWED", code=None)
        return Egress(out, dest.value, cats, actions, scope_id, grant_ids)

    def _rewrite(self, text, cls, actions, dest, scope, ttl_s, requester):
        rewrite = [f for f in cls.findings if actions.get(f.category) in (P.PSEUDONYMIZE, P.REDACT)]
        if not rewrite:
            return text, None
        sc = None
        if any(actions[f.category] == P.PSEUDONYMIZE for f in rewrite):
            sc = self.vault.open(scope or ("s-" + uuid.uuid4().hex), ttl_s, requester=requester)
        parts, pos = [], 0
        for f in rewrite:
            parts.append(text[pos:f.start])
            if actions[f.category] == P.PSEUDONYMIZE:
                parts.append(sc.token_for(f.category, text[f.start:f.end]))
            else:
                parts.append("" if dest == P.Destination.WEB_SEARCH else REDACTED)
            pos = f.end
        parts.append(text[pos:])
        if sc is not None:
            self.vault.save(sc)
        return "".join(parts), (sc.scope_id if sc is not None else None)

    # -- local reconstruction -------------------------------------------------------------------------------------------
    def restore(self, text, scope, *, requester, destination=P.Destination.LOCAL_TOOL, task_id=None) -> str:
        """Resolve this scope's references, only for a local destination. Foreign tokens stay as they are."""
        meta = {"requester": str(requester), "task_id": task_id, "purpose": "restore",
                "destination": str(getattr(destination, "value", destination)), "policy": P.POLICY_ID}
        try:
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
        except (ValueError, VaultError) as exc:
            err = PrivacyRefused(getattr(exc, "code", "PRIVACY_RESTORE_FAILED"))
            self._audit_refusal(meta, err)
            raise err from None
        self.audit.write(**meta, decision="RESTORE", categories={"restored": restored, "foreign": foreign},
                         grant_ids=[], outcome="RESTORED", code="FOREIGN_TOKENS" if foreign else None)
        return out

    def close_scope(self, scope) -> None:
        self.vault.close(scope)


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
