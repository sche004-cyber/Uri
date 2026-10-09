"""Hallucination guard check (live voice phase).

Noise clips: the room noise in the real-microphone recordings (first 0.5 s of
each, before the talker starts), tiled to 3 s and scaled to several levels
above the service's silence gate. Speech clips: the 45 real-microphone
recordings. For each clip: the final-pass transcript, VAD-kept duration, and
whether the guard (VAD-kept speech < MIN_SPEECH_S -> no speech) would drop it.
Usage: python -I noise_guard_probe.py <stt evidence dir> <out.json>
"""
import json
import os
import sys
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

MIN_SPEECH_S = 0.25
out_dir = Path(sys.argv[1])
model = WhisperModel(str(Path(os.environ["LOCALAPPDATA"]) / "URI" / "models" / "faster-whisper-base.en"),
                     device="cpu", compute_type="int8", cpu_threads=4)
meta = [m for m in json.loads((out_dir / "recordings.json").read_text(encoding="utf-8"))["items"] if m["rms"] >= 0.005]


def load(f):
    with wave.open(str(f), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768


def run(a):
    segs, info = model.transcribe(a, language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False,
                                  hotwords="URI")
    text = " ".join(s.text.strip() for s in segs).strip()
    return text, round(float(info.duration_after_vad), 3)


rows = []
for m in meta[:12]:
    a = load(out_dir / m["file"])[: int(16000 * 0.5)]
    base = np.tile(a, 6)
    base = base - base.mean()
    r0 = float(np.sqrt(np.mean(base ** 2))) or 1e-6
    for target in (0.005, 0.01, 0.02):
        clip = (base * (target / r0)).astype("float32")
        text, kept = run(clip)
        rows.append({"kind": "noise", "src": m["file"], "rms": target, "text": text, "vad_kept_s": kept,
                     "guard_drops": kept < MIN_SPEECH_S, "would_send": bool(text) and kept >= MIN_SPEECH_S})
speech = []
for m in meta:
    text, kept = run(load(out_dir / m["file"]))
    speech.append({"kind": "speech", "src": m["file"], "text": text, "vad_kept_s": kept,
                   "guard_drops": kept < MIN_SPEECH_S})
res = {"min_speech_s": MIN_SPEECH_S,
       "noise_clips": len(rows), "noise_nonempty_text": sum(1 for r in rows if r["text"]),
       "noise_sent_with_guard": sum(1 for r in rows if r["would_send"]),
       "speech_clips": len(speech), "speech_dropped_by_guard": sum(1 for r in speech if r["guard_drops"]),
       "min_speech_vad_kept_s": min(r["vad_kept_s"] for r in speech),
       "noise": rows, "speech": speech}
Path(sys.argv[2]).write_text(json.dumps(res, indent=1), encoding="utf-8")
print(json.dumps({k: v for k, v in res.items() if k not in ("noise", "speech")}, indent=1))
for r in rows:
    if r["text"]:
        print(r["rms"], r["vad_kept_s"], r["text"])
