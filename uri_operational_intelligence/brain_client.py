"""Inference client for Runtime v1: streamed and structured chat calls with cancellation, deadlines and honest
status reporting.

Builds on the frozen persistent-client finding (freeze record section 8: one keep-alive pool per server; a new client
per request costs ~0.22 s). Adds what the research client did not have:

  * streaming with separate reasoning / answer deltas;
  * cooperative cancellation that closes the HTTP stream (llama-server aborts the slot when the client disconnects;
    the release of the single slot is verified by the live tests, not assumed);
  * three deadlines enforced by a watcher thread: time-to-first-token, idle gap between chunks, and total;
  * a single status vocabulary, never a fabricated success:
      COMPLETE, INCOMPLETE_LENGTH, CANCELLED, TIMEOUT_FIRST_TOKEN, STALLED, DEADLINE_EXCEEDED,
      INTERRUPTED (stream broke after output began), UNREACHABLE, HTTP_ERROR, PROTOCOL_ERROR;
  * one automatic retry ONLY for a transport failure before any byte of output (inference has no side effects;
    nothing is retried after output began, and nothing is ever sent to another model).

Request parameters for a tier come from `reasoning_policy.tier_params` (server-side), never from model output.
"""
from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Callable, Optional

import httpx

COMPLETE = "COMPLETE"
INCOMPLETE_LENGTH = "INCOMPLETE_LENGTH"
CANCELLED = "CANCELLED"
TIMEOUT_FIRST_TOKEN = "TIMEOUT_FIRST_TOKEN"
STALLED = "STALLED"
DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
INTERRUPTED = "INTERRUPTED"
UNREACHABLE = "UNREACHABLE"
HTTP_ERROR = "HTTP_ERROR"
PROTOCOL_ERROR = "PROTOCOL_ERROR"

SUCCESS = {COMPLETE}


class CancelToken:
    def __init__(self):
        self._event = threading.Event()
        self.reason = None

    def cancel(self, reason="user"):
        self.reason = self.reason or reason
        self._event.set()

    @property
    def cancelled(self):
        return self._event.is_set()

    def wait(self, timeout):
        return self._event.wait(timeout)


@dataclass
class Deadlines:
    first_token_s: float = 60.0     # covers a full 30k-token prefill (14.5 s measured) with margin
    idle_s: float = 30.0            # max gap between chunks once output began
    total_s: float = 300.0


@dataclass
class CallResult:
    status: str
    text: str = ""
    reasoning: str = ""
    finish_reason: Optional[str] = None
    error: Optional[str] = None
    http_status: Optional[int] = None
    ttft_s: Optional[float] = None          # first chunk of ANY kind (reasoning or answer)
    first_answer_s: Optional[float] = None  # first visible answer character
    total_s: Optional[float] = None
    timings: dict = field(default_factory=dict)   # llama-server's own timings, verbatim keys
    usage: dict = field(default_factory=dict)
    retried: bool = False
    request_id: Optional[str] = None

    @property
    def ok(self):
        return self.status in SUCCESS

    def to_dict(self):
        return asdict(self)


class BrainClient:
    """One persistent keep-alive pool per Runtime v1 server."""

    def __init__(self, base_url, *, connect_timeout=3.0):
        self.base_url = base_url.rstrip("/")
        self.connect_timeout = connect_timeout
        self._client = None
        self._lock = threading.Lock()

    def _get(self):
        with self._lock:
            if self._client is None:
                self._client = httpx.Client(
                    base_url=self.base_url, http2=False,
                    timeout=httpx.Timeout(connect=self.connect_timeout, read=None, write=30.0, pool=10.0),
                    limits=httpx.Limits(max_keepalive_connections=4, max_connections=8, keepalive_expiry=300.0))
            return self._client

    def reset(self):
        with self._lock:
            c, self._client = self._client, None
        if c is not None:
            try:
                c.close()
            except Exception:
                pass

    def close(self):
        self.reset()

    # ---- streaming ------------------------------------------------------------------------------
    def stream_chat(self, body: dict, *, cancel: CancelToken | None = None, deadlines: Deadlines | None = None,
                    on_delta: Callable[[str, str], None] | None = None, request_id=None) -> CallResult:
        """`on_delta(kind, text)` with kind in {"reasoning", "answer"}. Returns a CallResult; never raises for
        runtime/transport conditions (only for programming errors)."""
        cancel = cancel or CancelToken()
        deadlines = deadlines or Deadlines()
        body = dict(body, stream=True, stream_options={"include_usage": True})
        result = self._stream_once(body, cancel, deadlines, on_delta, request_id)
        if result.status == UNREACHABLE and not cancel.cancelled:
            # Transport failure before any output: the persistent pool may hold a socket from a restarted server.
            self.reset()
            retry = self._stream_once(body, cancel, deadlines, on_delta, request_id)
            retry.retried = True
            return retry
        return result

    def _stream_once(self, body, cancel, deadlines, on_delta, request_id) -> CallResult:
        t0 = time.monotonic()
        res = CallResult(status=PROTOCOL_ERROR, request_id=request_id)
        state = {"first": None, "last": t0, "why": None, "response": None, "done": False}
        guard = threading.Lock()

        def stop(why):
            with guard:
                if state["why"] is None:
                    state["why"] = why
                resp = state["response"]
            if resp is not None:
                try:
                    resp.close()   # unblocks the reader; llama-server sees the disconnect and frees the slot
                except Exception:
                    pass

        def watcher():
            while not state["done"]:
                if cancel.wait(0.05):
                    stop(CANCELLED)
                    return
                now = time.monotonic()
                if now - t0 > deadlines.total_s:
                    stop(DEADLINE_EXCEEDED)
                    return
                if state["first"] is None and now - t0 > deadlines.first_token_s:
                    stop(TIMEOUT_FIRST_TOKEN)
                    return
                if state["first"] is not None and now - state["last"] > deadlines.idle_s:
                    stop(STALLED)
                    return

        w = threading.Thread(target=watcher, daemon=True)
        w.start()
        text, reasoning = [], []
        try:
            req = self._get().build_request("POST", "/v1/chat/completions", json=body)
            resp = self._get().send(req, stream=True)
            with guard:
                state["response"] = resp
                why = state["why"]
            if why:
                resp.close()
                raise httpx.ReadError("closed by watcher")
            res.http_status = resp.status_code
            if resp.status_code != 200:
                try:
                    detail = resp.read().decode("utf-8", "replace")[:300]
                except Exception:
                    detail = None
                res.status, res.error = HTTP_ERROR, detail
                return res
            for line in resp.iter_lines():
                if not line or not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload == "[DONE]":
                    break
                try:
                    chunk = json.loads(payload)
                except ValueError:
                    res.status, res.error = PROTOCOL_ERROR, "BAD_SSE_JSON"
                    return res
                now = time.monotonic()
                state["last"] = now
                if chunk.get("timings"):
                    res.timings = chunk["timings"]
                if chunk.get("usage"):
                    res.usage = chunk["usage"]
                for choice in chunk.get("choices") or []:
                    delta = choice.get("delta") or {}
                    r = delta.get("reasoning_content")
                    c = delta.get("content")
                    if (r or c) and state["first"] is None:
                        state["first"] = now
                        res.ttft_s = round(now - t0, 4)
                    if r:
                        reasoning.append(r)
                        if on_delta:
                            on_delta("reasoning", r)
                    if c:
                        if res.first_answer_s is None:
                            res.first_answer_s = round(now - t0, 4)
                        text.append(c)
                        if on_delta:
                            on_delta("answer", c)
                    if choice.get("finish_reason"):
                        res.finish_reason = choice["finish_reason"]
            if state["why"]:
                res.status = state["why"]
            elif res.finish_reason == "length":
                res.status = INCOMPLETE_LENGTH
            elif res.finish_reason in ("stop", "eos"):
                res.status = COMPLETE
            else:
                res.status, res.error = INTERRUPTED, "STREAM_ENDED_WITHOUT_FINISH"
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            res.status, res.error = (state["why"] or UNREACHABLE), type(exc).__name__
        except (httpx.TransportError, httpx.StreamError, httpx.RemoteProtocolError) as exc:
            if state["why"]:
                res.status = state["why"]
            elif state["first"] is None and not text and not reasoning:
                res.status = UNREACHABLE
            else:
                res.status = INTERRUPTED
            res.error = type(exc).__name__
        finally:
            state["done"] = True
            with guard:
                resp = state["response"]
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass
            res.text, res.reasoning = "".join(text), "".join(reasoning)
            res.total_s = round(time.monotonic() - t0, 4)
        return res

    # ---- structured (non-streaming) ---------------------------------------------------------------
    def complete_json(self, body: dict, *, timeout_s=120.0) -> CallResult:
        """Non-streaming call for structured seams (freeze record section 8: streaming not used for JSON seams)."""
        t0 = time.monotonic()
        res = CallResult(status=PROTOCOL_ERROR)
        body = dict(body, stream=False)
        for attempt in (0, 1):
            try:
                r = self._get().post("/v1/chat/completions", json=body, timeout=httpx.Timeout(timeout_s, connect=self.connect_timeout))
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.RemoteProtocolError) as exc:
                self.reset()
                res.status, res.error = UNREACHABLE, type(exc).__name__
                if attempt == 0:
                    res.retried = True
                    continue
                break
            except httpx.TimeoutException as exc:
                res.status, res.error = DEADLINE_EXCEEDED, type(exc).__name__
                break
            except httpx.TransportError as exc:
                res.status, res.error = INTERRUPTED, type(exc).__name__
                break
            res.http_status = r.status_code
            if r.status_code != 200:
                res.status, res.error = HTTP_ERROR, r.text[:300]
                break
            try:
                data = r.json()
                choice = data["choices"][0]
                res.text = choice["message"].get("content") or ""
                res.reasoning = choice["message"].get("reasoning_content") or ""
                res.finish_reason = choice.get("finish_reason")
                res.timings = data.get("timings") or {}
                res.usage = data.get("usage") or {}
            except (ValueError, KeyError, IndexError, TypeError):
                res.status, res.error = PROTOCOL_ERROR, "BAD_RESPONSE_SHAPE"
                break
            res.status = INCOMPLETE_LENGTH if res.finish_reason == "length" else COMPLETE
            break
        res.total_s = round(time.monotonic() - t0, 4)
        return res
