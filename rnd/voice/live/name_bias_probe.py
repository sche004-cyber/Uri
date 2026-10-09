"""Does biasing the recogniser toward the assistant's name fix "URI" -> "You are I"?

Records each phrase through the speakers and the real microphone (two voices),
then transcribes the same audio with and without faster-whisper's `hotwords`
bias ("URI"). Also checks that ordinary sentences are not changed by the bias.
Usage: python -I name_bias_probe.py <outdir>
"""
import json
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "uri_ui" / "assets" / "voice" / "voice_engine.ps1"
MODEL = Path(os.environ["LOCALAPPDATA"]) / "URI" / "models" / "faster-whisper-base.en"
PHRASES = ["URI, dashboard.", "URI, open the workspace.", "Hello URI, what can you do?",
           "You are right, I will send it tomorrow.", "What is the capital of Sikkim?"]
VOICES = [("sapi", "Microsoft Zira Desktop"), ("onecore", "Microsoft Mark")]

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
ps = subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(BRIDGE)],
                      stdin=subprocess.PIPE, stdout=subprocess.PIPE, env={**os.environ, "URI_VOICE_VERB": "serve"})
model = WhisperModel(str(MODEL), device="cpu", compute_type="int8", cpu_threads=4)
rows = []
for vi, (eng, name) in enumerate(VOICES):
    for pi, text in enumerate(PHRASES):
        tts = out / f"_t{vi}{pi}.wav"
        ps.stdin.write((json.dumps({"engine": eng, "name": name, "text": text, "out": str(tts)}) + "\n").encode())
        ps.stdin.flush()
        assert json.loads(ps.stdout.readline())["ok"]
        with wave.open(str(tts), "rb") as w:
            sr = w.getframerate()
            pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768
        tts.unlink()
        pad = np.zeros(int(sr * 0.5), dtype="float32")
        rec = sd.playrec(np.concatenate([pad, pcm, pad]).reshape(-1, 1), samplerate=sr, channels=1, dtype="float32", blocking=True)[:, 0]
        a = np.interp(np.arange(0, len(rec), sr / 16000), np.arange(len(rec)), rec).astype("float32")
        r = {"voice": name, "said": text, "rms": round(float(np.sqrt(np.mean(a * a))), 5)}
        for label, kw in [("plain", {}), ("hotwords_URI", {"hotwords": "URI"})]:
            segs, _ = model.transcribe(a, language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False, **kw)
            r[label] = " ".join(s.text.strip() for s in segs).strip()
        rows.append(r)
        print(json.dumps(r), flush=True)
ps.stdin.write(b"\n")
ps.stdin.flush()
(out / "name_bias.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
