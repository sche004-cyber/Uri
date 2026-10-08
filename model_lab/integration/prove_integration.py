"""Proof of the recommended architecture, using the production integration adapter (local_brain.py).

1. Start the resident runtime from local_brain.json (hash-verified) and record load cost.
2. Drive the REAL frozen Phase 1 paired loop (Stack: server app, client persistence, intent
   discovery, gates, approval, signed ticket, execution, independent verification) through
   create_app(composition=local_brain.composition(...)) for every Suite P scenario.
3. Exercise tiered language calls (fast answer, bounded normal analysis, advisory route, vision).
4. Soak: N mixed sequential calls; errors, latency drift and resident memory over time.
Writes model_lab/evidence/integration_proof.json. Touches nothing in uri_core.
"""
import base64
import io
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "model_lab"))

import psutil  # noqa: E402

from model_lab.integration import local_brain as LB  # noqa: E402
from lab import cases as CS, decision, vision  # noqa: E402
from lab.paired import scenarios, _two_reports  # noqa: E402
from lab.runtime import gpu_dedicated_mib  # noqa: E402
from test_c5_intent_discovery import Stack, uid  # noqa: E402


def server_rss():
    for p in psutil.process_iter(["name", "memory_info"]):
        if (p.info["name"] or "").lower() == "llama-server.exe":
            return round(p.info["memory_info"].rss / 2**20, 1)
    return None


def run_phase1(cfg, url):
    sel = LB.selection(cfg)
    out = []
    for sid, setup, turns, check in scenarios():
        st = Stack(18650)
        st.start(**LB.composition(cfg, url))
        try:
            session = _two_reports(st) if setup == "two" else uid()
            outs, last, err = [], None, None
            t0 = time.monotonic()
            try:
                for t in turns:
                    if isinstance(t, tuple):
                        nxt = last if last.get("state") == "approval_required" else st.runner.confirm(session, sel, last)
                        fin = st.runner.decide("Confirm", session, sel, nxt, True) if nxt.get("state") == "approval_required" else nxt
                        outs.append((nxt, fin))
                        last = fin
                    else:
                        last = st.runner.begin(t, session, sel)
                        outs.append(last)
                ok = bool(check(outs, st, session))
            except Exception as exc:
                ok, err = False, f"{type(exc).__name__}: {exc}"
            codes = [o["code"] if isinstance(o, dict) else [o[0].get("code"), o[1].get("code")] for o in outs]
            out.append({"id": sid, "pass": ok, "codes": codes, "error": err, "wall_s": round(time.monotonic() - t0, 2),
                        "memory": st.memory(session)})
        finally:
            st.close()
    return out


def run_tiers(brain):
    res = {}
    t0 = time.monotonic()
    a = brain.answer([{"role": "user", "content": "In one sentence: what is an office order?"}], tier="fast")
    res["fast_answer"] = {"s": round(time.monotonic() - t0, 2), "complete": a["complete"], "text": a["text"][:200]}
    t0 = time.monotonic()
    q = [c for c in __import__("lab.hard", fromlist=["cases"]).cases() if c["id"] == "rh5_path"][0]
    a = brain.answer([{"role": "user", "content": q["q"]}], tier="normal")
    res["normal_analysis"] = {"s": round(time.monotonic() - t0, 2), "complete": a["complete"], "tail": a["text"][-160:],
                              "expected": q["a"]}
    for text in ("Refactor the Flutter settings screens across 14 files and run the tests.", "What's 15% of 2,40,000?",
                 "Remember that the VC meeting moved to Thursday."):
        t0 = time.monotonic()
        res.setdefault("route", []).append({"text": text, "out": brain.route(text), "s": round(time.monotonic() - t0, 2)})
    im = vision.img_ui()
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    t0 = time.monotonic()
    a = brain.answer([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()}},
        {"type": "text", "text": "What error is shown and which toggles are on?"}]}], tier="fast")
    res["vision"] = {"s": round(time.monotonic() - t0, 2), "text": a["text"][:240]}
    return res


def soak(cfg, url, n):
    brain = LB.LocalBrain(cfg, url)
    directory = decision.real_directory()
    dcases = decision.cases()
    ccases = [CS.build_c(c) for c in CS.C_CASES]
    rows, errors = [], 0
    for i in range(n):
        t0 = time.monotonic()
        kind = ("decision", "core_context", "fast")[i % 3]
        try:
            if kind == "decision":
                r = decision.run_case(url, dcases[i % len(dcases)], directory, template_kwargs={"enable_thinking": False}, grammar=True)
                ok = r["status"] == "ok"
            elif kind == "core_context":
                c = ccases[i % len(ccases)]
                a = brain.answer(c["messages"], tier="fast", max_tokens=700)
                ok = a["complete"]
            else:
                a = brain.answer([{"role": "user", "content": f"Give one word that rhymes with 'case' (attempt {i})."}], tier="fast", max_tokens=30)
                ok = bool(a["text"].strip())
        except Exception:
            ok = False
        errors += 0 if ok else 1
        row = {"i": i, "kind": kind, "s": round(time.monotonic() - t0, 3), "ok": ok}
        if i % 15 == 0:
            row.update(rss_mib=server_rss(), vram_mib=gpu_dedicated_mib(), avail_ram_mib=round(psutil.virtual_memory().available / 2**20))
        rows.append(row)
    lat = {k: [r["s"] for r in rows if r["kind"] == k] for k in ("decision", "core_context", "fast")}
    first, last = rows[: n // 3], rows[-(n // 3):]
    return {"n": n, "errors": errors,
            "p50": {k: round(statistics.median(v), 3) for k, v in lat.items() if v},
            "p95": {k: round(sorted(v)[int(0.95 * (len(v) - 1))], 3) for k, v in lat.items() if v},
            "drift_first_third_vs_last_third_s": [round(statistics.mean(r["s"] for r in first), 3),
                                                  round(statistics.mean(r["s"] for r in last), 3)],
            "memory_samples": [r for r in rows if "rss_mib" in r]}


def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 150
    cfg = LB.load_config()
    rt = LB.ResidentRuntime(cfg)
    t0 = time.monotonic()
    rt.verify_model()
    verify_s = round(time.monotonic() - t0, 1)
    t0 = time.monotonic()
    rt.start(verify=False)
    load_s = round(time.monotonic() - t0, 1)
    report = {"config": cfg, "verify_hash_s": verify_s, "load_s": load_s, "after_load": {
        "rss_mib": server_rss(), "vram_mib": gpu_dedicated_mib(), "avail_ram_mib": round(psutil.virtual_memory().available / 2**20)}}
    try:
        report["phase1"] = run_phase1(cfg, rt.url)
        report["phase1_pass"] = f"{sum(r['pass'] for r in report['phase1'])}/{len(report['phase1'])}"
        report["tiers"] = run_tiers(LB.LocalBrain(cfg, rt.url))
        report["soak"] = soak(cfg, rt.url, n)
    finally:
        rt.stop()
    (ROOT / "model_lab" / "evidence" / "integration_proof.json").write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("verify_hash_s", "load_s", "after_load", "phase1_pass")}))
    print(json.dumps(report["tiers"], indent=1)[:2500])
    print(json.dumps({k: v for k, v in report["soak"].items() if k != "memory_samples"}))
    print(json.dumps(report["soak"]["memory_samples"]))


if __name__ == "__main__":
    main()
