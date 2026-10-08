"""URI local intelligence integration layer (outside the frozen Phase 1 Core).

What this module does:
  * runs ONE resident local model under llama.cpp (llama-server, Vulkan) with the measured
    configuration in local_brain.json;
  * exposes the two Brain seams Phase 1 Core already accepts through create_app(composition=...):
      proposer(prepared, request, selection)            -> decision-contract proposal
      interpreter(text, capability, slots, selection)   -> verbatim slot suggestions
    Both always run on the FAST tier (thinking off, grammar-constrained). Measured: thinking
    never improved the decision contract and unbounded thinking collapsed it (0.33-0.38);
  * exposes depth-tiered language calls for work Core does not compose yet (answers, drafting,
    analysis): fast / normal (bounded thinking) and an escalation verdict for external harnesses.

What it deliberately does NOT do:
  * approve, execute, confirm, bind references or choose arguments: Core owns those;
  * switch to another model or provider silently: failures raise ReasoningUnavailable and Core
    reports them (existing Phase 1 "never substitute" behaviour);
  * modify anything in uri_core.

Reversible: nothing is registered globally. A caller opts in by passing composition() to
create_app; removing that argument restores the no-Brain deterministic behaviour.
"""
from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "local_brain.json"


# --------------------------------------------------------------------------- HTTP client -------
class BrainClient:
    """One persistent HTTP/1.1 keep-alive connection pool per resident server.

    Measured (stream_probe2.py, 2026-10-06): constructing a new httpx client per request costs ~0.22 s on this
    machine (TLS context + pool setup), i.e. ~10% of a decision turn, while the server answers the same trivial
    request in 74 ms on a reused socket. A single client is kept per base URL; a transport-level failure (server
    restarted, connection reset) closes the pool and the next call rebuilds it once, so a llama-server restart
    costs one retried request, never a stuck provider.
    """

    def __init__(self, base_url, timeout=120.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = None

    def _get(self):
        if self._client is None:
            self._client = httpx.Client(base_url=self.base_url, timeout=self.timeout, http2=False,
                                        limits=httpx.Limits(max_keepalive_connections=4, max_connections=8, keepalive_expiry=300.0))
        return self._client

    def reset(self):
        c, self._client = self._client, None
        if c is not None:
            try:
                c.close()
            except Exception:
                pass

    def post(self, path, json_body, timeout=None, retry_once=True):
        try:
            return self._get().post(path, json=json_body, timeout=timeout or self.timeout)
        except (httpx.TransportError, httpx.RemoteProtocolError):
            self.reset()
            if not retry_once:
                raise
            return self._get().post(path, json=json_body, timeout=timeout or self.timeout)

    def get(self, path, timeout=2.0):
        try:
            return self._get().get(path, timeout=timeout)
        except (httpx.TransportError, httpx.RemoteProtocolError):
            self.reset()
            raise


_CLIENTS = {}


def client_for(url):
    url = url.rstrip("/")
    if url not in _CLIENTS:
        _CLIENTS[url] = BrainClient(url)
    return _CLIENTS[url]


def load_config(path=CONFIG_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------- runtime ----------
class ResidentRuntime:
    """Start/stop/health of the single resident llama-server. Verifies the model hash first."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.proc = None
        self.url = f"http://127.0.0.1:{cfg['runtime']['port']}"

    def verify_model(self):
        import hashlib
        m = self.cfg["model"]
        h = hashlib.sha256()
        with open(m["path"], "rb") as f:
            for chunk in iter(lambda: f.read(1 << 24), b""):
                h.update(chunk)
        if h.hexdigest() != m["sha256"]:
            raise RuntimeError("MODEL_HASH_MISMATCH")

    def argv(self):
        r, m = self.cfg["runtime"], self.cfg["model"]
        a = [r["binary"], "-m", m["path"], "-c", str(r["ctx"]), "-ngl", str(r["ngl"]), "-fa", "on",
             "-ctk", r["cache_type"], "-ctv", r["cache_type"], "-np", "1", "--host", "127.0.0.1",
             "--port", str(r["port"]), "--jinja", "--reasoning-format", "deepseek", "--no-webui",
             "--load-mode", r["load_mode"], "--cache-ram", str(r["cache_ram_mib"])]
        if m.get("mmproj") and r.get("vision_enabled"):
            a += ["--mmproj", m["mmproj"]]
        else:
            a += ["--no-mmproj"]
        return a + list(r.get("extra_args", []))

    def healthy(self):
        try:
            return client_for(self.url).get("/health", timeout=2).status_code == 200
        except Exception:
            return False

    def start(self, verify=True, timeout=300):
        if self.healthy():
            return self
        if verify:
            self.verify_model()
        self.proc = subprocess.Popen(self.argv(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError(f"LOCAL_BRAIN_EXITED:{self.proc.returncode}")
            if self.healthy():
                return self
            time.sleep(0.5)
        self.stop()
        raise TimeoutError("LOCAL_BRAIN_START_TIMEOUT")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(30)
            except subprocess.TimeoutExpired:
                self.proc.kill()


# --------------------------------------------------------------------------- calls ------------
def _chat(url, messages, *, max_tokens, tier, cfg, json_schema=None, timeout=120):
    t = cfg["tiers"][tier]
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": t["temperature"],
            "stream": False, "chat_template_kwargs": {"enable_thinking": t["thinking"]}}
    if t.get("thinking_budget") is not None:
        body["thinking_budget_tokens"] = t["thinking_budget"]
    if json_schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": json_schema, "strict": True}}
    r = client_for(url).post("/v1/chat/completions", body, timeout=timeout)
    r.raise_for_status()
    msg = r.json()["choices"][0]
    return msg["message"].get("content") or "", msg.get("finish_reason")


@dataclass
class LocalBrain:
    """Brain seams + tiered language calls bound to one resident runtime."""
    cfg: dict
    url: str

    # ---- Core seams (always FAST tier, grammar constrained) -------------------------------------
    def proposer(self, prepared, request, selection):
        from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT
        from uri_core.core.paired_reasoning import ReasoningUnavailable
        from model_lab.lab.decision import decision_schema
        req = prepared["request"]
        ids = [s["capability_id"] for s in req.get("capability_summaries") or []]
        try:
            text, finish = _chat(self.url, [{"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
                                            {"role": "user", "content": json.dumps(req, ensure_ascii=False)}],
                                 max_tokens=600, tier="fast", cfg=self.cfg, json_schema=decision_schema(ids))
            obj = json.loads(text)
        except Exception:
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID") from None
        if not isinstance(obj, dict) or finish == "length":
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID")
        return route_intent_capabilities(obj, prepared)

    def interpreter(self, text, capability, slots, selection):
        from uri_core.core.paired_reasoning import ReasoningUnavailable
        from model_lab.lab.paired import INTERPRETER_SYSTEM
        schema = {"type": "object", "properties": {s: {"anyOf": [{"type": "string"}, {"type": "null"}]} for s in slots},
                  "required": list(slots), "additionalProperties": False}
        try:
            out, _ = _chat(self.url, [{"role": "system", "content": INTERPRETER_SYSTEM},
                                      {"role": "user", "content": json.dumps({"message": text, "capability": capability,
                                                                              "slots": list(slots)})}],
                           max_tokens=200, tier="fast", cfg=self.cfg, json_schema=schema)
            obj = json.loads(out)
        except Exception:
            raise ReasoningUnavailable("BRAIN_OUTPUT_INVALID") from None
        # Core re-checks every value against the user's words (groundedness); this is a suggestion only.
        from model_lab.lab.paired import snap_to_user_span
        return {k: snap_to_user_span(v, text) for k, v in obj.items() if isinstance(v, str) and v.strip()}

    # ---- language work outside the Phase 1 composition --------------------------------------------
    def answer(self, messages, *, tier="fast", max_tokens=800):
        """fast: conversation, formatting, short drafting. normal: bounded-thinking analysis."""
        if tier not in ("fast", "normal"):
            raise ValueError("unbounded thinking is not offered locally; escalate instead")
        text, finish = _chat(self.url, messages, max_tokens=max_tokens if tier == "fast" else max(max_tokens, 4000),
                             tier=tier, cfg=self.cfg)
        return {"text": text, "finish_reason": finish, "complete": finish != "length"}

    def route(self, user_text):
        """Advisory route (answer_locally | use_capability | clarify | escalate_harness | refuse).
        Core still decides capability authority; this only says whether LOCAL language work suffices."""
        from model_lab.lab.prompts import ROUTER_SYSTEM
        schema = {"type": "object", "properties": {
            "route": {"type": "string", "enum": ["answer_locally", "use_capability", "clarify", "escalate_harness", "refuse"]},
            "capability": {"anyOf": [{"type": "string"}, {"type": "null"}]}, "reason": {"type": "string"}},
            "required": ["route", "capability", "reason"], "additionalProperties": False}
        text, _ = _chat(self.url, [{"role": "system", "content": ROUTER_SYSTEM}, {"role": "user", "content": user_text}],
                        max_tokens=300, tier="fast", cfg=self.cfg, json_schema=schema)
        return json.loads(text)


def route_intent_capabilities(obj, prepared):
    """Core owns inputs and clarification for capabilities Intent Discovery interviews for. A model
    proposal that names such a capability without an action (single_action or clarification) is
    routed to Core's own budgeted clarification by naming the capability's action with NO inputs.
    Without this, Core fails closed with REFUSED_UNCONFIRMED_ACTION (documented limitation B-1)."""
    from uri_core.core.intent_discovery import SCHEMAS
    cap = obj.get("capability")
    if obj.get("mode") in ("clarification", "single_action") and cap in SCHEMAS and not obj.get("actions"):
        detail = prepared["directory"].describe(cap)
        if detail and detail.get("actions"):
            obj = dict(obj, mode="single_action", clarification=None,
                       actions=[{"name": sorted(detail["actions"])[0], "inputs": {}}])
    return obj


def selection(cfg):
    return {"kind": "server_local_model", "provider": "llamacpp", "model": cfg["model"]["id"]}


def composition(cfg, url):
    """Exactly what create_app(runtime, composition=...) accepts today; no Core change required."""
    from uri_core.core.paired_reasoning import ReasoningSelectionPolicy
    brain = LocalBrain(cfg, url)
    s = selection(cfg)
    return {"policy": ReasoningSelectionPolicy({(s["kind"], s["provider"], s["model"])}),
            "proposer": brain.proposer, "interpreter": brain.interpreter}

