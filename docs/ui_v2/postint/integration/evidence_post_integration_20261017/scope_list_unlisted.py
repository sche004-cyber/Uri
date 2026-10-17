"""List paths that tests/phase2a/test_frozen_core.py::test_nothing_changed_outside_checkpoint_and_phase2a_paths
reports as stray, in the materialized runtime given as argv[1] (same logic as the test, read-only)."""
import fnmatch
import sys
import zipfile
from pathlib import Path

root = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tests" / "phase2a"))
import test_frozen_core as T  # noqa: E402
from scripts.ws_materialized_verify import verified_transitions  # noqa: E402

z = {n for n in zipfile.ZipFile(T.CHECKPOINT).namelist() if not n.startswith("GIT_")}
changed = set(T.sh("diff", "--name-only", T.BASE_COMMIT).split()) | set(
    T.sh("ls-files", "--others", "--exclude-standard").split())
changed = {c.replace("\\", "/") for c in changed}
authorized = verified_transitions(T.ROOT)
stray = sorted(c for c in changed if c not in z and c not in authorized
               and not any(fnmatch.fnmatch(c, g) for g in T.ALLOWED_NEW))
print("\n".join(stray))
