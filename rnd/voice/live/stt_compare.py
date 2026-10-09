"""Recogniser comparison on real-microphone recordings (live voice phase, AC-3/AC-4).

Step 1 (record): each reference sentence is synthesised by a Windows voice,
played through the default speakers and captured by the real default
microphone (acoustic path: speaker -> room -> microphone). The talker is
synthetic; the capture path is the real one. Recordings are 16 kHz mono WAV.

Step 2 (score): every engine transcribes the same recordings; WER after a
stated normalisation (lower case, punctuation removed, "3:30"/"3.30" -> "3 30",
digit-group commas removed). Engines:
  * fw-base.en-b5-vad : faster-whisper base.en int8 CPU, beam 5, VAD (URI's final pass)
  * fw-base.en-b1     : same model, beam 1, no VAD (URI's partial pass)
  * sapi-dictation    : System.Speech DictationGrammar from the WAV (built-in Windows)
Not measurable here: Windows.Media.SpeechRecognition (microphone only, no file
input); other Whisper sizes, whisper.cpp, Moonshine, Vosk (not installed; no
download in this phase).

Usage: python -I stt_compare.py record <outdir>
       python -I stt_compare.py score <outdir>
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import wave
from pathlib import Path

SENTENCES = [
    # conversation
    "What is the weather usually like in Gangtok in October?",
    "Can you remind me what meetings I have tomorrow morning?",
    "How long does it take to drive from Siliguri to Gangtok?",
    "Explain the difference between a casual leave and an earned leave.",
    "Which festival holidays are left this year?",
    "Please summarise the last message from the finance department.",
    "Is the local Brain running right now?",
    "Tell me three ways to reduce paper use in the office.",
    "What time is it in London when it is noon in India?",
    "Remember that the laboratory is closed on Friday afternoon.",
    "Stop.",
    "Open the dashboard.",
    # office dictation
    "Dear Sir, I request leave from 15 October to 17 October because of a family function.",
    "The meeting with the Director is rescheduled to Monday at 3:30 in the afternoon.",
    "Please release the payment of Rs 5,000 to the vendor before the end of the month.",
    "Kindly forward the attendance register for September to the establishment section.",
    "I will not be able to attend the training programme on Thursday due to illness.",
    "The budget proposal for the next financial year must reach this office by 30 November.",
    "Mr. Tshering Bhutia has joined the department as an assistant engineer.",
    "Please treat this as urgent and send a reply by tomorrow evening.",
    "The committee has approved the purchase of two printers and one scanner.",
    "Copy to the Joint Secretary for information and necessary action.",
    "The office will remain closed on account of Dussehra.",
    "Thank you for your cooperation, and please let me know if you need anything else.",
]
VOICES = [("sapi", "Microsoft Zira Desktop"), ("onecore", "Microsoft Mark")]
ROOT = Path(__file__).resolve().parents[3]
BRIDGE = ROOT / "uri_ui" / "assets" / "voice" / "voice_engine.ps1"
MODEL = Path(os.environ["LOCALAPPDATA"]) / "URI" / "models" / "faster-whisper-base.en"
SR = 16000
# System.Speech dictation is scored on every 4th recording (12 of 48 before
# exclusions): one file costs it tens of seconds of CPU here, against well under
# a second for faster-whisper. The subset is stated in the results.
SAPI_EVERY = 4


def normalise(t: str) -> list[str]:
    t = t.lower()
    t = re.sub(r"(\d)[:.](\d)", r"\1 \2", t)
    t = re.sub(r"(\d),(\d{3})", r"\1\2", t)
    t = t.replace("rs.", "rs").replace("mr.", "mr")
    t = re.sub(r"[^a-z0-9' ]+", " ", t)
    return t.split()


MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def normalise_format(t: str) -> list[str]:
    """Second, stated normalisation for formatting that does not change meaning:
    ordinals ("30th" -> "30"), date order ("October 15" -> "15 October"),
    currency ("5,000 rupees" -> "rs 5000"), "programme"/"program". Reported
    beside the strict WER, never instead of it."""
    w = " ".join(normalise(t))
    w = re.sub(r"\b(\d+)(st|nd|rd|th)\b", r"\1", w)
    w = re.sub(rf"\b({MONTHS}) (\d+)\b", r"\2 \1", w)
    w = re.sub(r"\b(\d+) rupees\b", r"rs \1", w)
    w = w.replace("programme", "program")
    return w.split()


def wer(ref: list[str], hyp: list[str]) -> tuple[int, int]:
    d = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        prev, d[0] = d[0], i
        for j, h in enumerate(hyp, 1):
            cur = min(d[j] + 1, d[j - 1] + 1, prev + (r != h))
            prev, d[j] = d[j], cur
    return d[len(hyp)], len(ref)


def record(out: Path) -> None:
    import numpy as np
    import sounddevice as sd

    out.mkdir(parents=True, exist_ok=True)
    ps = subprocess.Popen(["powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                           str(BRIDGE)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          env={**os.environ, "URI_VOICE_VERB": "serve"})
    meta = []
    dev = sd.query_devices(kind="input")
    for vi, (eng, name) in enumerate(VOICES):
        for si, text in enumerate(SENTENCES):
            tts = out / f"_tts_{vi}_{si}.wav"
            ps.stdin.write((json.dumps({"engine": eng, "name": name, "text": text, "out": str(tts)}) + "\n").encode())
            ps.stdin.flush()
            r = json.loads(ps.stdout.readline())
            assert r["ok"], r
            with wave.open(str(tts), "rb") as w:
                sr, ch = w.getframerate(), w.getnchannels()
                pcm = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768
            tts.unlink()
            if ch > 1:
                pcm = pcm.reshape(-1, ch).mean(axis=1)
            pad = np.zeros(int(sr * 0.6), dtype="float32")
            play = np.concatenate([pad, pcm, pad])
            rec = sd.playrec(play.reshape(-1, 1), samplerate=sr, channels=1, dtype="float32", blocking=True)
            # resample capture to 16 kHz with an anti-alias average (sr is 22050/24000/16000)
            x = rec[:, 0]
            idx = np.arange(0, len(x), sr / SR)
            y = np.interp(idx, np.arange(len(x)), x).astype("float32")
            f = out / f"v{vi}_s{si:02d}.wav"
            with wave.open(str(f), "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(SR)
                w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
            meta.append({"file": f.name, "voice": f"{eng}:{name}", "text": text,
                         "rms": round(float(np.sqrt(np.mean(y * y))), 5), "seconds": round(len(y) / SR, 2)})
            print(f.name, meta[-1]["rms"], flush=True)
    ps.stdin.write(b"\n")
    ps.stdin.flush()
    ps.wait(10)
    (out / "recordings.json").write_text(json.dumps({"input_device": dev["name"], "captured": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                                     "items": meta}, indent=1), encoding="utf-8")


def load(f: Path):
    import numpy as np

    with wave.open(str(f), "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768


SAPI_PS = r"""
Add-Type -AssemblyName System.Speech
$e = New-Object System.Speech.Recognition.SpeechRecognitionEngine (New-Object System.Globalization.CultureInfo 'en-US')
$e.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar))
foreach ($f in $env:URI_FILES.Split('|')) {
  $sw = [Diagnostics.Stopwatch]::StartNew()
  $e.SetInputToWaveFile($f)
  $words = @()
  while ($true) { $r = $e.Recognize(); if ($null -eq $r) { break }; $words += $r.Text }
  [Console]::Out.WriteLine((ConvertTo-Json -Compress @{ file = [IO.Path]::GetFileName($f); text = ($words -join ' '); ms = $sw.ElapsedMilliseconds }))
}
"""


def score_main(out: Path) -> None:
    allmeta = json.loads((out / "recordings.json").read_text(encoding="utf-8"))["items"]
    # A recording whose level is below the room's noise floor was not heard by
    # the microphone (on 2026-10-09 the speaker level fell about 15x during the
    # last three items); it measures the playback path, not a recogniser, and
    # is excluded with this stated rule rather than silently.
    meta = [m for m in allmeta if m["rms"] >= 0.005]
    excluded = [m["file"] for m in allmeta if m["rms"] < 0.005]
    results = {}
    from faster_whisper import WhisperModel

    t = time.perf_counter()
    model = WhisperModel(str(MODEL), device="cpu", compute_type="int8", cpu_threads=4)
    load_ms = round((time.perf_counter() - t) * 1000)
    for name, kw in [("fw-base.en-b5-vad", dict(beam_size=5, vad_filter=True)),
                     ("fw-base.en-b1", dict(beam_size=1, vad_filter=False, without_timestamps=True))]:
        rows = []
        for m in meta:
            a = load(out / m["file"])
            t = time.perf_counter()
            segs, _ = model.transcribe(a, language="en", condition_on_previous_text=False, **kw)
            text = " ".join(s.text.strip() for s in segs).strip()
            ms = round((time.perf_counter() - t) * 1000)
            e, n = wer(normalise(m["text"]), normalise(text))
            ef, _ = wer(normalise_format(m["text"]), normalise_format(text))
            rows.append({"file": m["file"], "ref": m["text"], "hyp": text, "errors": e, "words": n, "ms": ms,
                         "errors_format_normalised": ef,
                         "audio_s": m["seconds"]})
            print(name, m["file"], e, n, text, flush=True)
        results[name] = rows
        (out / "stt_compare_fw_partial.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    # System.Speech dictation, one process per file with a bound: a first run
    # with all 45 files in one process took over 15 minutes of CPU and hit the
    # run's limit, so each file now has its own 120 s bound and a timeout is
    # recorded as such (empty transcript, counted as errors).
    rows = []
    for m in meta[::SAPI_EVERY]:
        t = time.perf_counter()
        try:
            p = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", SAPI_PS],
                               capture_output=True, text=True, timeout=120,
                               env={**os.environ, "URI_FILES": str(out / m["file"])})
            line = (p.stdout.strip().splitlines() or ["{}"])[-1]
            r = json.loads(line) if line.startswith("{") else {"text": "", "ms": None}
            status = "ok"
        except subprocess.TimeoutExpired:
            r = {"text": "", "ms": None}
            status = "timeout_120s"
        wall = round((time.perf_counter() - t) * 1000)
        e, n = wer(normalise(m["text"]), normalise(r.get("text", "")))
        ef, _ = wer(normalise_format(m["text"]), normalise_format(r.get("text", "")))
        rows.append({"file": m["file"], "ref": m["text"], "hyp": r.get("text", ""), "errors": e, "words": n,
                     "errors_format_normalised": ef,
                     "ms": r.get("ms"), "wall_ms_incl_process_start": wall, "status": status, "audio_s": m["seconds"]})
        print("sapi", m["file"], status, e, n, r.get("text"), flush=True)
    results["sapi-dictation (every 4th recording)"] = rows
    summary = {}
    for k, rows in results.items():
        E = sum(r["errors"] for r in rows)
        N = sum(r["words"] for r in rows)
        ms = sorted(r["ms"] for r in rows if r["ms"] is not None)
        timed = [r for r in rows if r["ms"] is not None]
        rtf = sum(r["ms"] for r in timed) / 1000 / max(1e-9, sum(r["audio_s"] for r in timed))
        by_voice = {}
        for v in ("v0", "v1"):
            vr = [r for r in rows if r["file"].startswith(v)]
            by_voice[v] = round(100 * sum(r["errors"] for r in vr) / max(1, sum(r["words"] for r in vr)), 2)
        EF = sum(r["errors_format_normalised"] for r in rows)
        summary[k] = {"wer_pct": round(100 * E / N, 2), "errors": E, "words": N, "wer_by_voice_pct": by_voice,
                      "wer_format_normalised_pct": round(100 * EF / N, 2),
                      "sentences_exact": sum(1 for r in rows if r["errors"] == 0), "sentences": len(rows),
                      "ms_p50": ms[len(ms) // 2] if ms else None, "ms_max": ms[-1] if ms else None,
                      "real_time_factor": round(rtf, 3)}
    (out / "stt_compare.json").write_text(json.dumps({"model_load_ms": load_ms, "excluded_rms_below_0.005": excluded,
                                                      "summary": summary,
                                                      "rows": results}, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))


def rescore(out: Path) -> None:
    """Recomputes WER (strict and format-normalised) from the saved transcripts;
    no audio is transcribed again."""
    data = json.loads((out / "stt_compare.json").read_text(encoding="utf-8"))
    for k, rows in data["rows"].items():
        for r in rows:
            r["errors"], r["words"] = wer(normalise(r["ref"]), normalise(r["hyp"]))
            r["errors_format_normalised"], _ = wer(normalise_format(r["ref"]), normalise_format(r["hyp"]))
        E = sum(r["errors"] for r in rows)
        EF = sum(r["errors_format_normalised"] for r in rows)
        N = sum(r["words"] for r in rows)
        data["summary"][k].update({"wer_pct": round(100 * E / N, 2), "errors": E, "words": N,
                                   "wer_format_normalised_pct": round(100 * EF / N, 2),
                                   "sentences_exact": sum(1 for r in rows if r["errors"] == 0),
                                   "sentences_exact_format_normalised": sum(
                                       1 for r in rows if r["errors_format_normalised"] == 0)})
    (out / "stt_compare.json").write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(json.dumps(data["summary"], indent=1))


if __name__ == "__main__":
    cmd, out = sys.argv[1], Path(sys.argv[2])
    if cmd == "record":
        record(out)
    elif cmd == "rescore":
        rescore(out)
    else:
        score_main(out)
