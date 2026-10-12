"""Sequential benchmark queue: one model on the GPU at a time; waits for verified downloads."""
import json
import subprocess
import sys
import time
from pathlib import Path

import psutil

HERE = Path(__file__).resolve().parent
PY = sys.executable
M = Path(r"D:\uri-model-lab\models")
LMS = Path(r"C:\Users\cheta\.lmstudio\models")
MANIFEST = Path(r"D:\uri-model-lab\dl\manifest.jsonl")

ALL = "F,D,DG,C,H,S,O,R,P,L"
DEEP = "D,C,H,R"
DEEP_ONLY = "C,H,R"

JOBS = [
    ("gptoss-20b", M / "ggml-org__gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf", "gptoss", ["--paths", "fast", "--suites", ALL]),
    ("gptoss-20b", M / "ggml-org__gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf", "gptoss", ["--paths", "normal,deep", "--suites", DEEP]),
    ("qwen35-9b", LMS / "Qwen/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf", "qwen", ["--paths", "fast", "--suites", ALL]),
    ("qwen35-9b", LMS / "Qwen/Qwen3.5-9B-GGUF/Qwen3.5-9B-Q4_K_M.gguf", "qwen", ["--paths", "normal,deep", "--suites", DEEP]),
    ("qwen35-2b", LMS / "Qwen/Qwen3.5-2B-GGUF/Qwen3.5-2B-Q4_K_M.gguf", "qwen", ["--paths", "fast", "--suites", "F,D,DG,C,H,P"]),
]
# Larger models: fast = everything; normal (budgeted thinking) = D,C,H,R; deep (unbounded) = C,H,R only.
# Unbounded thinking on all 72 decision cases costs ~90 min per model and gpt-oss showed it hurts routing.
for _name, _path, _fam in (
        ("qwen36-35b-a3b", M / "unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-Q4_K_M.gguf", "qwen"),
        ("qwen38-27b", M / "unsloth__Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-IQ4_XS.gguf", "qwen38"),
        ("nemotron35-30b-a3b", M / "ggml-org__NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-Q4_0.gguf", "nemotron")):
    JOBS += [(_name, _path, _fam, ["--ngl", "-1", "--paths", "fast", "--suites", ALL]),
             (_name, _path, _fam, ["--ngl", "-1", "--paths", "normal", "--suites", DEEP]),
             (_name, _path, _fam, ["--ngl", "-1", "--paths", "deep", "--suites", DEEP_ONLY])]


G26 = LMS / "lmstudio-community/gemma-4-26B-A4B-it-QAT-GGUF/gemma-4-26B-A4B-it-QAT-Q4_0.gguf"
G26_MMPROJ = LMS / "lmstudio-community/gemma-4-26B-A4B-it-QAT-GGUF/mmproj-gemma-4-26B-A4B-it-QAT-BF16.gguf"
Q36IQ3 = M / "unsloth__Qwen3.6-35B-A3B-GGUF/Qwen3.6-35B-A3B-UD-IQ3_S.gguf"
JOBS2 = [
    ("qwen36-35b-a3b-iq3s", Q36IQ3, "qwen", ["--ngl", "-1", "--paths", "fast", "--suites", ALL + ",RH"]),
    ("qwen36-35b-a3b-iq3s", Q36IQ3, "qwen", ["--ngl", "-1", "--paths", "normal", "--suites", DEEP + ",RH"]),
    ("qwen36-35b-a3b-iq3s", Q36IQ3, "qwen", ["--ngl", "-1", "--paths", "deep", "--suites", DEEP_ONLY + ",RH"]),
    ("gemma4-26b-a4b-qat", G26, "gemma", ["--paths", "fast", "--suites", "P,RH"]),
    ("gemma4-26b-a4b-qat", G26, "gemma", ["--paths", "normal", "--suites", DEEP + ",RH"]),
    ("gemma4-26b-a4b-qat", G26, "gemma", ["--paths", "deep", "--suites", DEEP_ONLY + ",RH"]),
    ("gemma4-26b-a4b-qat-vision", G26, "gemma", ["--paths", "fast", "--suites", "V", "--mmproj", str(G26_MMPROJ), "--ctx", "16384"]),
    ("gptoss-20b", M / "ggml-org__gpt-oss-20b-GGUF/gpt-oss-20b-MXFP4.gguf", "gptoss", ["--paths", "fast", "--suites", "P,O,L,RH"]),
]
Q38 = M / "unsloth__Qwen3.8-27B-GGUF/Qwen3.8-27B-UD-IQ4_XS.gguf"
Q36_MMPROJ = M / "unsloth__Qwen3.6-35B-A3B-GGUF/mmproj-F16.gguf"
# Finalist experiments: can the quality leader run fully on the GPU, and does the fast MoE carry vision?
JOBS3 = [
    ("qwen38-27b-gpu16k", Q38, "qwen38", ["--ngl", "999", "--ctx", "16384", "--paths", "fast",
                                          "--suites", "F,D,C,H,P,L,RH", "--l-sizes", "4000,12000"]),
    ("qwen38-27b-gpu16k", Q38, "qwen38", ["--ngl", "999", "--ctx", "16384", "--paths", "normal", "--suites", "RH"]),
    ("qwen36-35b-a3b-iq3s-vision", Q36IQ3, "qwen", ["--ngl", "999", "--ctx", "16384", "--paths", "fast", "--suites", "V",
                                                     "--mmproj", str(Q36_MMPROJ)]),
]
if __import__("os").environ.get("URI_QUEUE_SET") == "2":
    JOBS = JOBS2
if __import__("os").environ.get("URI_QUEUE_SET") == "3":
    JOBS = JOBS3


def gpu_busy():
    return any(p.info["name"] and p.info["name"].lower() == "llama-server.exe" for p in psutil.process_iter(["name"]))


def verified(path):
    if not str(path).startswith(str(M)):
        return path.exists()
    if not MANIFEST.exists():
        return False
    for line in MANIFEST.read_text(encoding="utf-8-sig").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if Path(r["local"]) == path and r.get("verified"):
            return True
    return False


def main():
    only = set(sys.argv[1:])
    log = open(HERE / "evidence" / "queue.log", "a", encoding="utf-8")
    pending = [j for j in JOBS if not only or j[0] in only]
    while pending:
        progressed = False
        for job in list(pending):
            name, model, fam, extra = job
            if not verified(model):
                continue
            while gpu_busy():
                time.sleep(15)
            log.write(f"{time.strftime('%H:%M:%S')} START {name} {extra}\n"); log.flush()
            rc = subprocess.call([PY, str(HERE / "run_bench.py"), "--name", name, "--model", str(model), "--family", fam,
                                  "--ctx", "40960", "--l-sizes", "4000,16000,32000"] + extra,
                                 stdout=open(HERE / "evidence" / f"run_{name}.log", "a", encoding="utf-8"), stderr=subprocess.STDOUT)
            log.write(f"{time.strftime('%H:%M:%S')} END {name} rc={rc}\n"); log.flush()
            pending.remove(job)
            progressed = True
            break
        if not progressed:
            time.sleep(60)
    log.write(f"{time.strftime('%H:%M:%S')} QUEUE_DONE\n")


if __name__ == "__main__":
    main()





