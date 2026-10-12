"""Suite RH: harder reasoning with answers computed by brute force / execution at import time.

Ground truth is never hand-entered: every expected answer below is produced by code, and the
uniqueness of puzzle solutions is asserted, so a wrong key cannot silently reward a wrong model.
"""
import heapq
import itertools

from .cases import r_score
from . import prompts as P


def _order_puzzle():
    tasks = ["audit", "budget", "census", "draft", "exam", "fees", "grades"]
    cons = [
        ("budget", "<", "draft"), ("audit", "<", "budget"), ("census", ">", "exam"),
        ("fees", "adj", "grades"), ("exam", "<", "audit"), ("grades", "last", None),
        ("draft", "<", "census"),
    ]
    text = ("Seven tasks must be done one per day in some order: audit, budget, census, draft, exam, fees, grades. "
            "Constraints: budget before draft; audit before budget; census after exam; fees and grades on adjacent days; "
            "exam before audit; grades is done last; draft before census. Give the full order as a list.")

    def ok(p):
        pos = {t: i for i, t in enumerate(p)}
        for a, rel, b in cons:
            if rel == "<" and not pos[a] < pos[b]:
                return False
            if rel == ">" and not pos[a] > pos[b]:
                return False
            if rel == "adj" and abs(pos[a] - pos[b]) != 1:
                return False
            if rel == "last" and pos[a] != len(p) - 1:
                return False
        return True
    sols = [list(p) for p in itertools.permutations(tasks) if ok(p)]
    assert len(sols) == 1, sols
    return text, sols[0]


def _truth_puzzle():
    names = ["Anil", "Bina", "Chen", "Devi"]
    text = ("Each of Anil, Bina, Chen and Devi always tells the truth or always lies. "
            "Anil says: 'Bina is a liar.' Bina says: 'Chen and Devi are both truth-tellers.' "
            "Chen says: 'Anil is a liar.' Devi says: 'Anil and Bina are both liars.' "
            "Which of them are truth-tellers? Answer as a list of names.")

    def consistent(t):
        A, B, C, D = t
        claims = [not B, C and D, not A, (not A) and (not B)]
        return all(c == s for c, s in zip(claims, t))
    sols = [t for t in itertools.product([True, False], repeat=4) if consistent(t)]
    assert len(sols) == 1, sols
    return text, [n for n, v in zip(names, sols[0]) if v]


CODE = """data = {"a": [3, 1], "b": [4], "c": []}
total = 0
for k in sorted(data, key=lambda k: -len(data[k])):
    data[k].append(len(k) * 2)
    for v in data[k]:
        if v % 2:
            total += v
        else:
            total -= v // 2
    data.setdefault(k.upper(), []).extend(data[k][:1])
print(total, len(data), sum(len(v) for v in data.values()))"""


def _code_trace():
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(CODE, {})
    out = buf.getvalue().strip()
    return ("What exactly does this Python program print?\n" + CODE + "\nAnswer with the printed line as a string."), out


def _rooms():
    iv = [(9, 11), (9.5, 10.5), (10, 12), (11, 13), (11.5, 12.5), (12, 14), (13, 15), (9, 10), (14, 16), (12.5, 13.5)]
    text = ("Ten meetings need rooms (start-end, 24h clock, a meeting ending at 11 frees its room for one starting at 11): "
            + ", ".join(f"{s:g}-{e:g}" for s, e in iv) + ". What is the minimum number of rooms needed? Answer with a number.")
    events = sorted([(s, 1) for s, _ in iv] + [(e, -1) for _, e in iv], key=lambda x: (x[0], x[1]))
    cur = best = 0
    for _, d in events:
        cur += d
        best = max(best, cur)
    return text, best


def _path():
    edges = {("Hostel", "Library"): 4, ("Hostel", "Canteen"): 2, ("Canteen", "Library"): 1, ("Library", "Admin"): 5,
             ("Canteen", "Lab"): 8, ("Lab", "Admin"): 3, ("Library", "Lab"): 2, ("Admin", "Gate"): 4, ("Lab", "Gate"): 9,
             ("Canteen", "Gate"): 15}
    g = {}
    for (a, b), w in edges.items():
        g.setdefault(a, []).append((b, w))
        g.setdefault(b, []).append((a, w))
    dist = {"Hostel": 0}
    pq = [(0, "Hostel")]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist.get(u, 1e9):
            continue
        for v, w in g[u]:
            if d + w < dist.get(v, 1e9):
                dist[v] = d + w
                heapq.heappush(pq, (d + w, v))
    text = ("Campus walking times in minutes (paths are two-way): " + "; ".join(f"{a}-{b} {w}" for (a, b), w in edges.items())
            + ". What is the shortest walking time from Hostel to Gate? Answer with a number.")
    return text, dist["Gate"]


def _knapsack():
    items = [("projector", 42, 7), ("laptops", 60, 9), ("printer", 18, 3), ("router", 12, 2), ("ups", 25, 5),
             ("scanner", 15, 4), ("speakers", 9, 2), ("tablet", 30, 6)]
    cap = 20
    best = max((sum(v for _, v, _ in c), sorted(n for n, _, _ in c)) for r in range(len(items) + 1)
               for c in itertools.combinations(items, r) if sum(w for _, _, w in c) <= cap)
    text = ("Lab budget is Rs 20 lakh. Items (value score, cost in lakh): " + ", ".join(f"{n} ({v}, {w})" for n, v, w in items)
            + ". Each item at most once. What is the maximum total value score achievable within budget? Answer with a number.")
    return text, best[0]


def _dates():
    import datetime as dt
    start = dt.date(2026, 10, 6)
    # 45 working days (Mon-Fri), excluding listed holidays, counting from the next working day after start.
    hol = {dt.date(2026, 10, 20), dt.date(2026, 11, 8), dt.date(2026, 11, 9), dt.date(2026, 11, 24)}
    d, n = start, 0
    while n < 45:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in hol:
            n += 1
    text = ("A file is received on Tuesday 6 October 2026. The rule allows 45 working days (Monday-Friday) counted from the "
            "next working day, excluding holidays on 20 October, 8 November, 9 November and 24 November 2026. "
            "On what date does the period end? Answer as YYYY-MM-DD.")
    return text, d.isoformat()


BINSEARCH = """1  def find(xs, target):
2      lo, hi = 0, len(xs) - 1
3      while lo < hi:
4          mid = (lo + hi) // 2
5          if xs[mid] == target:
6              return mid
7          if xs[mid] < target:
8              lo = mid + 1
9          else:
10             hi = mid - 1
11     return -1"""


def _bug():
    text = ("This function should return the index of target in the sorted list xs, or -1.\n" + BINSEARCH +
            "\nfind([2, 5, 8], 8) returns -1 instead of 2. Which single line number contains the bug? Answer with the number.")
    return text, 3


def cases():
    out = []
    for cid, fn in (("rh1_order", _order_puzzle), ("rh2_truth", _truth_puzzle), ("rh3_trace", _code_trace),
                    ("rh4_rooms", _rooms), ("rh5_path", _path), ("rh6_knapsack", _knapsack), ("rh7_dates", _dates),
                    ("rh8_bug", _bug)):
        q, a = fn()
        out.append({"id": cid, "q": q, "a": a})
    return out


def build(max_tokens):
    return [{"id": c["id"], "suite": "RH", "max_tokens": max_tokens, "score": r_score(c["a"]), "answer_key": c["a"],
             "messages": [{"role": "system", "content": P.REASONING_SYSTEM}, {"role": "user", "content": c["q"]}]}
            for c in cases()]


