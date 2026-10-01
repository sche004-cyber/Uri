"""Writes reports/F_EVIDENCE_MANIFEST.json: SHA-256 of every EPQ-1 file plus the earlier evidence it relies on (read-only)."""
import hashlib, json, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
V1 = Path(r"C:\Users\cheta\Development\Uri\_V1")
def h(p): return hashlib.sha256(p.read_bytes()).hexdigest()
files = {str(p.relative_to(HERE)).replace("\\", "/"): {"sha256": h(p), "bytes": p.stat().st_size}
         for p in sorted(HERE.rglob("*")) if p.is_file() and "__pycache__" not in p.parts and p.name not in ("F_EVIDENCE_MANIFEST.json", "_bg.log")}
ext = {}
for rel in ["docs/research/DYNAMIC_PLANNING_CANONICAL_IMPLEMENTATION_REVIEW.md", "docs/research/DYNAMIC_PLANNING_CANONICAL_REVIEW_EVIDENCE.json",
            "experimental/edge_model_tests/experimental_needle_bridge_runtime.py"] + \
           [str(p.relative_to(V1)).replace("\\", "/") for p in sorted((V1 / "experimental/edge_model_tests/fresh_20260929").glob("*")) if p.is_file()]:
    p = V1 / rel
    if p.exists():
        ext[rel] = {"sha256": h(p), "bytes": p.stat().st_size}
head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=HERE, text=True).strip()
out = {"experiment": "EPQ-1", "branch": "claude/project-thread-gb7z7s", "head_when_built": head,
       "files": files, "earlier_evidence_untracked_in_V1_read_only": ext}
(HERE / "reports" / "F_EVIDENCE_MANIFEST.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
print(len(files), "files;", len(ext), "external")
