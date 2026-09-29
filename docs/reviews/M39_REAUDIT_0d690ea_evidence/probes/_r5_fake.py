"""Re-audit (0d690ea) fake Claude Code: extra adversarial modes (URI_PROBE_MODE)."""
import glob, json, os, sys
from pathlib import Path
def emit(o): sys.stdout.write(json.dumps(o) + "\n"); sys.stdout.flush()
def main():
    if "--version" in sys.argv: print("2.1.283 (Fake Claude Code, re-audit probe)"); return 0
    sys.stdin.read()
    p = os.environ.get("URI_PROBE_MODE", ""); root = Path(os.environ.get("URI_PROBE_ROOT", "."))
    emit({"type": "system", "subtype": "init", "session_id": "probe", "tools": ["Read", "Edit"]})
    script = Path(sorted(glob.glob("*.py"))[0])
    fix = lambda: script.write_text(script.read_text().replace('"Amt"', '"Amount"'))
    if p == "write_sibling":          # writes a NEW, non-original file into the user's folder; no fix
        (root / "harness_notes.txt").write_text("written by harness\n")
    elif p == "write_sibling_and_fix":
        (root / "harness_notes.txt").write_text("written by harness\n"); fix()
    elif p == "delete_original":
        (root / "report.py").unlink(); fix()
    elif p == "write_original_nofix":  # touches original AND does no fix
        o = root / "report.py"; o.write_text(o.read_text() + "\n# x\n")
    elif p == "write_both_originals":
        for n in ("report.py",):
            o = root / n; o.write_text(o.read_text() + "\n# x\n")
        (root / "sales.xlsx").write_bytes((root / "sales.xlsx").read_bytes() + b"\0"); fix()
    elif p == "rewrite_same_bytes":    # rewrite original with identical bytes (undetectable, and harmless)
        o = root / "report.py"; o.write_bytes(o.read_bytes()); fix()
    elif p == "honest":
        fix()
    emit({"type": "result", "subtype": "success", "is_error": False, "result": "Done. VERIFIED.", "session_id": "probe",
          "num_turns": 2, "total_cost_usd": 0.01, "usage": {}, "modelUsage": {}})
    return 0
if __name__ == "__main__": raise SystemExit(main())
