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

from uri_privacy import PrivacyGateway, PrivacyRefused
from uri_privacy.classify import classify

from . import synth


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
                           ("held_out_measured_once", synth.HELD_OUT_POSITIVES, synth.HELD_OUT_BENIGN)):
        n, hit = Counter(), Counter()
        for c, t in pos:
            n[c] += 1
            hit[c] += c in classify(t).categories()
        fp = sum(bool(classify(t).categories()) for t in neg)
        out[name] = {"recall": {c: round(hit[c] / n[c], 4) for c in sorted(n)}, "positives": len(pos),
                     "false_negatives": sum(n.values()) - sum(hit.values()), "benign": len(neg),
                     "false_positives": fp, "false_positive_rate": round(fp / len(neg), 4)}
    return out


def doc(kb):
    base = ("Minutes of the planning meeting on 2026-10-22. Asha Rao summarised the Q3 numbers: revenue 4,512,330, "
            "margin 14.2%. Action: send the draft to asha.rao7@example.in and call +91 98450 12345. Vendor PAN "
            "ABCPE1234F; payment card 4111 1111 1111 1111. Next review in room 4B at 14:30. ")
    return (base * (kb * 1024 // len(base) + 1))[: kb * 1024]


def latency(kb, dest, n):
    g = PrivacyGateway()
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


def memory():
    gc.collect()
    before = rss_mb()
    g = PrivacyGateway()
    text = doc(2)
    for i in range(10_000):
        g.prepare(text, requester="m", destination="WEB_SEARCH", purpose="m")
    gc.collect()
    after = rss_mb()
    return {"rss_before_mb": round(before, 1), "rss_after_10k_calls_mb": round(after, 1),
            "delta_mb": round(after - before, 1), "audit_records_in_memory": len(g.audit.records),
            "note": "memory-mode audit keeps records in RAM; production uses URI_PRIVACY_HOME (file audit)"}


def token_effect():
    g = PrivacyGateway()
    rows = []
    for dest in ("WEB_SEARCH", "EXTERNAL_MODEL"):
        t = doc(2)
        e = g.prepare(t, requester="m", destination=dest, purpose="m")
        rows.append({"destination": dest, "tokens_in": toks(t), "tokens_out": toks(e.text),
                     "delta_pct": round(100 * (toks(e.text) - toks(t)) / toks(t), 2)})
    return rows


def friction():
    """How often ordinary and sensitive work is interrupted (refusal / grant needed) per destination."""
    g = PrivacyGateway()
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
        benign = synth.BENIGN + synth.HELD_OUT_BENIGN
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
           "accuracy": accuracy(),
           "latency": [latency(0.4, "WEB_SEARCH", 500), latency(2, "WEB_SEARCH", 300), latency(2, "EXTERNAL_MODEL", 300),
                       latency(64, "EXTERNAL_MODEL", 60), latency(64, "LOG", 60)],
           "memory": memory(), "token_effect": token_effect(), "friction": friction()}
    res["elapsed_s"] = round(time.perf_counter() - t0, 2)
    s = json.dumps(res, indent=1)
    if path:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(s + "\n")
    print(s)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
