"""Extract the Vulkan SDK payload from the LunarG installer without installing it (no registry, no PATH, no
system environment change). The installer (Qt Installer Framework) refuses to run unattended without
elevation because its core component writes machine-scope registry/environment entries; the SDK files
themselves are plain 7z archives appended inside the executable. This carves every 7z archive out by its
signature and exact length (from the 7z start header) and extracts them into one directory.

  python model_lab/uri_engine/carve_vulkan_sdk.py <installer.exe> <dest dir>
Writes <dest dir>/CARVE_RECORD.json with offsets, sizes and sha256 of every carved archive.
"""
from __future__ import annotations

import hashlib
import io
import json
import struct
import sys
from pathlib import Path

import py7zr

SIG = b"7z\xbc\xaf\x27\x1c"


def main(exe, dest):
    exe, dest = Path(exe), Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    data = exe.read_bytes()
    record = {"installer": str(exe), "installer_sha256": hashlib.sha256(data).hexdigest(), "archives": []}
    pos = 0
    while True:
        i = data.find(SIG, pos)
        if i < 0:
            break
        # 7z start header: sig(6) ver(2) startheader_crc(4) next_header_offset(8) next_header_size(8) next_header_crc(4)
        try:
            nho, nhs = struct.unpack_from("<QQ", data, i + 12)
        except struct.error:
            break
        size = 32 + nho + nhs
        if size <= 32 or i + size > len(data):
            pos = i + 1
            continue
        blob = data[i:i + size]
        entry = {"offset": i, "size": size, "sha256": hashlib.sha256(blob).hexdigest()}
        try:
            with py7zr.SevenZipFile(io.BytesIO(blob), "r") as z:
                names = z.getnames()
                entry["files"] = len(names)
                entry["sample"] = names[:5]
                z.extractall(path=dest)
            entry["extracted"] = True
        except Exception as exc:
            entry["extracted"] = False
            entry["error"] = repr(exc)[:200]
        record["archives"].append(entry)
        print(json.dumps(entry)[:300], flush=True)
        pos = i + size
    (dest / "CARVE_RECORD.json").write_text(json.dumps(record, indent=1), encoding="utf-8")
    print("archives:", len(record["archives"]), "extracted:", sum(1 for a in record["archives"] if a.get("extracted")))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
