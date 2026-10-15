"""FCV-05 (owner-authorized 2026-10-15): the PowerShell 5.1 headless bridge in scripts/uri_client.ps1 must deliver
the frame bytes unchanged under a UTF-8 console code page (65001), where PS 5.1 used to prepend a UTF-8 BOM."""
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell 5.1 only")


def bridge(tmp_path):
    """The script's own bridge block, run against a child that reports the first bytes it receives."""
    text = (ROOT / "scripts/uri_client.ps1").read_text(encoding="utf-8")
    block = text[text.index("        $start = New-Object System.Diagnostics.ProcessStartInfo"):text.index("        exit $process.ExitCode")]
    dump = tmp_path / "dump.py"
    dump.write_text("import sys\nsys.stdout.write(sys.stdin.buffer.read()[:8].hex())\n", encoding="utf-8")
    script = tmp_path / "bridge.ps1"
    script.write_text(f"$interpreter = '{sys.executable}'\n$arguments = @('-I', '{dump}')\n" + block, encoding="utf-8")
    return script


@pytest.mark.parametrize("codepage", [437, 65001])
def test_bridge_delivers_frames_without_a_bom(tmp_path, codepage):
    script = bridge(tmp_path)
    run = subprocess.run(f'cmd /c "chcp {codepage} >nul & powershell -NoProfile -ExecutionPolicy Bypass -File "{script}" & chcp"',
                         input=b"\x00\x00\x00\x05ABCDE", capture_output=True, timeout=60, shell=False)
    out = run.stdout.decode("ascii", "replace")
    assert out.startswith("0000000541424344"), out
    assert f"Active code page: {codepage}" in out     # the console's encoding is restored afterwards
