"""M35 URIv1 -- A2.8D D2: Needle 3 narrow reference-detection inner runner.

Runs INSIDE the dedicated .venv-needle interpreter (not the main URIv1
process) -- invoked as a subprocess by m35_a2_8d_detector_d2_needle.py,
mirroring the existing offline-bridge pattern in
uri_v1/turn/needle_bridge_runtime.py (reused as a *pattern*, not imported,
same reasoning as that file's own module docstring: this script carries no
URIv1 semantic policy and is decode-only).

Frozen boundary (M35_URIV1_A2_8D_VERIFICATION_AND_QUALIFICATION_PLAN.md S13):
the schema below has NO candidate_id field and NO ranking field -- Needle is
structurally unable to emit a resolution decision through this schema.

Reads raw_user_text values from stdin (one JSON object per line:
{"case_id": ..., "text": ...}) and writes one JSON result per line to
stdout. A FRESH agent is constructed for every case (confirmed necessary
during pre-flight smoke testing this session: a reused agent across
.complete() calls exhibits cross-call context bleed -- e.g. a later call's
extracted span belonging to an earlier call's text -- so freshness is a
correctness requirement here, not merely a cleanliness preference).
"""

from __future__ import annotations

import json
import os
import sys
import time

os.environ.setdefault("NEEDLE_TELEMETRY", "0")
os.environ.setdefault("DO_NOT_TRACK", "1")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

import needle  # noqa: E402

SCHEMA = {
    "name": "detect_reference",
    "description": (
        "Always call this exactly once to detect whether the message refers "
        "to a previously-known object (a file, document, email, or person "
        "already known to the assistant), without identifying which specific "
        "object it is."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "reference_detected": {"type": "boolean"},
            "reference_span": {
                "type": "string",
                "description": "verbatim substring of the input naming or pointing at the object, or empty string if none",
            },
            "coarse_type": {
                "type": "string",
                "enum": ["document", "spreadsheet", "pdf", "image", "email", "person", "record", "none"],
            },
            "recency_hint": {
                "type": "string",
                "enum": ["latest", "previous", "earlier", "same", "none"],
            },
        },
        "required": ["reference_detected", "reference_span", "coarse_type", "recency_hint"],
        "additionalProperties": False,
    },
}

SYSTEM = (
    "You are a reference-detection interpreter. Never decline to call "
    "detect_reference. Only extract a reference span and coarse signals; "
    "never decide which specific object is meant."
)


def main() -> int:
    results = []
    for raw_line in sys.stdin:
        raw_line = raw_line.strip()
        if not raw_line:
            continue
        req = json.loads(raw_line)
        case_id = req["case_id"]
        text = req["text"]

        agent = needle.Needle(tools=[SCHEMA], system=SYSTEM, generation=3)
        t0 = time.perf_counter()
        try:
            resp = agent.complete(text, max_new_tokens=200)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            calls = resp.get("function_calls") or []
            call_made = bool(calls) and calls[0].get("name") == "detect_reference"
            args = calls[0].get("arguments", {}) if call_made else {}
            result = {
                "case_id": case_id,
                "status": "ok",
                "call_made": call_made,
                "arguments": args,
                "reasoning": resp.get("reasoning"),
                "confidence": resp.get("confidence"),
                "latency_ms": elapsed_ms,
                "peak_ram_mb": resp.get("peak_ram_mb"),
                "prefill_tps": resp.get("prefill_tps"),
                "decode_tps": resp.get("decode_tps"),
            }
        except Exception as exc:  # surface as a per-case error, never crash the whole run
            result = {
                "case_id": case_id,
                "status": "error",
                "error": f"{type(exc).__name__}: {exc}",
                "call_made": False,
                "arguments": {},
                "latency_ms": (time.perf_counter() - t0) * 1000.0,
            }
        finally:
            try:
                agent.close()
            except Exception:
                pass

        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
