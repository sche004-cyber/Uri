"""R2 soak wrapper: runs the frozen soak harness (model_lab/uri_engine/soak_final.py, unchanged) with its evidence
directory redirected to the research evidence folder, optionally with the hash-identical NVMe model copies.
The suballocation-block environment variable and the pressure consumer are set up by the caller.

  GGML_VK_SUBALLOCATION_BLOCK_SIZE=134217728 URI_R2_MODEL_DIR=C:/.../models python soak_r2.py --minutes 60
Evidence: research/adaptive_runtime/evidence/r2_soak/soak_final.json (+ soak_logs/)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "model_lab" / "uri_engine"))
import soak_final as sf  # noqa: E402

out = Path(os.environ.get("URI_R2_SOAK_DIR", ROOT / "research" / "adaptive_runtime" / "evidence" / "r2_soak"))
out.mkdir(parents=True, exist_ok=True)
sf.EVID = out
md = os.environ.get("URI_R2_MODEL_DIR")
if md:
    m = sf.CFG["model"]
    m["path"] = str(Path(md) / Path(m["path"]).name)
    m["mmproj"] = str(Path(md) / Path(m["mmproj"]).name)
    new_mtp = (Path(md) / Path(sf.MTP).name).as_posix()
    sf.CAND = sf.CAND.replace(sf.MTP, new_mtp)
    sf.MTP = new_mtp
print("soak_r2: evidence ->", out, "| model", sf.CFG["model"]["path"], "| env GGML_VK_SUBALLOCATION_BLOCK_SIZE =",
      os.environ.get("GGML_VK_SUBALLOCATION_BLOCK_SIZE", "default"), flush=True)
sf.main()
