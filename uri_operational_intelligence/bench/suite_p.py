"""Suite P (12 Phase 1 production-adapter scenarios, model_lab/lab/paired.py) through the REAL paired Core with
Runtime v1 served by the OI provider over Core's accepted `brain_composition` seam.

Run from a materialized e8e3b65 test runtime (scripts/oi_materialize_test_runtime.py) with Runtime v1 READY:
    .venv\\Scripts\\python.exe -m uri_operational_intelligence.bench.suite_p [--label NAME]
Writes work/oi/evidence/suite_p_<label>_<ts>.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", default="oi")
    ap.add_argument("--composition", choices=("oi", "stock"), default="oi")
    a = ap.parse_args(argv)
    from test_c5_intent_discovery import Stack
    from model_lab.lab.paired import scenarios, _two_reports
    from uri_operational_intelligence import brain_client as BC, runtime_v1 as R
    from uri_operational_intelligence.core_provider import oi_composition, runtime_v1_composition, selection
    cfg = R.load_config()
    ready = R.RuntimeManager(cfg).status()
    if ready.state != R.READY:
        sys.exit("RUNTIME_NOT_READY:" + ready.state)
    client = BC.BrainClient(R.base_url(cfg))
    sel = selection(cfg)
    results = []
    for sid, setup, turns, check in scenarios():
        comp, provider = (oi_composition if a.composition == "oi" else runtime_v1_composition)(cfg, client)
        st = Stack(18740)
        st.start(**comp)
        try:
            session = _two_reports(st) if setup == "two" else str(uuid.uuid4())
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
            results.append({"id": sid, "pass": ok, "codes": codes, "error": err, "wall_s": round(time.monotonic() - t0, 2),
                            "seam_calls": provider.calls, "memory": st.memory(session)})
            print(sid, "PASS" if ok else "FAIL", codes, flush=True)
        finally:
            st.close()
    summary = {"label": a.label, "composition": a.composition, "passed": sum(r["pass"] for r in results), "total": len(results),
               "seam_calls": sum(len(r["seam_calls"]) for r in results),
               "seam_errors": sum(1 for r in results for c in r["seam_calls"] if c["status"] != "COMPLETE"),
               "readiness": ready.to_dict(), "results": results}
    out = ROOT / "work/oi/evidence" / ("suite_p_%s_%s.json" % (a.label, time.strftime("%Y%m%d-%H%M%S")))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    print(json.dumps({k: summary[k] for k in ("label", "passed", "total", "seam_calls", "seam_errors")}), out)


if __name__ == "__main__":
    main()
