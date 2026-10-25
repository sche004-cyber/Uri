"""M95 measurements (AC-1, AC-14): classification accuracy, latency, memory, token effect, permission friction.

    python -m tests.privacy.measure [out.json]

CPU only; the gateway never touches the GPU. Token counts use a whitespace/punctuation split (no tokenizer
dependency): a relative measure of what sanitization adds or removes, not a provider-exact count.
"""
import gc
import json
import os
import platform
import re
import statistics
import sys
import time
from collections import Counter

from uri_privacy import PrivacyRefused
from uri_privacy.classify import classify

from . import synth
from .helpers import TGateway


def rss_mb():
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        class PMC(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
                (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                               "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                               "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        c = PMC()
        c.cb = ctypes.sizeof(PMC)
        k = ctypes.WinDLL("kernel32")
        k.GetCurrentProcess.restype = wintypes.HANDLE
        psapi = ctypes.WinDLL("psapi")
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMC), wintypes.DWORD]
        psapi.GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
        return c.WorkingSetSize / 2**20
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def toks(s):
    return len(re.findall(r"\w+|[^\w\s]", s))


def accuracy():
    out = {}
    for name, pos, neg in (("core", [(c, t) for c, t, _ in synth.positives()], synth.BENIGN),
                           ("hard_after_fixes", synth.HARD_POSITIVES, synth.HARD_BENIGN),
                           ("held_out_measured_once", synth.HELD_OUT_POSITIVES, synth.HELD_OUT_BENIGN),
                           ("number_shaped_benign", [], synth.NUMBER_BENIGN)):
        n, hit = Counter(), Counter()
        for c, t in pos:
            n[c] += 1
            hit[c] += c in classify(t).categories()
        fp = sum(bool(classify(t).categories()) for t in neg)
        if name == "number_shaped_benign":            # measured where it matters: what WEB_SEARCH would change
            g = TGateway()
            changed = []
            for t in neg:
                try:
                    if g.prepare(t, requester="m", destination="WEB_SEARCH", purpose="m").text != " ".join(t.split()):
                        changed.append(t)
                except PrivacyRefused:
                    changed.append(t)
            out[name] = {"benign": len(neg), "changed_or_refused_at_web_search": len(changed), "examples": changed}
            continue
        out[name] = {"recall": {c: round(hit[c] / n[c], 4) for c in sorted(n)}, "positives": len(pos),
                     "false_negatives": sum(n.values()) - sum(hit.values()), "benign": len(neg),
                     "false_positives": fp, "false_positive_rate": round(fp / len(neg), 4)}
    return out


def _web(g, t):
    """'refused', 'altered' or 'unchanged' at WEB_SEARCH."""
    try:
        out = g.prepare(t, requester="m", destination="WEB_SEARCH", purpose="m", reversible=False).text
    except PrivacyRefused:
        return "refused"
    return "unchanged" if out == " ".join(t.split()) else "altered"


def generated(n=500, seed=23):
    """Owner decision LDEC-006 (digit budget), measured on generated text rather than examples (review FB4 R1-07).
    benign: per class, how often WEB_SEARCH alters or refuses it. Classes over the budget are altered by decision;
    the exempt classes (dates, times, ISO timestamps, IPv4) must stay unchanged. leaks: generated sensitive values
    that reach WEB_SEARCH with their digits intact."""
    import random
    from .test_ldec006 import AADHAAR, CARD, STD_SEPS, compositions, grouped, leaks, _gen_exempt
    rng, g = random.Random(seed), TGateway()
    d = lambda k: "".join(rng.choice("0123456789") for _ in range(k))         # noqa: E731
    classes = {
        "over_budget_by_decision": {
            "amazon_order_ids": lambda: f"amazon order {d(3)}-{d(7)}-{d(7)} status",
            "number_lists": lambda: "numbers " + ", ".join(str(rng.randint(1, 99)) for _ in range(rng.randint(6, 10))),
            "ms_timestamps": lambda: f"event at {rng.randint(1500000000000, 1800000000000)} ms",
            "csv_rows": lambda: ",".join(str(rng.randint(0, 9999)) for _ in range(rng.randint(4, 6))),
            "thousands_groupings": lambda: f"total {rng.randint(10**9, 10**13):,} units",
            "isbn13": lambda: f"ISBN 978-{d(1)}-{d(3)}-{d(5)}-{d(1)}",
        },
        "under_budget_or_exempt": {
            "dates_times_iso_ipv4": lambda: _gen_exempt(rng),
            "ip_port": lambda: f"server {'.'.join(str(rng.randint(0, 255)) for _ in range(4))}:{rng.randint(1, 65535)}",
            "short_ids": lambda: f"order {d(rng.randint(4, 8))} shipped",
            "prices": lambda: f"price {rng.randint(1, 99999)}.{rng.randint(0, 99):02d} rupees for {rng.randint(1, 9)} items",
            "years_and_counts": lambda: f"top {rng.randint(2, 50)} films of {rng.randint(1950, 2030)} rated {rng.randint(1, 10)}",
            "versions": lambda: f"python {rng.randint(2, 3)}.{rng.randint(0, 13)}.{rng.randint(0, 20)} release notes",
        },
    }
    benign = {}
    for group, cls in classes.items():
        for name, make in cls.items():
            c = Counter(_web(g, make()) for _ in range(n))
            benign[f"{group}.{name}"] = {"n": n, "altered_pct": round(100 * c["altered"] / n, 1),
                                         "refused_pct": round(100 * c["refused"] / n, 1)}
    sweeps = {}
    for label, value, prefix in (("card_all_groupings", CARD, "card"), ("aadhaar_all_groupings", AADHAAR, "my aadhaar is")):
        texts = [f"{prefix} {grouped(value, z, [sep])} ok" for z in compositions(len(value)) for sep in STD_SEPS]
        sweeps[label] = {"n": len(texts), "leaked": sum(leaks(t, value, "WEB_SEARCH") for t in texts)}
    gaps = ["x", "ab", " ", "\n", "*", "..", "x ", " x ", "-\n", "_", "#", "|", ";", "~", "\t"]
    comps = list(compositions(16, 6))
    texts = ["card " + grouped(CARD, z, [rng.choice(gaps) for _ in z]) for z in (rng.choice(comps) for _ in range(n * 4))]
    sweeps["card_mixed_gaps"] = {"n": len(texts), "leaked": sum(leaks(t, CARD, "WEB_SEARCH") for t in texts)}
    marks = ["password"[:i] + chr(cp) + "password"[i:] + ": Mango#2026!" for cp in range(0x300, 0x370) for i in range(1, 9)]
    sweeps["password_combining_marks"] = {"n": len(marks), "leaked": sum(
        _web(g, t) != "refused" and "Mango#2026" in g.prepare(t, requester="m", destination="WEB_SEARCH",
                                                               purpose="m", reversible=False).text for t in marks)}
    return {"seed": seed, "benign": benign, "leak_sweeps": sweeps}


def doc(kb):
    base = ("Minutes of the planning meeting on 2026-10-22. Asha Rao summarised the Q3 numbers: revenue 4,512,330, "
            "margin 14.2%. Action: send the draft to asha.rao7@example.in and call +91 98450 12345. Vendor PAN "
            "ABCPE1234F; payment card 4111 1111 1111 1111. Next review in room 4B at 14:30. ")
    return (base * (kb * 1024 // len(base) + 1))[: kb * 1024]


def latency(kb, dest, n):
    g = TGateway()
    text = doc(kb) if kb >= 1 else doc(1)[: int(kb * 1000)]
    for _ in range(3):
        g.prepare(text, requester="m", destination=dest, purpose="m")
    xs = []
    for _ in range(n):
        t = time.perf_counter()
        g.prepare(text, requester="m", destination=dest, purpose="m")
        xs.append((time.perf_counter() - t) * 1000)
    xs.sort()
    return {"kb": kb, "destination": dest, "n": n, "p50_ms": round(statistics.median(xs), 3),
            "p95_ms": round(xs[int(0.95 * (n - 1))], 3), "max_ms": round(xs[-1], 3)}


SCRIPTS = {   # ordinary prose in three scripts with the same synthetic values as doc() (review FB5 R1-02)
    "hindi": "\u092f\u0939 \u090f\u0915 \u0938\u093e\u0927\u093e\u0930\u0923 \u0935\u093e\u0915\u094d\u092f \u0939\u0948\u0964 ",
    "japanese": "\u4eca\u65e5\u306f\u3068\u3066\u3082\u826f\u3044\u5929\u6c17\u3067\u3059\u306d\u3002\u6771\u4eac\u306e\u99c5\u3002",
    "arabic": "\u0647\u0630\u0647 \u062c\u0645\u0644\u0629 \u0639\u0627\u062f\u064a\u0629 \u0644\u0627 \u062a\u062d\u062a\u0648\u064a. ",
}


def script_doc(script, size):
    base = SCRIPTS[script] * 6 + "mail asha.rao7@example.in card 4111 1111 1111 1111. "
    return (base * (size // len(base) + 1))[:size]


def latency_scripts():
    out = []
    for script in sorted(SCRIPTS):
        for size, dest, n in ((400, "WEB_SEARCH", 300), (2048, "EXTERNAL_MODEL", 150), (65536, "EXTERNAL_MODEL", 12)):
            g, text = TGateway(), script_doc(script, size)
            for _ in range(3):
                g.prepare(text, requester="m", destination=dest, purpose="m")
            xs = []
            for _ in range(n):
                t = time.perf_counter()
                g.prepare(text, requester="m", destination=dest, purpose="m")
                xs.append((time.perf_counter() - t) * 1000)
            xs.sort()
            out.append({"script": script, "chars": size, "destination": dest, "n": n,
                        "p50_ms": round(statistics.median(xs), 3), "p95_ms": round(xs[int(0.95 * (n - 1))], 3)})
    # Two-reading path (review FB9 R1-06): one NBSP makes the egress form differ from the original, so the original is
    # classified and rewritten too and the output is checked in both readings.
    for script in ["ascii"] + sorted(SCRIPTS):
        for size, dest, n in ((400, "WEB_SEARCH", 200), (2048, "EXTERNAL_MODEL", 100), (65536, "EXTERNAL_MODEL", 10)):
            base = doc(size // 1024) if script == "ascii" and size >= 1024 else (doc(1)[:size] if script == "ascii"
                                                                               else script_doc(script, size))
            g, text = TGateway(), base.replace(" ", "\u00a0", 1)
            for _ in range(2):
                g.prepare(text, requester="m", destination=dest, purpose="m")
            xs = []
            for _ in range(n):
                t = time.perf_counter()
                g.prepare(text, requester="m", destination=dest, purpose="m")
                xs.append((time.perf_counter() - t) * 1000)
            xs.sort()
            out.append({"script": script + "+nbsp", "chars": size, "destination": dest, "n": n,
                        "p50_ms": round(statistics.median(xs), 3), "p95_ms": round(xs[int(0.95 * (n - 1))], 3)})
    # Multi-reading path from invisible shaping characters (review FB11 R1-07): ZWJ in emoji sequences, ZWNJ in Persian.
    extra = {"emoji+zwj": "family \U0001f468\u200d\U0001f469\u200d\U0001f467 photos and plans for the weekend trip. ",
             "persian+zwnj": "\u0645\u06cc\u200c\u062e\u0648\u0627\u0647\u0645 \u06a9\u062a\u0627\u0628 \u0628\u062e\u0648\u0627\u0646\u0645. "}
    for name, prose in sorted(extra.items()):
        for size, dest, n in ((400, "WEB_SEARCH", 200), (2048, "EXTERNAL_MODEL", 100), (65536, "EXTERNAL_MODEL", 8)):
            base = prose * 6 + "mail asha.rao7@example.in card 4111 1111 1111 1111. "
            g, text = TGateway(), (base * (size // len(base) + 1))[:size]
            for _ in range(2):
                g.prepare(text, requester="m", destination=dest, purpose="m")
            xs = []
            for _ in range(n):
                t = time.perf_counter()
                g.prepare(text, requester="m", destination=dest, purpose="m")
                xs.append((time.perf_counter() - t) * 1000)
            xs.sort()
            out.append({"script": name, "chars": size, "destination": dest, "n": n,
                        "p50_ms": round(statistics.median(xs), 3), "p95_ms": round(xs[int(0.95 * (n - 1))], 3)})
    # Adversarial worst case: refused before any matching (PRIVACY_INPUT_TOO_COMPLEX), and the largest accepted shape.
    g, adv = TGateway(), []
    for text in ("a/" * 32768, "a/" * 1024, "a/" * 200):
        t = time.perf_counter()
        try:
            g.prepare(text, requester="m", destination="EXTERNAL_MODEL", purpose="m")
            res = "sent"
        except PrivacyRefused as exc:
            res = exc.code
        adv.append({"input": f"'a/' x {len(text) // 2}", "ms": round((time.perf_counter() - t) * 1000, 3), "result": res})
    return {"scripts": out, "adversarial": adv}


def memory():
    gc.collect()
    before = rss_mb()
    g = TGateway()
    text = doc(2)
    for i in range(10_000):
        g.prepare(text, requester="m", destination="WEB_SEARCH", purpose="m")
    gc.collect()
    after = rss_mb()
    return {"rss_before_mb": round(before, 1), "rss_after_10k_calls_mb": round(after, 1),
            "delta_mb": round(after - before, 1), "audit_records_in_memory": len(g.audit.records),
            "note": "memory-mode audit keeps records in RAM; production uses URI_PRIVACY_HOME (file audit)"}


def token_effect():
    g = TGateway()
    rows = []
    for dest in ("WEB_SEARCH", "EXTERNAL_MODEL"):
        t = doc(2)
        e = g.prepare(t, requester="m", destination=dest, purpose="m")
        rows.append({"destination": dest, "tokens_in": toks(t), "tokens_out": toks(e.text),
                     "delta_pct": round(100 * (toks(e.text) - toks(t)) / toks(t), 2)})
    return rows


def friction():
    """How often ordinary and sensitive work is interrupted (refusal / grant needed) per destination."""
    g = TGateway()
    texts = [t for _, t, _ in synth.positives(n=10, seed=3)] + synth.BENIGN + synth.HELD_OUT_BENIGN
    out = {}
    for dest in ("WEB_SEARCH", "EXTERNAL_MODEL", "EXTERNAL_AGENT"):
        c = Counter()
        for t in texts:
            try:
                e = g.prepare(t, requester="m", destination=dest, purpose="m")
                c["sanitized" if e.changed else "unchanged"] += 1
            except PrivacyRefused as x:
                c[x.code] += 1
        benign = synth.BENIGN + synth.HELD_OUT_BENIGN + synth.NUMBER_BENIGN
        stopped = 0
        for t in benign:
            try:
                g.prepare(t, requester="m", destination=dest, purpose="m")
            except PrivacyRefused:
                stopped += 1
        out[dest] = {"all_texts": dict(c), "benign_texts_interrupted": stopped, "benign_texts": len(benign)}
    return out


def main(path=None):
    t0 = time.perf_counter()
    import uri_privacy  # noqa: F401  (already imported; kept for the record)
    res = {"schema": "m95-measurements/1", "python": sys.version.split()[0], "platform": platform.platform(),
           "processor": platform.processor(), "gpu_used": False,
           "accuracy": accuracy(), "generated_ldec006": generated(),
           "latency": [latency(0.4, "WEB_SEARCH", 500), latency(2, "WEB_SEARCH", 300), latency(2, "EXTERNAL_MODEL", 300),
                       latency(64, "EXTERNAL_MODEL", 60), latency(64, "LOG", 60)],
           "latency_non_ascii": latency_scripts(), "memory": memory(), "token_effect": token_effect(), "friction": friction()}
    res["elapsed_s"] = round(time.perf_counter() - t0, 2)
    s = json.dumps(res, indent=1)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(s + "\n")
    print(s)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
