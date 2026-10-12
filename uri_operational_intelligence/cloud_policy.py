"""Cloud-provider interface, prepared but NOT activated (WS blueprint AC-12).

What exists:
  * A provider-neutral description of the cloud Brain providers URI may later use.
  * A spending policy with a hard cap of $5.00 per calendar month (UTC), which counts estimated cost before a call.
  * Single-use manual approvals. Each paid call needs its own approval that the user grants explicitly. An approval
    is bound to provider, model and estimated cost, expires, and can be consumed once.

What does not exist, on purpose:
  * No transport. `call()` always refuses with CLOUD_ACTIVATION_DISABLED. The module imports no HTTP library and
    opens no socket.
  * No credential storage or lookup. Nothing here reads an environment variable, a key file or a keyring.
  * No activation switch. Enabling cloud calls needs a separate owner decision and a code change that is reviewed
    on its own.
"""
from __future__ import annotations

import json
import secrets
import threading
import time
from pathlib import Path

MONTHLY_CAP_USD = 5.00
APPROVAL_TTL_S = 15 * 60
ACTIVATION = "disabled"

_PROVIDERS = (
    {"id": "anthropic", "display": "Anthropic Claude"},
    {"id": "openai", "display": "OpenAI"},
    {"id": "google", "display": "Google Gemini"},
)


class CloudPolicyError(RuntimeError):
    pass


def providers() -> list:
    return [dict(p, activation=ACTIVATION, credentials="none") for p in _PROVIDERS]


def _month(ts=None) -> str:
    return time.strftime("%Y-%m", time.gmtime(ts if ts is not None else time.time()))


class CloudSpendPolicy:
    """Budget + single-use approvals. Persists only month totals and approval records (no prompts, no keys)."""

    def __init__(self, path: Path | None = None, *, cap_usd: float = MONTHLY_CAP_USD, clock=time.time):
        if not (0 < cap_usd <= MONTHLY_CAP_USD):
            raise CloudPolicyError("CAP_ABOVE_POLICY")      # the owner policy is the ceiling, never raised in code
        self.path, self.cap, self.clock = path, round(cap_usd, 2), clock
        self._lock = threading.Lock()
        self._state = {"months": {}, "approvals": {}}
        if path is not None and Path(path).is_file():
            self._state = json.loads(Path(path).read_text(encoding="utf-8"))

    def _save(self):
        if self.path is not None:
            p = Path(self.path)
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(self._state, indent=1, sort_keys=True), encoding="utf-8")
            tmp.replace(p)

    def spent(self, month=None) -> float:
        return round(self._state["months"].get(month or _month(self.clock()), 0.0), 4)

    def remaining(self) -> float:
        return round(self.cap - self.spent(), 4)

    def request(self, provider: str, model: str, est_cost_usd: float) -> dict:
        """A pending approval record for ONE call. The user must approve it explicitly; nothing is approved here."""
        if provider not in {p["id"] for p in _PROVIDERS}:
            raise CloudPolicyError("PROVIDER_UNKNOWN")
        if not isinstance(est_cost_usd, (int, float)) or est_cost_usd <= 0:
            raise CloudPolicyError("COST_ESTIMATE_REQUIRED")
        with self._lock:
            if self.spent() + est_cost_usd > self.cap:
                raise CloudPolicyError("MONTHLY_CAP_EXCEEDED")
            aid = secrets.token_hex(16)
            rec = {"id": aid, "provider": provider, "model": model, "est_cost_usd": round(float(est_cost_usd), 4),
                   "state": "PENDING", "created": self.clock(), "expires": self.clock() + APPROVAL_TTL_S}
            self._state["approvals"][aid] = rec
            self._save()
            return dict(rec)

    def approve(self, approval_id: str, *, by_user: bool) -> dict:
        """Manual approval. `by_user` must be True and comes from a UI button handler, never from text or a model."""
        if by_user is not True:
            raise CloudPolicyError("MANUAL_APPROVAL_REQUIRED")
        with self._lock:
            rec = self._state["approvals"].get(approval_id)
            if rec is None or rec["state"] != "PENDING":
                raise CloudPolicyError("APPROVAL_NOT_PENDING")
            if self.clock() > rec["expires"]:
                rec["state"] = "EXPIRED"
                self._save()
                raise CloudPolicyError("APPROVAL_EXPIRED")
            rec["state"] = "APPROVED"
            self._save()
            return dict(rec)

    def consume(self, approval_id: str, provider: str, model: str, est_cost_usd: float) -> dict:
        """Single use: an APPROVED record that matches exactly is consumed once and charged to the month."""
        with self._lock:
            rec = self._state["approvals"].get(approval_id)
            if rec is None or rec["state"] != "APPROVED":
                raise CloudPolicyError("APPROVAL_NOT_USABLE")
            if (rec["provider"], rec["model"], rec["est_cost_usd"]) != (provider, model, round(float(est_cost_usd), 4)):
                raise CloudPolicyError("APPROVAL_BINDING_MISMATCH")
            if self.clock() > rec["expires"]:
                rec["state"] = "EXPIRED"
                self._save()
                raise CloudPolicyError("APPROVAL_EXPIRED")
            if self.spent() + rec["est_cost_usd"] > self.cap:
                raise CloudPolicyError("MONTHLY_CAP_EXCEEDED")
            rec["state"] = "CONSUMED"
            m = _month(self.clock())
            self._state["months"][m] = round(self._state["months"].get(m, 0.0) + rec["est_cost_usd"], 4)
            self._save()
            return dict(rec)

    def summary(self) -> dict:
        return {"cap_usd": self.cap, "spent_usd": self.spent(), "remaining_usd": self.remaining(),
                "month": _month(self.clock()), "activation": ACTIVATION, "providers": providers()}


def call(*_args, **_kwargs):
    """Paid calls are not wired. This stays a refusal until the owner separately authorizes activation."""
    raise CloudPolicyError("CLOUD_ACTIVATION_DISABLED")
