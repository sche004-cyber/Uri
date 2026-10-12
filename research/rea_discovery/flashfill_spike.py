"""REA-equivalent discovery spike (research only, not runtime): can a small deterministic programming-by-example
synthesizer (Flash Fill style) cover typical office form transformations from 1-2 examples?

DSL: program = concat(part_1 .. part_k), k <= 3; part = Const(s) | Tok(kind, i, case) | Sub(kind, i, a, b)
  kind in {word, number, alnum, email_user, email_domain}; i indexes from the start (>=0) or end (<0);
  case in {as_is, upper, lower, title}; Sub takes characters [a:b) of a token (initials, year parts).
Search: enumerate parts that explain a prefix of the first example's output, extend left to right keeping the best
60 partial programs per output position, keep programs consistent with ALL examples, rank by a cost that prefers
tokens over literal letters/digits.
Measures: solved (correct on held-out inputs), ambiguous (>1 distinct outputs among top programs on held-out), time.
Run: python research/rea_discovery/flashfill_spike.py   (prints JSON)
"""
import itertools, json, re, statistics, time

KINDS = {"word": r"[A-Za-z]+", "number": r"\d+", "alnum": r"[A-Za-z0-9]+",
         "email_user": r"^[^@\s]+(?=@)", "email_domain": r"(?<=@)[^@\s]+$"}
CASES = ("as_is", "upper", "lower", "title")


def toks(s, kind):
    return re.findall(KINDS[kind], s)


def case(v, c):
    return {"as_is": v, "upper": v.upper(), "lower": v.lower(), "title": v.title()}[c]


def run_part(p, s):
    if p[0] == "const":
        return p[1]
    _, kind, i, c, a, b = p
    t = toks(s, kind)
    if not -len(t) <= i < len(t):
        return None
    v = t[i]
    if a is not None:
        v = v[a:b]
        if not v:
            return None
    return case(v, c)


def run(prog, s):
    out = []
    for p in prog:
        v = run_part(p, s)
        if v is None:
            return None
        out.append(v)
    return "".join(out)


def candidates(inp, out_rest):
    """Parts whose value is a non-empty prefix of out_rest."""
    res = []
    for kind in KINDS:
        n = len(toks(inp, kind))
        for i in list(range(min(n, 4))) + [-1, -2]:
            for c in CASES:
                for a, b in ((None, None), (0, 1), (0, 2), (-2, None), (0, 4)):
                    p = ("tok", kind, i, c, a, b)
                    v = run_part(p, inp)
                    if v and out_rest.startswith(v):
                        res.append(p)
    for L in range(1, min(4, len(out_rest)) + 1):           # short constants (separators, punctuation)
        if not any(ch.isalnum() for ch in out_rest[:L]) or L == 1:
            res.append(("const", out_rest[:L]))
    return res


def cost(prog):
    c = 0.0
    for p in prog:
        if p[0] == "const":
            c += 3.0 if any(ch.isalnum() for ch in p[1]) else 1.0   # literal letters/digits are suspicious
        else:
            c += 1.0 + (0.5 if p[4] is not None else 0) + (0.25 if p[3] != "as_is" else 0) + (0.1 if p[1] == "alnum" else 0)
    return c


def synthesize(examples, max_parts=6, limit=200):
    inp, out = examples[0]
    progs, frontier = [], [((), 0)]
    while frontier and len(progs) < limit:
        nxt = []
        for prog, pos in frontier:
            if pos == len(out):
                if all(run(prog, i) == o for i, o in examples[1:]):
                    progs.append(prog)
                continue
            if len(prog) >= max_parts:
                continue
            for p in candidates(inp, out[pos:]):
                v = run_part(p, inp)
                nxt.append((prog + (p,), pos + len(v)))
        # Version-space style: keep the best few partial programs PER output position (not a global cut, which
        # discards whole branches when many equivalent tokens exist).
        by_pos = {}
        for prog, pos in set(nxt):
            by_pos.setdefault(pos, []).append(prog)
        frontier = [(pr, pos) for pos, prs in by_pos.items() for pr in sorted(prs, key=cost)[:60]]
    progs.sort(key=cost)
    return progs


TASKS = {
    "name_to_last_first_initial": [("Asha Rao", "Rao, A."), ("Vikram Seth", "Seth, V."), ("Meena Iyer", "Iyer, M."), ("Ravi Kumar", "Kumar, R.")],
    "dmy_to_iso": [("31/01/2026", "2026-01-31"), ("05/11/2025", "2025-11-05"), ("15/08/2024", "2024-08-15"), ("02/02/2027", "2027-02-02")],
    "email_to_user": [("asha.rao@school.example", "asha.rao"), ("v.seth@mail.example", "v.seth"), ("ravi@x.example", "ravi"), ("m_iyer@y.example", "m_iyer")],
    "upper_surname": [("Asha Rao", "RAO"), ("Vikram Seth", "SETH"), ("Meena Iyer", "IYER"), ("Ravi Kumar", "KUMAR")],
    "class_section_code": [("Class 7 Section B", "7-B"), ("Class 10 Section A", "10-A"), ("Class 4 Section C", "4-C"), ("Class 12 Section D", "12-D")],
    "initials": [("Asha Rao", "AR"), ("Vikram Seth", "VS"), ("Meena Iyer", "MI"), ("Ravi Kumar", "RK")],
    "phone_group": [("9876543210", "98765 43210"), ("9123456789", "91234 56789"), ("9000011111", "90000 11111"), ("9988776655", "99887 76655")],
    "roll_from_id": [("STU-2026-0147", "0147"), ("STU-2025-0009", "0009"), ("STU-2027-1200", "1200"), ("STU-2024-0333", "0333")],
}


def main():
    out = {"tasks": {}}
    for name, rows in TASKS.items():
        for k in (1, 2):
            train, test = rows[:k], rows[k:]
            t0 = time.perf_counter()
            progs = synthesize(train)
            dt = (time.perf_counter() - t0) * 1000
            best = progs[0] if progs else None
            correct = best is not None and all(run(best, i) == o for i, o in test)
            # ambiguity: do the top-5 consistent programs disagree on held-out inputs?
            outs = {tuple(run(p, i) for i, _ in test) for p in progs[:5]}
            out["tasks"].setdefault(name, {})[f"{k}_example"] = {
                "programs": len(progs), "correct_on_heldout": correct, "ambiguous_top5": len(outs) > 1,
                "ms": round(dt, 1)}
    for k in ("1_example", "2_example"):
        r = [t[k] for t in out["tasks"].values()]
        out[f"summary_{k}"] = {"solved": sum(x["correct_on_heldout"] for x in r), "of": len(r),
                               "ambiguous": sum(x["ambiguous_top5"] for x in r),
                               "ms_p50": round(statistics.median(x["ms"] for x in r), 1),
                               "ms_max": max(x["ms"] for x in r)}
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
