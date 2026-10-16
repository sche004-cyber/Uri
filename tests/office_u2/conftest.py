"""Fixtures for O2 tests. Synthetic documents only (OD-U7). Tests marked `engine` need the pinned LibreOffice on this
PC and are skipped, with a stated reason, when it is missing; they never pass silently."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def pytest_configure(config):
    config.addinivalue_line("markers", "engine: needs the pinned LibreOffice engine on this PC")
    config.addinivalue_line("markers", "windows: needs Windows (Job Objects, WinRT)")


def lo_present() -> bool:
    from uri_office import engines as E
    pin = E.pins()["libreoffice"]
    return (E.engines_root() / pin["dir"] / "program" / "soffice.com").is_file()


def pdf_with_text(path: Path, pages: list, size=(612, 792), font_size=12) -> Path:
    """A minimal valid PDF, one line of Helvetica text per page (written by hand; no PDF library writes text)."""
    objs = []
    kids = []
    font_obj = 3
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(None)                                  # pages, filled below
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for text in pages:
        content = f"BT /F1 {font_size} Tf 72 {size[1] - 100} Td ({text}) Tj ET".encode("latin-1")
        objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
        cid = len(objs)
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {size[0]} {size[1]}] /Contents {cid} 0 R "
                    f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>".encode())
        kids.append(len(objs))
    objs[1] = f"<< /Type /Pages /Kids [{' '.join(f'{k} 0 R' for k in kids)}] /Count {len(kids)} >>".encode()
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, o in enumerate(objs, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


@pytest.fixture
def work(tmp_path):
    d = tmp_path / "files"
    d.mkdir()
    return d


needs_windows = pytest.mark.skipif(os.name != "nt", reason="Windows only (Job Objects, WinRT, LibreOffice pin)")
