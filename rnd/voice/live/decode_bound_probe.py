"""Bounded decoding check: CPU time on room-noise clips and WER on the 45 speech
recordings, current settings vs temperature 0 only + a token cap proportional to
the audio length. Single process, cpu_threads=4, same machine state for both.
Usage: python -I decode_bound_probe.py <stt evidence dir> <out.json>
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stt_compare", HERE / "stt_compare.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

out_dir = Path(sys.argv[1])
model = WhisperModel(str(sc.MODEL), device="cpu", compute_type="int8", cpu_threads=4)
meta = [m for m in json.loads((out_dir / "recordings.json").read_text(encoding="utf-8"))["items"] if m["rms"] >= 0.005]


def keep(s):
    return s.no_speech_prob < 0.3 and s.avg_logprob > -1.2 and s.compression_ratio < 2.4


def run(a, bounded):
    kw = dict(language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False, hotwords="URI")
    if bounded:
        kw.update(temperature=0.0, max_new_tokens=int(len(a) / 16000 * 8) + 16)
    t = time.process_time()
    w = time.perf_counter()
    segs, _ = model.transcribe(a, **kw)
    segs = [s for s in segs if keep(s)]
    return " ".join(s.text.strip() for s in segs).strip(), round(time.process_time() - t, 2), round(time.perf_counter() - w, 2)


noise = []
for m in meta[:12]:
    a = sc.load(out_dir / m["file"])[: int(16000 * 0.5)]
    base = np.tile(a, 16)
    base = base - base.mean()
    r0 = float(np.sqrt(np.mean(base ** 2))) or 1e-6
    for t in (0.005, 0.02):
        clip = (base * (t / r0)).astype("float32")
        noise.append(clip)
res = {}
for bounded in (False, True):
    label = "bounded" if bounded else "current"
    ncpu = []
    ntext = 0
    for clip in noise:
        text, cpu, wall = run(clip, bounded)
        ncpu.append(cpu)
        ntext += bool(text)
    E = N = EF = 0
    scpu = []
    for m in meta:
        text, cpu, wall = run(sc.load(out_dir / m["file"]), bounded)
        e, n = sc.wer(sc.normalise(m["text"]), sc.normalise(text))
        ef, _ = sc.wer(sc.normalise_format(m["text"]), sc.normalise_format(text))
        E += e
        N += n
        EF += ef
        scpu.append(cpu)
    res[label] = {"noise_clips": len(noise), "noise_clip_seconds": round(len(noise[0]) / 16000, 1),
                  "noise_cpu_s_mean": round(sum(ncpu) / len(ncpu), 2), "noise_cpu_s_max": max(ncpu),
                  "noise_with_text": ntext, "speech_wer_pct": round(100 * E / N, 2),
                  "speech_wer_format_normalised_pct": round(100 * EF / N, 2),
                  "speech_cpu_s_mean": round(sum(scpu) / len(scpu), 2), "speech_cpu_s_max": max(scpu)}
    print(label, json.dumps(res[label]), flush=True)
Path(sys.argv[2]).write_text(json.dumps(res, indent=1), encoding="utf-8")
