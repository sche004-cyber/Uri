"""M35 URIv1 -- A2.8D D2: Needle 3 detector, outer subprocess wrapper.

Runs in the main environment; spawns the dedicated .venv-needle interpreter
(uri_v1/turn/needle_decoder.py's own default_venv_python() convention,
reused here for path discovery only) to run
m35_a2_8d_needle_inner_runner.py, feeding it every case's raw_user_text and
collecting one structured result per case.

Frozen boundary: this wrapper performs zero interpretation of Needle's
output beyond mechanical field extraction -- it never adds a candidate_id,
never ranks anything, and marks NEEDLE_UNAVAILABLE / NEEDLE_ERROR honestly
if the subprocess cannot be reached, per the task's explicit instruction not
to substitute another model.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]

NEEDLE_TYPE_TO_RAR_TYPE = {
    "document": "document", "spreadsheet": "spreadsheet", "pdf": "pdf",
    "image": "image", "email": "email", "person": "person", "record": "record",
    "none": None,
}
NEEDLE_RECENCY_TO_RAR_HINT = {
    "latest": "latest", "previous": "previous", "earlier": "earlier",
    "same": "same", "none": None,
}


def default_needle_venv_python() -> Path:
    env_override = os.environ.get("NEEDLE_VENV_PYTHON")
    if env_override:
        return Path(env_override)
    base = Path(r"C:\Users\cheta\Development\uri-agent")
    if sys.platform == "win32":
        return base / ".venv-needle" / "Scripts" / "python.exe"
    return base / ".venv-needle" / "bin" / "python"


def check_availability() -> Optional[str]:
    """Returns None if available, else a human-readable unavailability reason."""
    py = default_needle_venv_python()
    if not py.is_file():
        return f"NEEDLE_VENV_PYTHON_NOT_FOUND: {py}"
    inner = REPO_ROOT / "scripts" / "m35_a2_8d_needle_inner_runner.py"
    if not inner.is_file():
        return f"INNER_RUNNER_NOT_FOUND: {inner}"
    try:
        probe = subprocess.run(
            [str(py), "-c", "import needle; print(getattr(needle, '__version__', 'unknown'))"],
            capture_output=True, text=True, timeout=60,
        )
        if probe.returncode != 0:
            return f"NEEDLE_IMPORT_FAILED: {probe.stderr.strip()[:500]}"
    except Exception as exc:
        return f"NEEDLE_PROBE_EXCEPTION: {type(exc).__name__}: {exc}"
    return None


def run_batch(cases: List[Dict[str, str]], timeout_s: int = 600) -> Dict[str, dict]:
    """cases: list of {"case_id": str, "text": str}. Returns case_id -> result dict."""
    py = default_needle_venv_python()
    inner = REPO_ROOT / "scripts" / "m35_a2_8d_needle_inner_runner.py"
    stdin_payload = "\n".join(json.dumps(c) for c in cases) + "\n"

    proc = subprocess.run(
        [str(py), str(inner)],
        input=stdin_payload,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )
    results: Dict[str, dict] = {}
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
            results[r["case_id"]] = r
        except Exception:
            continue
    if proc.returncode != 0 and not results:
        results["__stderr__"] = {"status": "error", "error": proc.stderr[:2000]}
    return results


def to_d1_shaped_reference(needle_result: dict):
    """Adapts a Needle result into the same evidence shape D1 produces
    (span/coarse_type/recency_hint/negation_spans), for the shared RAR-query
    construction step in the main runner. Needle's schema (frozen, S13) has
    no negation field, so negation_spans is always empty here -- a disclosed
    boundary, not an omission."""
    args = needle_result.get("arguments") or {}
    if not needle_result.get("call_made") or not args.get("reference_detected"):
        return None
    span = (args.get("reference_span") or "").strip()
    if not span:
        return None
    coarse_type = NEEDLE_TYPE_TO_RAR_TYPE.get(args.get("coarse_type"))
    recency_hint = NEEDLE_RECENCY_TO_RAR_HINT.get(args.get("recency_hint"))
    return {
        "span": span,
        "coarse_type": coarse_type,
        "recency_hint": recency_hint,
        "negation_spans": (),
    }
