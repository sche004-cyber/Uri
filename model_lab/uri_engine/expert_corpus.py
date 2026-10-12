"""Build a realistic URI prompt corpus for expert-activation measurement (llama-imatrix counts).

Writes D:/uri-model-lab/uri_engine/corpus_uri.txt made of the prompts URI actually sends: decision
requests (Core system prompt + request JSON), resolved-state answers (C), routes (H), extraction (S),
drafting (O), trivial turns (F) and one 16k session dossier (L). Also writes corpus_generic.txt
(the long dossier filler only) as a contrast corpus.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
LAB = HERE.parent
ROOT = LAB.parent
for p in (str(LAB), str(ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from lab import cases as CS  # noqa: E402
from lab import decision, longctx  # noqa: E402
from lab.paired import INTERPRETER_SYSTEM  # noqa: E402
from scripts.m30_4_decision_quality_analysis import real_directory, turn_state_for  # noqa: E402
from uri_core.core.decision_engine import DECISION_CONTRACT_SYSTEM_PROMPT, build_decision_request, preselect_candidate_ids  # noqa: E402

OUT = Path(r"D:\uri-model-lab\uri_engine")
OUT.mkdir(parents=True, exist_ok=True)


def render(messages):
    # imatrix consumes raw text; approximate the chat template's role framing so the token stream
    # resembles what the server feeds the model.
    parts = []
    for m in messages:
        c = m["content"] if isinstance(m["content"], str) else json.dumps(m["content"], ensure_ascii=False)
        parts.append(f"<|im_start|>{m['role']}\n{c}<|im_end|>\n")
    parts.append("<|im_start|>assistant\n<think>\n\n</think>\n\n")
    return "".join(parts)


def main():
    directory = real_directory()
    chunks = []
    for c in decision.cases():
        st = turn_state_for(c["text"], directory, active_pointer=c.get("active_pointer"),
                            recent_conversation=c.get("recent_conversation"), attempt_history=c.get("attempt_history"))
        pre = preselect_candidate_ids(st, directory) or [s["capability_id"] for s in directory.summaries()]
        req = build_decision_request(st, preselected_ids=pre, capability_directory=directory)
        chunks.append(render([{"role": "system", "content": DECISION_CONTRACT_SYSTEM_PROMPT},
                              {"role": "user", "content": json.dumps(req, ensure_ascii=False)}]))
        chunks.append(render([{"role": "system", "content": INTERPRETER_SYSTEM},
                              {"role": "user", "content": json.dumps({"message": c["text"], "capability": "remember_fact", "slots": ["statement"]})}]))
    simple = CS.all_simple_cases(reasoning_max_tokens=1500)
    for case in simple:
        if case["suite"] in ("C", "H", "S", "O", "F"):
            chunks.append(render(case["messages"]))
    dossier, task = longctx.build_package(16000)
    chunks.append(render([{"role": "system", "content": "You are URI's local assistant. Follow the user's standing instructions."},
                          {"role": "user", "content": "SESSION DOSSIER\n\n" + dossier + "\n\n---\n" + task}]))
    uri = "\n".join(chunks)
    (OUT / "corpus_uri.txt").write_text(uri, encoding="utf-8")
    generic, _ = longctx.build_package(40000, seed=5)
    (OUT / "corpus_generic.txt").write_text(generic, encoding="utf-8")
    print("uri chars", len(uri), "generic chars", len(generic), "chunks", len(chunks))


if __name__ == "__main__":
    main()
