import hashlib
import json
from pathlib import Path
from zipfile import ZipFile

root = Path(__file__).resolve().parents[3]
tree = root / "uri-agent"
new = root / "evidence/phase2close-candidate-20261008-a.zip"
old = root / "evidence/phase2ops-candidate-20261008-r6.zip"
with ZipFile(new) as z, ZipFile(old) as o:
    print("manifest", z.read("MANIFEST.json").decode()[:3000])
    files = [n for n in z.namelist() if not n.startswith("evidence/") and n not in ("GIT_HEAD.txt", "GIT_STATUS.txt", "MANIFEST.json")]
    missing = [n for n in files if not (tree/n).is_file()]
    mismatch = [n for n in files if (tree/n).is_file() and (tree/n).read_bytes() != z.read(n)]
    print("candidate tree files", len(files), "missing", missing, "mismatch", mismatch)
    ofiles = {n for n in o.namelist() if not n.startswith("evidence/") and n not in ("GIT_HEAD.txt", "GIT_STATUS.txt", "MANIFEST.json")}
    nf = set(files)
    print("added", len(nf-ofiles), *sorted(nf-ofiles), sep="\n")
    print("removed", len(ofiles-nf), *sorted(ofiles-nf), sep="\n")
    print("changed", len([n for n in nf&ofiles if z.read(n)!=o.read(n)]), *sorted(n for n in nf&ofiles if z.read(n)!=o.read(n)), sep="\n")
    manifest = json.loads(z.read("MANIFEST.json"))
    packaged = set(z.namelist())- {"GIT_HEAD.txt", "GIT_STATUS.txt", "MANIFEST.json"}
    print("manifest entries", len(manifest), "name match", set(manifest)==packaged,
          "missing names", sorted(packaged-set(manifest)), "extra names", sorted(set(manifest)-packaged),
          "digest mismatch", [n for n in manifest if n in packaged and hashlib.sha256(z.read(n)).hexdigest()!=manifest[n]])
frozen = root.parent / "uri-phase1-integration/uri-agent/work/c1/checkpoints/final-closure-20261005-phase1.zip"
print("frozen archive present", frozen.is_file())
if frozen.is_file():
    print("frozen sha256", hashlib.sha256(frozen.read_bytes()).hexdigest())
    with ZipFile(frozen) as f:
        ff = [n for n in f.namelist() if not n.endswith("/") and n not in ("GIT_HEAD.txt", "GIT_STATUS.txt", "GIT_DIFF.patch", "MANIFEST.json")]
        print("frozen count", len(ff), "missing", [n for n in ff if not (tree/n).is_file()],
              "changed", [n for n in ff if (tree/n).is_file() and (tree/n).read_bytes()!=f.read(n)])
