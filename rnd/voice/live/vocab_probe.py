"""Same 45 real-microphone recordings, final-pass settings, three bias settings:
none, the assistant name only ("URI", what the service uses), and the name plus
a user vocabulary of local names. WER uses stt_compare's two normalisations.
Usage: python -I vocab_probe.py <stt evidence dir>
"""
import importlib.util
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("stt_compare", HERE / "stt_compare.py")
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)
from faster_whisper import WhisperModel  # noqa: E402

out = Path(sys.argv[1])
meta = [m for m in json.loads((out / "recordings.json").read_text(encoding="utf-8"))["items"] if m["rms"] >= 0.005]
model = WhisperModel(str(sc.MODEL), device="cpu", compute_type="int8", cpu_threads=4)
VOCAB = "URI Gangtok Siliguri Sikkim Tshering Bhutia Dussehra"
res = {}
for label, hw in [("none", None), ("name", "URI"), ("name+vocabulary", VOCAB)]:
    rows = []
    for m in meta:
        a = sc.load(out / m["file"])
        t = time.perf_counter()
        segs, _ = model.transcribe(a, language="en", beam_size=5, vad_filter=True, condition_on_previous_text=False,
                                   hotwords=hw)
        text = " ".join(s.text.strip() for s in segs).strip()
        e, n = sc.wer(sc.normalise(m["text"]), sc.normalise(text))
        ef, _ = sc.wer(sc.normalise_format(m["text"]), sc.normalise_format(text))
        rows.append({"file": m["file"], "ref": m["text"], "hyp": text, "errors": e, "errors_fmt": ef, "words": n,
                     "ms": round((time.perf_counter() - t) * 1000)})
    N = sum(r["words"] for r in rows)
    res[label] = {"hotwords": hw, "wer_pct": round(100 * sum(r["errors"] for r in rows) / N, 2),
                  "wer_format_normalised_pct": round(100 * sum(r["errors_fmt"] for r in rows) / N, 2),
                  "ms_p50": sorted(r["ms"] for r in rows)[len(rows) // 2], "rows": rows}
    print(label, res[label]["wer_pct"], res[label]["wer_format_normalised_pct"], res[label]["ms_p50"], flush=True)
(out / "vocab_probe.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
