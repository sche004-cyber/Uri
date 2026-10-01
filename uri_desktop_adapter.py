"""URI Desktop Startup Validator and Capability Inventory.

Provides startup-time validation for the desktop application:
- Verifies Ollama is reachable and the configured models are available.
- Checks for port conflicts before binding.
- Registers a /desktop/status endpoint reporting honest capability inventory.

ARCHITECTURAL INVARIANT: This module does NOT intercept, modify, or bypass
the canonical POST /ask handler in uri_core.app.server. Desktop requests
flow through the canonical /ask lifecycle exactly as every other client's
requests do — including authenticated-user resolution, content-length
enforcement, context construction, approval resumption, lifecycle intent
interpretation, canonical execution, and response finalization.

The desktop's model configuration is managed through the existing
uri_workspace/model_roles.json mechanism (see uri_core.config.model_roles),
which the canonical pipeline already reads.
"""

from __future__ import annotations

import json
import logging
import os
import socket
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uri.desktop_adapter")

REPO_ROOT = Path(__file__).resolve().parent
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")


def _check_ollama_health(timeout: float = 3.0) -> Dict[str, Any]:
    """Probe the local Ollama instance for availability."""
    try:
        req = urllib.request.Request(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/tags",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in data.get("models", [])]
            return {"healthy": True, "models": models}
    except Exception as exc:
        return {"healthy": False, "models": [], "error": str(exc)}


def _check_port_available(host: str, port: int) -> Dict[str, Any]:
    """Check whether the target port is available for binding."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1.0)
    try:
        result = sock.connect_ex((host, port))
        if result == 0:
            # Port is occupied — something is already listening
            return {"available": False, "detail": f"{host}:{port} is already in use"}
        return {"available": True}
    except Exception as exc:
        return {"available": True, "detail": str(exc)}
    finally:
        sock.close()


def validate_desktop_readiness(
    host: str = "127.0.0.1",
    port: int = 8000,
) -> Dict[str, Any]:
    """Run pre-startup validation checks. Returns a report dict.

    This is called by run_desktop_server.py BEFORE uvicorn.run() to
    verify that the runtime environment is viable. It does NOT start
    or intercept any server.
    """
    from uri_core.config.model_roles import load_model_roles, MODEL_ROLES_PATH

    report: Dict[str, Any] = {
        "ollama": None,
        "model_roles": None,
        "port": None,
        "v1_capabilities": None,
        "ready": False,
    }

    # 1. Ollama health
    ollama = _check_ollama_health()
    report["ollama"] = ollama

    # 2. Model roles configuration — verify the file is consumed
    roles = load_model_roles()
    roles_file_exists = Path(MODEL_ROLES_PATH).exists()
    configured_models = set()
    for role, config in roles.items():
        model = config.get("model")
        if model:
            configured_models.add(model)

    missing_models = []
    if ollama["healthy"]:
        available = set(ollama["models"])
        for model in configured_models:
            # Ollama model names may include tags — check prefix match
            if model not in available and not any(
                a.startswith(model.split(":")[0]) for a in available
            ):
                missing_models.append(model)

    report["model_roles"] = {
        "config_file": MODEL_ROLES_PATH,
        "config_file_exists": roles_file_exists,
        "roles_loaded": list(roles.keys()),
        "configured_models": sorted(configured_models),
        "missing_from_ollama": missing_models,
    }

    # 3. Port availability (only relevant before binding)
    report["port"] = _check_port_available(host, port)

    # 4. Honest v1 capability inventory
    v1_caps = _inventory_v1_capabilities()
    report["v1_capabilities"] = v1_caps

    # Overall readiness
    report["ready"] = (
        ollama["healthy"]
        and len(missing_models) == 0
        and report["port"].get("available", False)
    )

    return report


def _inventory_v1_capabilities() -> Dict[str, Any]:
    """Inspect which v1 modules are importable and what they expose.

    This is an honest inventory — it reports what IS available, not
    what the adapter CLAIMS to integrate. Each capability is marked
    as 'importable' (the module loads without error) and 'status'
    (whether it has been qualified/verified for desktop use).
    """
    inventory: Dict[str, Any] = {}

    # Edge Registry — M37 qualified deterministic capabilities
    try:
        import uri_v1.edge.registry as edge_reg
        registry = edge_reg.default_registry()
        caps = []
        for name, cap in registry.capabilities.items():
            caps.append({
                "name": name,
                "mechanism": cap.mechanism.value if hasattr(cap.mechanism, "value") else str(cap.mechanism),
                "qualification": cap.qualification.value if hasattr(cap.qualification, "value") else str(cap.qualification),
            })
        inventory["edge_registry"] = {
            "importable": True,
            "capabilities": caps,
            "status": "MODULE_QUALIFIED_NOT_WIRED - M37 qualification is module-level; desktop /ask does not invoke uri_v1 on this line",
        }
    except Exception as exc:
        inventory["edge_registry"] = {"importable": False, "error": str(exc)}

    # Harness Adapters — M38 qualified
    try:
        from uri_v1.execution.harness.adapters import CodexCliAdapter
        adapter = CodexCliAdapter(model="gpt-5.6-terra")
        probe = adapter.probe()
        inventory["harness_codex"] = {
            "importable": True,
            "installed": probe.get("installed", False),
            "version": probe.get("version"),
            "status": "INSTALLED_NOT_WIRED - desktop /ask does not invoke the harness on this line"
            if probe.get("installed")
            else "NOT INSTALLED — Codex CLI binary not found",
        }
    except Exception as exc:
        inventory["harness_codex"] = {"importable": False, "error": str(exc)}

    # RAR Deterministic — reference grounding
    try:
        import uri_v1.turn.rar_deterministic as rar_det
        inventory["rar_deterministic"] = {
            "importable": True,
            "status": "IMPORTABLE_NOT_WIRED - not invoked by desktop /ask on this line",
        }
    except Exception as exc:
        inventory["rar_deterministic"] = {"importable": False, "error": str(exc)}

    # Memory Logging
    try:
        import uri_v1.memory.log as mem_log
        inventory["memory_log"] = {
            "importable": True,
            "status": "IMPORTABLE_NOT_WIRED - not invoked by desktop /ask on this line",
        }
    except Exception as exc:
        inventory["memory_log"] = {"importable": False, "error": str(exc)}

    # Harness Runner
    try:
        from uri_v1.execution.harness.runner import HarnessRunner
        inventory["harness_runner"] = {
            "importable": True,
            "status": "IMPORTABLE_NOT_WIRED - not invoked by desktop /ask on this line",
        }
    except Exception as exc:
        inventory["harness_runner"] = {"importable": False, "error": str(exc)}

    return inventory


def mount_desktop_status_endpoint(app: Any) -> None:
    """Register a GET /desktop/status endpoint on the FastAPI app.

    This endpoint reports the desktop runtime's honest capability
    inventory without intercepting or modifying any existing endpoints.
    """
    from fastapi.responses import JSONResponse

    @app.get("/desktop/status")
    def desktop_status():
        """Returns the desktop runtime capability inventory and configuration state."""
        from uri_core.config.model_roles import load_model_roles

        ollama = _check_ollama_health()
        roles = load_model_roles()
        v1_caps = _inventory_v1_capabilities()

        return JSONResponse(content={
            "runtime": "desktop",
            # Lets the launcher tell this checkout's backend apart from a
            # URI backend started from another worktree on the same port.
            "repo_root": str(REPO_ROOT),
            "ollama": ollama,
            "model_roles": {
                role: {
                    "provider": config.get("provider", "ollama"),
                    "model": config.get("model", "(default)"),
                }
                for role, config in roles.items()
                if role in (
                    "semantic_interpretation", "reasoning", "drafting",
                    "document_composition", "diagnostics", "background",
                )
            },
            "v1_capabilities": v1_caps,
            "architecture_note": (
                "Desktop requests flow through URI Core's canonical POST /ask handler. "
                "Model routing is configured via uri_workspace/model_roles.json and "
                "consumed by uri_core.config.model_roles.load_model_roles(). "
                "No middleware interception or /ask bypass is in effect."
            ),
        })

    logger.info("Registered GET /desktop/status endpoint (no /ask interception)")
