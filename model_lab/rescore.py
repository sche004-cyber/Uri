"""Re-apply the current deterministic scorers to stored outputs (C,H,R,S,O,F,L) and rebuild summaries.

Raw model outputs are never altered; rescored rows go to results.rescored.jsonl beside the original.
Suites scored by Core itself (D, DG) and live-loop suites (P, V) keep their recorded scores.
"""
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lab import cases as CS, longctx  # noqa: E402
from lab.client import ChatResult  # noqa: E402
from run_bench import summarize  # noqa: E402


# Cases whose expected capability Core's deterministic preselection does not show to the model.
PRESELECTION_GAP = {"x08_web", "x12_fetch_url"}


def scorers():
    s = {}
    for c in CS.C_CASES:
        s[c["id"]] = CS.build_c(c)["score"]
    for c in CS.H_CASES:
        s[c[0]] = CS.build_h(c)["score"]
    for c in CS.R_CASES:
        s[c["id"]] = CS.build_r(c)["score"]
    for c in CS.S_CASES:
        s[c["id"] + "_prompt"] = CS.build_s(c, False)["score"]
        s[c["id"] + "_grammar"] = CS.build_s(c, True)["score"]
    from lab import hard
    for c in hard.build(1000):
        s[c["id"]] = c["score"]
    for c in CS.O_CASES:
        s[c["id"]] = CS.build_o(c)["score"]
    for c in CS.F_CASES:
        s[c[0]] = CS.build_f(c)["score"]
    for c in longctx.build_cases((4000, 16000, 32000, 64000)):
        s[c["id"]] = longctx.score
    return s


def main():
    sc = scorers()
    for res in glob.glob(str(HERE / "evidence/runs/*/*/results.jsonl")):
        rows = []
        for line in open(res, encoding="utf-8"):
            r = json.loads(line)
            if r["suite"] in ("C", "H", "R", "RH", "S", "O", "F", "L") and r["id"] in sc:
                det = sc[r["id"]](ChatResult(content=r.get("content") or ""))
                r["score"], r["detail"] = det.get("score", 0.0), det
            if r["suite"] in ("D", "DG") and r["id"] in PRESELECTION_GAP:
                continue   # expected capability never shown to the model by Core preselection (Core finding B-2)
            rows.append(r)
        out = Path(res).with_name("results.rescored.jsonl")
        out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        summ_path = Path(res).with_name("summary.json")
        meta = json.loads(summ_path.read_text(encoding="utf-8"))["meta"] if summ_path.exists() else {"note": "run interrupted; no meta"}
        Path(res).with_name("summary.rescored.json").write_text(json.dumps({"meta": meta, "summary": summarize(rows)}, indent=1), encoding="utf-8")
        print("rescored", res)


if __name__ == "__main__":
    main()


