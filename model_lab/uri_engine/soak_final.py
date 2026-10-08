"""Stability soak of the exact Runtime v1 candidate (research only; no Core change).

Realistic URI mixture, sequential, through the persistent BrainClient (model_lab/integration/local_brain.py):
  fast trivial turn, decision contract (grammar), extraction, drafting, grounded answer over a resolved-state package,
  normal bounded reasoning (768-token budget), cached long-context sequence (final layout at 16k: repeat, new turn,
  changed evidence, changed session state), vision (VLM) cases, an idle/wake pause every few cycles, and one
  server restart + client reconnect at mid-run. MTP is on (part of the candidate).
Records per call: kind, wall, server prompt/decode ms, finish reason, validity (JSON/schema where structured), error;
per cycle: server RSS, dedicated VRAM, free RAM, GPU utilisation; at the end: Windows System-log events (WHEA, 4101,
41, 1001) created during the run.

  python model_lab/uri_engine/soak_final.py --minutes 75
Evidence: model_lab/evidence/uri_engine/soak_final.json (+ soak_logs/)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(HERE), str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

import psutil  # noqa: E402

from bench_spec import tasks as spec_tasks  # noqa: E402
from lab import cases as CS, hard, vision  # noqa: E402
from lab.runtime import Server, ServerConfig, gpu_dedicated_mib, gpu_util_pct  # noqa: E402
from model_lab.integration.local_brain import BrainClient  # noqa: E402

CFG = json.loads((LAB / "integration" / "local_brain.json").read_text(encoding="utf-8"))
EVID = LAB / "evidence" / "uri_engine"
MTP = "D:/uri-model-lab/mtp/mtp-qwen36-35b-a3b-Q4_K_M.gguf"
CAND = f"-b 2048 -ub 1024 --cache-ram 2048 --slot-prompt-similarity 0 --checkpoint-min-step 512 --ctx-checkpoints 16 -md {MTP} --spec-type draft-mtp --spec-draft-n-max 2 -otd token_embd.weight=CPU"
FAST = {"enable_thinking": False}
NORMAL = {"enable_thinking": True}


def server_rss():
    for p in psutil.process_iter(["name", "memory_info"]):
        if (p.info["name"] or "").lower() == "llama-server.exe":
            return round(p.info["memory_info"].rss / 2**20, 1)
    return None


def call(client, messages, *, max_tokens, tier="fast", schema=None, kind):
    body = {"model": "local", "messages": messages, "max_tokens": max_tokens, "temperature": 0, "seed": 7, "stream": False,
            "chat_template_kwargs": FAST if tier == "fast" else NORMAL}
    if tier == "normal":
        body["thinking_budget_tokens"] = 768
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "schema": schema, "strict": True}}
    t0 = time.monotonic()
    row = {"kind": kind, "t": dt.datetime.now().isoformat(timespec="seconds")}
    try:
        r = client.post("/v1/chat/completions", body, timeout=600)
        row["status"] = r.status_code
        j = r.json()
        ch = (j.get("choices") or [{}])[0]
        text = (ch.get("message") or {}).get("content") or ""
        tm = j.get("timings") or {}
        row.update({"finish": ch.get("finish_reason"), "prompt_n": tm.get("prompt_n"), "cache_n": tm.get("cache_n"),
                    "prompt_ms": tm.get("prompt_ms"), "predicted_n": tm.get("predicted_n"), "predicted_ms": tm.get("predicted_ms"),
                    "gen_tps": tm.get("predicted_per_second"), "draft_n": tm.get("draft_n"), "draft_acc": tm.get("draft_n_accepted"),
                    "chars": len(text)})
        if schema:
            try:
                obj = json.loads(text)
                row["valid"] = isinstance(obj, dict) and all(k in obj for k in schema.get("required", []))
            except Exception:
                row["valid"] = False
        row["text_head"] = text[:120]
    except Exception as exc:
        row["error"] = f"{type(exc).__name__}: {exc}"[:200]
    row["wall_s"] = round(time.monotonic() - t0, 3)
    return row


def long_context_items():
    f = EVID / "context_reuse" / "prompts_final.json"
    if not f.exists():
        return None
    p = json.loads(f.read_text(encoding="utf-8"))["sizes"]
    key = "16000:0" if "16000:0" in p else sorted(p)[0]
    return p[key]["messages"]


def windows_events(since):
    ps = ("$e=Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date '%s')} -ErrorAction SilentlyContinue | "
          "Where-Object { $_.Id -in 41,1001,4101,4102,6008 -or $_.ProviderName -like '*WHEA*' -or $_.LevelDisplayName -eq 'Critical' }; "
          "$e | ForEach-Object { '{0}|{1}|{2}|{3}' -f $_.TimeCreated, $_.Id, $_.ProviderName, ($_.Message -replace \"`r`n\",' ').Substring(0,[Math]::Min(120,$_.Message.Length)) }") % since
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=60).stdout.strip()
        return [l for l in out.splitlines() if l.strip()]
    except Exception as exc:
        return [f"query failed: {exc}"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--minutes", type=float, default=75)
    ap.add_argument("--idle-every", type=int, default=4, help="idle pause after every N cycles")
    ap.add_argument("--idle-s", type=int, default=90)
    a = ap.parse_args()
    log_dir = EVID / "soak_logs"
    cfg = ServerConfig(name="soak_final", model=CFG["model"]["path"], ctx=32768, ngl=999, port=18493, load_mode="none",
                       mmproj=CFG["model"]["mmproj"], extra=tuple(CAND.split()))
    started = dt.datetime.now()
    srv = Server(cfg, log_dir).start()
    client = BrainClient(srv.url)
    tasks = {t["id"]: t for t in spec_tasks()}
    dc = tasks["decision_contract"]
    simple = {c["id"]: c for c in CS.all_simple_cases()}
    f_cases = [c for c in simple.values() if c["suite"] == "F"][:3]
    c_cases = [c for c in simple.values() if c["suite"] == "C"][:3]
    rh = hard.cases()[:3]
    long_msgs = long_context_items()
    vcases = vision.CASES
    rows, cycles, restarted = [], [], False
    out = {"candidate_argv": cfg.argv(), "load_seconds": srv.load_seconds, "started": started.isoformat(timespec="seconds"),
           "minutes_requested": a.minutes}
    deadline = time.monotonic() + a.minutes * 60
    cyc = 0
    try:
        while time.monotonic() < deadline:
            cyc += 1
            c0 = time.monotonic()
            for fc in f_cases:
                rows.append(call(client, fc["messages"], max_tokens=fc["max_tokens"], kind="fast_trivial"))
            rows.append(call(client, dc["messages"], max_tokens=500, schema=dc["json_schema"], kind="decision_contract"))
            rows.append(call(client, tasks["extract_record"]["messages"], max_tokens=300, kind="extraction"))
            rows.append(call(client, tasks["office_draft"]["messages"], max_tokens=400, kind="drafting"))
            cc = c_cases[cyc % len(c_cases)]
            rows.append(call(client, cc["messages"], max_tokens=cc["max_tokens"], kind="grounded_answer"))
            r = rh[cyc % len(rh)]
            rows.append(call(client, [{"role": "user", "content": r["q"]}], max_tokens=4000, tier="normal", kind="normal_reasoning"))
            if long_msgs:
                for key, kind in (("A", "long16k_A"), ("A", "long16k_repeat"), ("C", "long16k_new_turn"), ("D", "long16k_evidence_changed"),
                                  ("S", "long16k_session_changed"), ("A", "long16k_back_to_A")):
                    rows.append(call(client, long_msgs[key], max_tokens=48, kind=kind))
            vc = vcases[cyc % len(vcases)]
            content = [{"type": "image_url", "image_url": {"url": "data:image/png;base64," + vision._b64(vc["img"]())}},
                       {"type": "text", "text": vc["q"]}]
            rows.append(call(client, [{"role": "system", "content": vision.SYSTEM}, {"role": "user", "content": content}], max_tokens=600, kind="vision"))
            cycles.append({"cycle": cyc, "t": dt.datetime.now().isoformat(timespec="seconds"), "cycle_s": round(time.monotonic() - c0, 1),
                           "server_rss_mib": server_rss(), "vram_mib": gpu_dedicated_mib(), "gpu_util": gpu_util_pct(),
                           "free_ram_mib": round(psutil.virtual_memory().available / 2**20)})
            print(json.dumps(cycles[-1]), "errors so far:", sum(1 for x in rows if x.get("error") or x.get("valid") is False), flush=True)
            (EVID / "soak_final.partial.json").write_text(json.dumps({"rows": rows, "cycles": cycles}), encoding="utf-8")
            if not restarted and time.monotonic() > deadline - a.minutes * 30:   # mid-run: restart + reconnect
                srv.stop()
                err = None
                try:
                    client.post("/v1/chat/completions", {"model": "local", "messages": f_cases[0]["messages"], "max_tokens": 4, "stream": False}, timeout=10, retry_once=False)
                except Exception as exc:
                    err = type(exc).__name__
                srv = Server(cfg, log_dir).start()
                t0 = time.monotonic()
                rr = call(client, f_cases[0]["messages"], max_tokens=f_cases[0]["max_tokens"], kind="after_restart")
                out["restart_reconnect"] = {"error_while_down": err, "reload_seconds": srv.load_seconds, "first_call": rr,
                                            "first_call_wall_s": round(time.monotonic() - t0, 3)}
                restarted = True
            if cyc % a.idle_every == 0 and time.monotonic() < deadline:
                time.sleep(a.idle_s)
                rows.append(call(client, dc["messages"], max_tokens=500, schema=dc["json_schema"], kind="decision_after_idle"))
        out["resources"] = srv.resource_snapshot()
    finally:
        srv.stop()
        client.reset()
    out["ended"] = dt.datetime.now().isoformat(timespec="seconds")
    out["windows_events_during_run"] = windows_events(started.strftime("%Y-%m-%d %H:%M:%S"))
    kinds = sorted({r["kind"] for r in rows})
    summ = {}
    for k in kinds:
        rs = [r for r in rows if r["kind"] == k]
        ok = [r for r in rs if not r.get("error")]
        third = max(1, len(ok) // 3)
        summ[k] = {"n": len(rs), "errors": sum(1 for r in rs if r.get("error")), "invalid": sum(1 for r in rs if r.get("valid") is False),
                   "truncated": sum(1 for r in rs if r.get("finish") == "length"),
                   "wall_p50": round(statistics.median(r["wall_s"] for r in ok), 3) if ok else None,
                   "wall_first_third": round(statistics.median(r["wall_s"] for r in ok[:third]), 3) if ok else None,
                   "wall_last_third": round(statistics.median(r["wall_s"] for r in ok[-third:]), 3) if ok else None,
                   "gen_tps_p50": round(statistics.median(r["gen_tps"] for r in ok if r.get("gen_tps")), 1) if any(r.get("gen_tps") for r in ok) else None,
                   "cache_n_p50": statistics.median(r["cache_n"] for r in ok if r.get("cache_n") is not None) if ok else None}
    mem = {"server_rss_first": cycles[0]["server_rss_mib"] if cycles else None, "server_rss_last": cycles[-1]["server_rss_mib"] if cycles else None,
           "server_rss_max": max((c["server_rss_mib"] or 0) for c in cycles) if cycles else None,
           "vram_max": max((c["vram_mib"] or 0) for c in cycles) if cycles else None,
           "free_ram_min": min(c["free_ram_mib"] for c in cycles) if cycles else None}
    out.update({"cycles": cycles, "rows": rows, "summary": summ, "memory": mem, "total_calls": len(rows),
                "total_errors": sum(1 for r in rows if r.get("error")), "total_invalid": sum(1 for r in rows if r.get("valid") is False)})
    (EVID / "soak_final.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    (EVID / "soak_final.partial.json").unlink(missing_ok=True)
    print(json.dumps({"calls": len(rows), "errors": out["total_errors"], "invalid": out["total_invalid"], "memory": mem,
                      "events": out["windows_events_during_run"], "summary": summ}, indent=1)[:6000])


if __name__ == "__main__":
    main()
