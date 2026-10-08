"""Runtime tuning for the primary candidate: batch/ubatch sizes vs prefill speed, decision TTFT,
VRAM, and the effect of --cache-ram on resident RAM. Writes evidence/tuning_<name>.json."""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lab import decision, longctx  # noqa: E402
from lab.client import chat  # noqa: E402
from lab.runtime import Server, ServerConfig  # noqa: E402

model, name = sys.argv[1], sys.argv[2]
variants = [("ub512", ["-b", "2048", "-ub", "512"]), ("ub1024", ["-b", "2048", "-ub", "1024"]),
            ("ub2048", ["-b", "2048", "-ub", "2048"])]
directory = decision.real_directory()
dcases = decision.cases()[:12]
dossier, task = longctx.build_package(16000)
out = []
for label, extra in variants + [("ub_best_cache1024", None)]:
    if extra is None:
        best = max(out, key=lambda r: r["long_prefill_tps"] or 0)
        extra = best["extra"] + ["--cache-ram", "1024"]
    cfg = ServerConfig(name=f"tune-{label}", model=model, ctx=32768, ngl=999, extra=tuple(extra), port=18490,
                       mmproj=sys.argv[3] if len(sys.argv) > 3 else None)
    srv = Server(cfg, HERE / "evidence" / "tuning").start()
    chat(srv.url, [{"role": "user", "content": "hi"}], max_tokens=4, template_kwargs={"enable_thinking": False})
    rows = [decision.run_case(srv.url, c, directory, template_kwargs={"enable_thinking": False}, grammar=True) for c in dcases]
    t0 = time.monotonic()
    lr = chat(srv.url, [{"role": "user", "content": dossier + "\n\n" + task}], max_tokens=300,
              template_kwargs={"enable_thinking": False})
    # repeated turn on the same dossier: prompt cache reuse
    lr2 = chat(srv.url, [{"role": "user", "content": dossier + "\n\n" + task}], max_tokens=300,
               template_kwargs={"enable_thinking": False})
    snap = srv.resource_snapshot()
    srv.stop()
    out.append({"label": label, "extra": extra, "decision_ttft_p50": sorted(r["ttft_s"] for r in rows)[len(rows) // 2],
                "decision_total_p50": sorted(r["latency_s"] for r in rows)[len(rows) // 2],
                "decision_correct": sum(r["score"] for r in rows), "long_prompt_tokens": lr.get("prompt_tokens"),
                "long_prefill_tps": lr.get("prefill_tps"), "long_ttft_s": lr.get("ttft_s"), "long_repeat_ttft_s": lr2.get("ttft_s"),
                "resources": snap})
    print(json.dumps(out[-1]))
(HERE / "evidence" / f"tuning_{name}.json").write_text(json.dumps(out, indent=1), encoding="utf-8")

