"""Diagnose p04/p11 interpreter outputs against Core's own groundedness tokenizer (read-only)."""
import glob
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from uri_core.core.intent_discovery import _tokens  # noqa: E402

for m in ("qwen36-35b-a3b-iq3s", "qwen36-35b-a3b", "qwen38-27b", "gemma4-26b-a4b-qat"):
    for f in glob.glob(str(ROOT / f"model_lab/evidence/runs/{m}/*/results.jsonl")):
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            if r["suite"] == "P" and r["id"] in ("p04_implicit_fact", "p11_preference_statement"):
                print(m, r["id"], r["score"], r["interpreter"], r["codes"])
print(_tokens("My office extension is 4412."), _tokens("My office extension is 4412"))
