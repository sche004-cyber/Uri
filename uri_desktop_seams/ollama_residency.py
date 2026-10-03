"""Best-effort desktop Ollama residency guard for large Brain models."""

from __future__ import annotations

import functools
import os
import threading
import time
from contextlib import contextmanager
from urllib.parse import urlparse

import requests


_DEFAULT_THRESHOLD = 2 * 1024**3
_CACHE_SECONDS = 5.0
_BUDGET_SECONDS = 2.0
_states_lock = threading.Lock()
_states = {}


class _ServerState:
    def __init__(self):
        self.lock = threading.Lock()
        self.preflight_lock = threading.Lock()
        self.in_flight = {}
        self.loaded = None
        self.checked_at = 0.0
        self.sizes = {}


def _model_key(name):
    return name.removesuffix(":latest") if isinstance(name, str) else ""


def _size(entry):
    if not isinstance(entry, dict):
        return 0
    values = (entry.get("size_vram"), entry.get("size"))
    return max((value for value in values if type(value) is int and value > 0), default=0)


def _threshold():
    try:
        return max(1, int(os.environ.get("URI_DESKTOP_OLLAMA_LARGE_MODEL_BYTES", _DEFAULT_THRESHOLD)))
    except ValueError:
        return _DEFAULT_THRESHOLD


def _enabled(base_url):
    if os.environ.get("URI_DESKTOP_OLLAMA_RESIDENCY_ENABLED", "1").lower() in {"0", "false", "off", "no"}:
        return False
    try:
        parsed = urlparse(base_url)
        return parsed.hostname in {"localhost", "127.0.0.1", "::1"} and parsed.port != 0
    except ValueError:
        return False


def _state(base_url):
    parsed = urlparse(base_url)
    # Loopback spellings can address the same Ollama daemon. Share leases.
    key = (parsed.scheme, parsed.port or 80, parsed.path.rstrip("/"))
    with _states_lock:
        return _states.setdefault(key, _ServerState())


def _entries(response, field):
    if response.status_code != 200:
        return None
    body = response.json()
    entries = body.get(field) if isinstance(body, dict) else None
    return entries if isinstance(entries, list) else None


def _preflight(state, base_url, current):
    deadline = time.monotonic() + _BUDGET_SECONDS
    root = base_url.rstrip("/")
    try:
        with state.lock:
            fresh = state.loaded is not None and time.monotonic() - state.checked_at < _CACHE_SECONDS
            loaded = state.loaded if fresh else None
        if loaded is None:
            response = requests.get(f"{root}/api/ps", timeout=min(0.7, max(0.01, deadline - time.monotonic())))
            entries = _entries(response, "models")
            if entries is None:
                return
            loaded = {_model_key(item.get("name")): (item.get("name"), _size(item))
                      for item in entries if isinstance(item, dict) and isinstance(item.get("name"), str)}
            with state.lock:
                state.loaded = loaded
                state.checked_at = time.monotonic()
                state.sizes.update({key: size for key, (_, size) in loaded.items() if size})

        target_size = loaded.get(current, (None, 0))[1] or state.sizes.get(current, 0)
        if not target_size:
            response = requests.get(f"{root}/api/tags", timeout=min(0.5, max(0.01, deadline - time.monotonic())))
            entries = _entries(response, "models")
            if entries is None:
                return
            target_size = next((_size(item) for item in entries
                                if isinstance(item, dict) and _model_key(item.get("name")) == current), 0)
            if target_size:
                with state.lock:
                    state.sizes[current] = target_size
        threshold = _threshold()
        if target_size < threshold:
            return

        edge = {_model_key("qwen3:0.6b"), _model_key(os.environ.get("URI_HARNESS_EDGE_CHAT_MODEL", "qwen3:0.6b"))}
        for key, (name, size) in tuple(loaded.items()):
            if key in {current, *edge} or size < threshold or time.monotonic() >= deadline:
                continue
            with state.lock:
                if state.in_flight.get(key):
                    continue
                try:
                    response = requests.post(
                        f"{root}/api/generate", json={"model": name, "keep_alive": 0},
                        timeout=max(0.01, deadline - time.monotonic()),
                    )
                    if response.status_code == 200 and state.loaded is not None:
                        state.loaded.pop(key, None)
                except Exception:
                    # Residency is an optimization; inference must still proceed.
                    return
    except Exception:
        return


@contextmanager
def _lease(config):
    if not _enabled(config.base_url):
        yield
        return
    state = _state(config.base_url.rstrip("/"))
    current = _model_key(config.model)
    with state.lock:
        state.in_flight[current] = state.in_flight.get(current, 0) + 1
    successful = False
    try:
        if state.preflight_lock.acquire(blocking=False):
            try:
                _preflight(state, config.base_url, current)
            finally:
                state.preflight_lock.release()
        yield
        successful = True
    finally:
        with state.lock:
            count = state.in_flight[current] - 1
            if count:
                state.in_flight[current] = count
            else:
                del state.in_flight[current]
            if successful and state.loaded is not None and current in state.sizes:
                state.loaded[current] = (config.model, state.sizes[current])


def guard_completion(method):
    """Keep a model leased through the full HTTP completion or stream."""
    if method.__name__ == "complete_stream":
        @functools.wraps(method)
        def stream(self, *args, **kwargs):
            with _lease(self.config):
                yield from method(self, *args, **kwargs)
        return stream

    @functools.wraps(method)
    def complete(self, *args, **kwargs):
        with _lease(self.config):
            return method(self, *args, **kwargs)
    return complete
