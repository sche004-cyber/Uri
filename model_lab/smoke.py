"""Smoke test: start a model, check streaming, timings and per-request reasoning controls."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lab.client import chat
from lab.runtime import Server, ServerConfig

model = sys.argv[1]
cfg = ServerConfig(name="smoke", model=model, ctx=int(sys.argv[2]) if len(sys.argv) > 2 else 8192,
                   n_cpu_moe=int(sys.argv[3]) if len(sys.argv) > 3 else 0, extra=tuple(sys.argv[4].split()) if len(sys.argv) > 4 else ())
srv = Server(cfg, Path(__file__).resolve().parent / "evidence" / "smoke").start()
print("load_s", srv.load_seconds)
props = srv.props()
print("template has enable_thinking:", "enable_thinking" in (props.get("chat_template") or ""),
      "reasoning_effort:", "reasoning_effort" in (props.get("chat_template") or ""))
msgs = [{"role": "user", "content": "What is 17*23? Answer with just the number."}]
variants = {
    "default": {},
    "think_off": {"template_kwargs": {"enable_thinking": False}},
    "effort_low": {"template_kwargs": {"reasoning_effort": "low"}},
    "budget0": {"extra": {"reasoning_budget": 0}},
}
for name, kw in variants.items():
    for rep in range(2):
        r = chat(srv.url, msgs, max_tokens=2048, **kw)
        print(name, rep, json.dumps({k: r.get(k) for k in ("content", "ttft_s", "ttfa_s", "total_s", "prompt_tokens",
                                                       "gen_tokens", "gen_tps", "prefill_tps", "error")}),
              "reasoning_chars", len(r["reasoning"]))
print(json.dumps(srv.resource_snapshot()))
srv.stop()

