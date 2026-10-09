"""Segment confidence on noise vs speech (follow-up to noise_guard_probe.py).
Records each segment's no_speech_prob, avg_logprob and compression_ratio for the
same noise clips and the 45 speech recordings, and evaluates candidate rules.
Usage: python -I noise_guard_probe2.py <stt evidence dir> <out.json>
"""
import json
import os
import sys
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

out_dir = Path(sys.argv[1])
model = WhisperModel(str(Path(os.environ["LOCALAPPDATA"]) / "URI" / "models" / "faster-whisper-base.en"),
                     device="cpu", compute_type="int8", cpu_threads=4)
meta = [m for m in json.loads((out_dir / "recordings.json").read_text(encoding="utf-8"))["items"] if m["rms"] >= 0.005]


def load(f):
    with wave.open(str(f), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768


def segs(a):
    s, _ = model.transcribe(a, language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False,
                            hotwords="URI")
    return [{"text": x.text.strip(), "nsp": round(x.no_speech_prob, 3), "lp": round(x.avg_logprob, 3),
             "cr": round(x.compression_ratio, 2)} for x in s]


items = []
for m in meta[:12]:
    a = load(out_dir / m["file"])[: int(16000 * 0.5)]
    base = np.tile(a, 6)
    base = base - base.mean()
    r0 = float(np.sqrt(np.mean(base ** 2))) or 1e-6
    for t in (0.005, 0.01, 0.02):
        items.append({"kind": "noise", "src": m["file"], "rms": t, "segs": segs((base * (t / r0)).astype("float32"))})
for m in meta:
    items.append({"kind": "speech", "src": m["file"], "segs": segs(load(out_dir / m["file"]))})


def keep(seg, rule):
    return rule(seg)


RULES = {
    "nsp<0.6": lambda s: s["nsp"] < 0.6,
    "lp>-0.8": lambda s: s["lp"] > -0.8,
    "nsp<0.5 and lp>-1.0": lambda s: s["nsp"] < 0.5 and s["lp"] > -1.0,
    "lp>-0.7 and cr<2.4": lambda s: s["lp"] > -0.7 and s["cr"] < 2.4,
}
summary = {}
for name, rule in RULES.items():
    noise_sent = 0
    speech_lost_words = 0
    speech_words = 0
    for it in items:
        kept = " ".join(s["text"] for s in it["segs"] if rule(s) and any(c.isalnum() for c in s["text"]))
        if it["kind"] == "noise":
            noise_sent += 1 if kept.strip() else 0
        else:
            allw = sum(len(s["text"].split()) for s in it["segs"])
            keptw = len(kept.split())
            speech_words += allw
            speech_lost_words += allw - keptw
    summary[name] = {"noise_clips_with_text": noise_sent, "speech_words_lost": speech_lost_words,
                     "speech_words": speech_words}
res = {"summary": summary, "items": items}
Path(sys.argv[2]).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps(summary, indent=1))
for it in items:
    if it["kind"] == "noise" and it["segs"]:
        print("NOISE", it["rms"], it["segs"])
ls = sorted((s["lp"], s["nsp"], s["text"][:40]) for it in items if it["kind"] == "speech" for s in it["segs"])
print("SPEECH lowest logprob:", ls[:5])
print("SPEECH highest nsp:", sorted(((s["nsp"], s["lp"], s["text"][:40]) for it in items if it["kind"] == "speech" for s in it["segs"]), reverse=True)[:5])
