"""PC-14 / LDEC-008 evidence: the folding and egress speed-ups are exact.

    python docs/privacy/evidence/fold_equivalence_check.py <old commit>

Loads uri_privacy/classify.py from <old commit> (git show) next to the working copy and compares fold() (text and both
span maps, all four readings) and egress_form() (text and signals) on random texts drawn from ASCII, encodings,
invisible characters, combining marks and several scripts. egress_form() texts holding U+200B, U+200F or U+FEFF are not
compared: their handling changed on purpose (review FB5 R1-06). Characters with a non-decimal digit value are not in
the pool: their folding changed on purpose (FB5 R1-01). Prints the mismatch counts; 0 is the expected result."""
import importlib.util
import random
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))


def main(old_commit):
    src = subprocess.run(["git", "-C", str(ROOT), "show", f"{old_commit}:uri_privacy/classify.py"], check=True,
                         capture_output=True).stdout
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "old_classify.py"
        p.write_bytes(src)
        spec = importlib.util.spec_from_file_location("old_classify", p)
        old = importlib.util.module_from_spec(spec)
        sys.modules["old_classify"] = old
        spec.loader.exec_module(old)
    import uri_privacy.classify as new
    pool = list("abcAZ09 #*%&;x/-.:@\t\n") + ["%41", "%25", "&amp;", "&#x41;", "&lt;", "%E2%80%8B", "  ", "%C3%A9",
                                              "&#8203;", "%2520", "&amp;amp;", "%CC%81", "&#769;"]
    pool += [chr(c) for c in (0xe9, 0x301, 0x200b, 0x200c, 0x200d, 0x200f, 0xfe0f, 0x20e3, 0xfeff, 0xff21, 0x2010,
                              0x2236, 0xff0e, 0x0905, 0x093f, 0x094d, 0x0948, 0x4eca, 0x0644, 0x0627, 0xfefb, 0x00a0,
                              0x3000, 0xff76, 0x2800, 0xe000, 0x0336, 0x2028, 0x2029, 0x0661, 0x0966, 0x0430, 0xfb01,
                              0x216b, 0x064e, 0x1F600, 0x2764, 0x1680, 0x85)]
    fold_bad = egress_bad = compared = 0
    for seed in (1, 2, 3, 4):
        rng = random.Random(seed)
        for _ in range(20000):
            t = "".join(rng.choice(pool) for _ in range(rng.randint(1, 40)))
            for cf, enc in (("", "decode"), (" ", "decode"), (" ", "space"), ("", "literal")):
                fold_bad += old.fold(t, cf, enc) != new.fold(t, cf, enc)
            if not any(c in t for c in "\u200b\u200f\ufeff"):
                compared += 1
                egress_bad += old.egress_form(t) != new.egress_form(t)
    print(f"fold mismatches: {fold_bad} (80000 texts x 4 readings)")
    print(f"egress_form mismatches: {egress_bad} ({compared} texts)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "a9528cd5")
