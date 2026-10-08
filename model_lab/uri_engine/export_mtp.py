"""Export Qwen3.6-35B-A3B's MTP head as a standalone llama.cpp draft GGUF (research only).

The qualified unsloth GGUF has no `nextn` tensors, so the draft must come from the HF checkpoint. Only the
shards that hold `mtp.*`, `embed_tokens`, `lm_head` and `model.norm` are downloaded
(D:/uri-model-lab/mtp/hf: shards 1, 25, 26 of 26). The converter verifies the index against the files
present, so a reduced index listing only tensors from those shards is written first.

  D:/uri-model-lab/pyconv/Scripts/python.exe model_lab/uri_engine/export_mtp.py [--outtype q8_0|f16|bf16]
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

HF = Path(r"D:\uri-model-lab\mtp\hf")
WORK = Path(r"D:\uri-model-lab\mtp\hf_mtp_only")
OUT = Path(r"D:\uri-model-lab\mtp")
CONVERT = Path(r"D:\uri-model-lab\strata_research\llamacpp-b11425\convert_hf_to_gguf.py")
KEEP_SHARDS = {"model-00001-of-00026.safetensors", "model-00025-of-00026.safetensors", "model-00026-of-00026.safetensors"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outtype", default="q8_0")
    a = ap.parse_args()
    WORK.mkdir(parents=True, exist_ok=True)
    for f in HF.iterdir():
        if f.suffix == ".safetensors":
            if f.name in KEEP_SHARDS:
                link = WORK / f.name
                if not link.exists():
                    try:
                        link.hardlink_to(f)
                    except OSError:
                        shutil.copy2(f, link)
            continue
        if f.name == "model.safetensors.index.json":
            idx = json.loads(f.read_text(encoding="utf-8"))
            wm = {k: v for k, v in idx["weight_map"].items() if v in KEEP_SHARDS}
            (WORK / f.name).write_text(json.dumps({"metadata": idx.get("metadata", {}), "weight_map": wm}, indent=1), encoding="utf-8")
            print("reduced index:", len(wm), "tensors from", sorted(set(wm.values())))
            continue
        shutil.copy2(f, WORK / f.name)
    cmd = [sys.executable, str(CONVERT), str(WORK), "--mtp", "--outtype", a.outtype, "--outfile", str(OUT)]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    for g in OUT.glob("*.gguf"):
        print(g, g.stat().st_size)


if __name__ == "__main__":
    main()
