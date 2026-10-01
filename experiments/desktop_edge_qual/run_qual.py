"""Run the pre-registered social-route qualification (see PREREGISTRATION.md)."""
import json, re, statistics, sys, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from uri_desktop_seams.harness_first import edge_chat
from uri_desktop_seams.harness_first.social import social_intent

HERE = Path(__file__).resolve().parent
MARKERS = {
    "thanks": r"welcome|pleasure|glad|anytime|no problem",
    "farewell": r"bye|goodbye|see you|take care|night|later",
    "about_uri": r"\buri\b|assistant|help",
}


def ps():
    with urllib.request.urlopen(edge_chat.OLLAMA_URL + "/api/ps", timeout=5) as r:
        return [m["name"] for m in json.loads(r.read())["models"]]


def check_reply(text, intent):
    if edge_chat.validate(text) is not None:
        return False
    m = MARKERS.get(intent)
    return bool(re.search(m, text, re.I)) if m else True


def main():
    corpus = json.loads((HERE / "corpus.json").read_text(encoding="utf-8"))
    out = HERE / "run_r1.jsonl"
    rows = []
    # cold: unload candidate then one call
    urllib.request.urlopen(urllib.request.Request(edge_chat.OLLAMA_URL + "/api/generate",
        data=json.dumps({"model": edge_chat.DEFAULT_MODEL, "keep_alive": 0}).encode(),
        headers={"Content-Type": "application/json"}), timeout=60).read()
    cold = edge_chat.generate("hello", "greeting", timeout_s=60)
    rows.append({"type": "cold", "ms": round(cold.latency_ms, 1), "source": cold.source, "reply": cold.text})
    for case in corpus:
        intent = social_intent(case["text"])
        rec = {"type": "admission", "id": case["id"], "expect": case["expect"], "label": case.get("intent"),
               "admitted": intent is not None, "intent": intent}
        rows.append(rec)
        if intent is None or case["expect"] != "edge":
            continue
        for rep in range(3):
            r = edge_chat.generate(case["text"], intent)
            rows.append({"type": "turn", "id": case["id"], "rep": rep, "intent": intent, "reply": r.text,
                         "source": r.source, "reject": r.reject_reason, "ms": round(r.latency_ms, 1),
                         "reply_ok": r.source == "edge_model" and check_reply(r.text, intent)})
    rows.append({"type": "resident_models_after", "models": ps()})
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")

    adm = [r for r in rows if r["type"] == "admission"]
    turns = [r for r in rows if r["type"] == "turn"]
    esc = [r for r in adm if r["expect"] == "escalate"]
    soc = [r for r in adm if r["expect"] == "edge"]
    admitted_soc = [r for r in soc if r["admitted"]]
    ms = sorted(t["ms"] for t in turns)
    res = {
        "Q1_false_admissions": [r["id"] for r in esc if r["admitted"]],
        "Q2_social_recall": round(len(admitted_soc) / len(soc), 3),
        "Q2_missed": [r["id"] for r in soc if not r["admitted"]],
        "Q3_intent_agreement": round(sum(r["intent"] == r["label"] for r in admitted_soc) / max(1, len(admitted_soc)), 3),
        "Q3_mismatch": [(r["id"], r["label"], r["intent"]) for r in admitted_soc if r["intent"] != r["label"]],
        "Q4_validator_accept": round(sum(t["source"] == "edge_model" for t in turns) / len(turns), 3),
        "Q5_reply_ok": round(sum(t["reply_ok"] for t in turns) / len(turns), 3),
        "Q5_failures": [(t["id"], t["reply"], t["reject"]) for t in turns if not t["reply_ok"]],
        "Q6_warm_ms_p50": statistics.median(ms), "Q6_warm_ms_p95": ms[int(0.95 * (len(ms) - 1))],
        "cold_ms": rows[0]["ms"], "n_turns": len(turns),
    }
    (HERE / "results_r1.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
