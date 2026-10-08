"""Expert-activation skew from an llama-imatrix GGUF (per-layer, per-expert routing counts).

  python model_lab/uri_engine/expert_stats.py D:/uri-model-lab/uri_engine/imatrix_uri.gguf [label]

For each MoE layer the imatrix stores `<tensor>.counts` with one entry per expert (how many tokens
were routed to it). We report, per layer and overall: share of routing mass captured by the hottest
k experts (k = 16, 32, 64, 128), Gini coefficient, number of experts never used, and the VRAM an
"all hot experts resident" cache would need versus the full expert set. Output JSON goes to
model_lab/evidence/uri_engine/expert_stats_<label>.json.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, r"D:\uri-model-lab\pylib")
from gguf import GGUFReader  # noqa: E402

HERE = Path(__file__).resolve().parent
EVID = HERE.parent / "evidence" / "uri_engine"

# bytes per expert per layer in the qualified IQ3_S artifact (from the tensor dump):
# ffn_gate_exps IQ2_S 82.0 MiB/256, ffn_up_exps IQ2_S 82.0 MiB/256, ffn_down_exps IQ3_S 110 MiB/256 (IQ4_XS 3 layers)
EXPERT_BYTES = (85983232 + 85983232 + 115343360) / 256


def gini(xs):
    xs = sorted(xs)
    n = len(xs)
    s = sum(xs)
    if s == 0:
        return 0.0
    cum = 0
    g = 0.0
    for i, x in enumerate(xs, 1):
        cum += x
        g += cum
    return round(1 - 2 * (g / (n * s)) + 1 / n, 4)


def main():
    path = sys.argv[1]
    label = sys.argv[2] if len(sys.argv) > 2 else Path(path).stem
    r = GGUFReader(path)
    per_layer = {}
    for t in r.tensors:
        if not t.name.endswith(".counts"):
            continue
        counts = [int(x) for x in t.data.reshape(-1).tolist()]
        if len(counts) <= 1:
            continue
        name = t.name[: -len(".counts")]
        per_layer[name] = counts
    layers = {}
    agg_top = {16: [], 32: [], 64: [], 128: []}
    total_unused = 0
    for name, c in sorted(per_layer.items()):
        tot = sum(c)
        srt = sorted(c, reverse=True)
        tops = {k: round(sum(srt[:k]) / tot, 4) if tot else None for k in agg_top}
        for k, v in tops.items():
            if v is not None:
                agg_top[k].append(v)
        unused = sum(1 for x in c if x == 0)
        total_unused += unused
        layers[name] = {"tokens_x_topk": tot, "top": tops, "gini": gini(c), "unused": unused,
                        "max_share": round(srt[0] / tot, 4) if tot else None, "min_count": srt[-1]}
    n_layers = len(layers)
    summary = {
        "label": label, "source": path, "moe_layers": n_layers,
        "mean_top_share": {k: round(sum(v) / len(v), 4) for k, v in agg_top.items() if v},
        "mean_gini": round(sum(l["gini"] for l in layers.values()) / n_layers, 4) if n_layers else None,
        "unused_experts_total": total_unused,
        "expert_bytes_iq3s": EXPERT_BYTES,
        "full_expert_set_gib": round(EXPERT_BYTES * 256 * 40 / 2**30, 3),
        "note": "top[k] = fraction of routed (token, expert) assignments served by the k most-used experts of that layer; "
                "with top-8 routing a uniform router gives k/256.",
        "layers": layers,
    }
    EVID.mkdir(parents=True, exist_ok=True)
    out = EVID / f"expert_stats_{label}.json"
    out.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "layers"}, indent=1))
    for name, l in list(layers.items())[:3] + list(layers.items())[-2:]:
        print(name, l["top"], "gini", l["gini"], "unused", l["unused"])


if __name__ == "__main__":
    main()
