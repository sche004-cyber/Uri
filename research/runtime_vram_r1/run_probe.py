"""Load one profile under the GPU lease; record buffers, residency, load time; measure decode on two prompt types,
vision encode (when vision is on), the per-request thinking controls; stop and release.

    python -I run_probe.py <name> --ctx 65536 [--no-mtp] [--vision off|gpu|cpu] [--draft-kv q8_0] [--thinking]
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / "model_lab"))
import vlab  # noqa: E402
import speed  # noqa: E402

URI_SYSTEM = (
    "You are URI, a local Windows assistant for a school office. You decide what the user wants and answer with one "
    "JSON object. Capabilities: calendar.read, calendar.propose_event, mail.draft, office.open_document, "
    "office.export_pdf, files.search, reminders.create, web.search. Rules: never send mail without approval; "
    "never invent dates; ask a clarification question when a required field is missing; keep replies short.\n"
    + "\n".join(f"Standing note {i}: staff member {i} prefers meetings after {9 + i % 6}:00 and replies in English."
                for i in range(1, 41)))
URI_TASKS = [
    "Draft a polite email to the transport office asking them to move the bus fitness test for SK-04-B-7730 to next "
    "Friday, and tell me what you will do.",
    "Find last term's examination timetable PDF, export the first page as PDF and propose a staff meeting on Monday "
    "to review it. What do you need from me?",
    "Remind me tomorrow at 8 to collect the chemistry store key from locker 4417, and draft a two-line note to the "
    "lab assistant about it.",
]
URI_FORMAT = (' Reply ONLY with JSON: {"intent": "...", "capabilities": ["..."], "needs_approval": true|false, '
              '"missing": ["..."], "plan": ["step", ...], "reply": "..."}')


def _image_b64():
    from lab import vision as V
    buf = io.BytesIO()
    V.img_ui().save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def run_speed(srv, reps):
    prose = []
    for _ in range(reps):
        r = speed.stream_chat(srv.url, [{"role": "user", "content": speed.FIXED_PROMPT}], max_tokens=400)
        prose.append({k: v for k, v in r.items() if k not in ("text", "reasoning")})
    uri = []
    for i in range(reps):
        msgs = [{"role": "system", "content": URI_SYSTEM},
                {"role": "user", "content": URI_TASKS[i % len(URI_TASKS)] + URI_FORMAT}]
        r = speed.stream_chat(srv.url, msgs, max_tokens=400)
        row = {k: v for k, v in r.items() if k not in ("text", "reasoning")}
        try:
            json.loads(r["text"][r["text"].index("{"):r["text"].rindex("}") + 1])
            row["valid_json"] = True
        except (ValueError, KeyError):
            row["valid_json"] = False
        uri.append(row)
    return {"prose": prose, "uri_structured": uri}


def run_vision(srv, reps=2):
    img = _image_b64()
    rows = []
    for _ in range(reps):
        msgs = [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img}},
            {"type": "text", "text": "What error message is shown, and which toggles are on? Answer in one sentence."}]}]
        r = speed.stream_chat(srv.url, msgs, max_tokens=80)
        rows.append({"ttft_s": r.get("ttft_s"), "total_s": r.get("total_s"), "prompt_n": r.get("prompt_n"),
                     "prompt_ms": r.get("prompt_ms"), "error": r.get("error"),
                     "mentions_401": "401" in (r.get("text") or ""), "text": (r.get("text") or "")[:300]})
    return rows


def run_thinking(srv):
    """Per-request controls on the same loaded server: off, on with budget 64, on with budget 768."""
    out = {}
    q = [{"role": "user", "content": "A box has 3 red and 5 blue pens. I add 4 red pens and remove 2 blue pens. "
                                     "How many pens are red, as a fraction of all pens? Answer briefly."}]
    for label, think, budget in (("off", False, None), ("on_b64", True, 64), ("on_b768", True, 768)):
        extra = {"thinking_budget_tokens": budget} if budget is not None else None
        r = speed.stream_chat(srv.url, q, max_tokens=1200, thinking=think, extra=extra)
        out[label] = {"reasoning_chars": len(r.get("reasoning") or ""), "answer": (r.get("text") or "")[:200],
                      "predicted_n": r.get("predicted_n"), "finish_reason": r.get("finish_reason"),
                      "total_s": r.get("total_s"), "error": r.get("error")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--ctx", type=int, default=32768)
    ap.add_argument("--ctk", default="q8_0")
    ap.add_argument("--no-mtp", action="store_true")
    ap.add_argument("--vision", default="gpu")
    ap.add_argument("--draft-kv", default="")
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--thinking", action="store_true")
    ap.add_argument("--env", default="", help="NAME=value[,NAME=value]")
    ap.add_argument("--expected-mib", type=int, default=None)
    a = ap.parse_args()
    env = tuple(tuple(x.split("=", 1)) for x in a.env.split(",") if x)
    prof = vlab.Profile(a.name, ctx=a.ctx, ctk=a.ctk, mtp=not a.no_mtp, vision=a.vision, draft_kv=a.draft_kv, env=env)
    run_dir = vlab.EVIDENCE / "probe" / f"{time.strftime('%Y%m%d-%H%M%S')}_{a.name}"
    srv = vlab.Server(prof, run_dir, max_hold_s=900, expected_mib=a.expected_mib)
    rec = srv.record
    try:
        srv.start()
        rec["speed"] = run_speed(srv, a.reps)
        rec["after_speed"] = srv.memory()
        if a.vision != "off":
            rec["vision"] = run_vision(srv)
            rec["after_vision"] = srv.memory()
        if a.thinking:
            rec["thinking"] = run_thinking(srv)
        rec["classification"] = "COMPLETED_WITH_RESULT"
    except Exception as exc:  # recorded, never hidden
        rec["error"] = f"{type(exc).__name__}: {exc}"
        if rec.get("classification") == "STARTED":
            rec["classification"] = "FAILED"
    finally:
        srv.stop()
        rec["after_stop"] = vlab.wait_vram_released(timeout=60)
        vlab.save(run_dir, "probe", rec)
    sp = rec.get("speed", {})
    brief = {"name": a.name, "class": rec.get("classification"), "error": rec.get("error"),
             "load_s": rec.get("load_seconds"),
             "free_before": (rec.get("before") or {}).get("free_for_one_process_mib"),
             "request": (rec.get("buffers") or {}).get("device_total_mib"),
             "device": (rec.get("buffers") or {}).get("device_mib"),
             "host_visible": (rec.get("buffers") or {}).get("host_total_mib"),
             "loaded": rec.get("loaded"), "after_speed": rec.get("after_speed"), "after_vision": rec.get("after_vision"),
             "prose": [(s.get("decode_tps"), s.get("draft_n"), s.get("draft_accepted")) for s in sp.get("prose", [])],
             "uri": [(s.get("prompt_n"), s.get("prompt_tps"), s.get("decode_tps"), s.get("valid_json"))
                     for s in sp.get("uri_structured", [])],
             "vision": [(v.get("ttft_s"), v.get("prompt_ms"), v.get("mentions_401")) for v in rec.get("vision", [])],
             "thinking": rec.get("thinking")}
    print(json.dumps(brief, indent=1, default=str))
    print("EVIDENCE", run_dir)


if __name__ == "__main__":
    main()
