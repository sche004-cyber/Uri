"""C1 second review: the running process executes exactly the pinned source bytes.

A start-up hash of the .py files is not enough on its own. Python will execute
timestamp-validated __pycache__ bytecode even under -B, an extension module or
sourceless .pyc shadows a .py, a lazy import reads whatever is on disk later,
and a namespace package merges portions from every sys.path entry. These tests
attack each path against the real entrypoint and the real pin.
"""
import importlib.util
import json
import marshal
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import textwrap
import uuid

import pytest

from uri_core.core.runtime_identity import (PAIRED_COMPOSITION, RuntimeIdentityError, RuntimeManifest, dpapi,
                                            provision, source_files)
from scripts.uri_server_launcher import listener, owned_instance

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv/Scripts/python.exe"


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def plant_stale_bytecode(module_rel, marker):
    """Write timestamp-valid bytecode that drops a marker, then runs the real source."""
    source = ROOT / module_rel
    st = os.stat(source)
    payload = textwrap.dedent(f"""
        open({marker!r}, "w").close()
        exec(compile(open(__file__, "rb").read(), __file__, "exec"), globals())
    """)
    code = compile(payload, str(source), "exec")
    cached = Path(importlib.util.cache_from_source(str(source)))
    cached.parent.mkdir(exist_ok=True)
    cached.write_bytes(importlib.util.MAGIC_NUMBER + struct.pack("<III", 0, int(st.st_mtime) & 0xFFFFFFFF,
                                                                   st.st_size & 0xFFFFFFFF) + marshal.dumps(code))
    return cached


def run_isolated(script):
    return subprocess.run([str(PYTHON), "-B", "-I", "-c", script], cwd=str(ROOT / "work/c1"),
                          capture_output=True, text=True, timeout=120)


# Exactly the import set-up the real entrypoints perform: the C1 bootstrap gate loaded by exact path,
# the source root never on sys.path.
BOOTSTRAP = textwrap.dedent(f"""
    import sys
    from pathlib import Path
    _boot = Path({str(ROOT / "scripts/c1_bootstrap.py")!r})
    c1_bootstrap = type(sys)("c1_bootstrap")
    c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_boot), _boot.read_bytes()
    exec(compile(c1_bootstrap.SOURCE, str(_boot), "exec"), c1_bootstrap.__dict__)
    sys.modules["c1_bootstrap"] = c1_bootstrap
    c1_bootstrap.install({str(ROOT)!r})
""")

PRELUDE = BOOTSTRAP + textwrap.dedent(f"""
    import json
    from uri_core.core.runtime_identity import install_source_pin, source_files
    root = Path({str(ROOT)!r})
    files = source_files(root)
""")


def _start(manifest):
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts/uri_server.ps1"), "-Manifest", str(manifest.path), "-Action", "start",
                        "-TimeoutSeconds", "30"], capture_output=True, text=True)
    lines = r.stdout.strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError):
        return {"result": "NO_RESULT", "returncode": r.returncode}


def _stop(manifest):
    proc = listener(manifest.data["port"])
    if proc is not None:
        owned_instance(manifest, proc)
        proc.terminate()
        proc.wait(timeout=10)


def test_stale_bytecode_is_never_executed_by_the_real_server():
    """Without the pin, both planted .pyc files run under the exact '-B -I' launch flags."""
    state = ROOT / "work/c1" / uuid.uuid4().hex
    manifest = RuntimeManifest(provision(ROOT, state, PYTHON, free_port(), composition=PAIRED_COMPOSITION))
    planted = [plant_stale_bytecode("uri_core/core/runtime_identity.py", "STALE_BOOTSTRAP_EXECUTED"),
               plant_stale_bytecode("uri_core/app/paired_server.py", "STALE_LAZY_EXECUTED")]
    try:
        r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                            str(ROOT / "scripts/uri_server.ps1"), "-Manifest", str(manifest.path), "-Action", "start",
                            "-TimeoutSeconds", "30"], capture_output=True, text=True)
        result = json.loads(r.stdout.strip().splitlines()[-1])
        assert result["result"] == "STARTED", result
        assert not (state / "STALE_BOOTSTRAP_EXECUTED").exists()
        assert not (state / "STALE_LAZY_EXECUTED").exists()
    finally:
        for path in planted:
            path.unlink(missing_ok=True)
        proc = listener(manifest.data["port"])
        if proc is not None:
            owned_instance(manifest, proc)
            proc.terminate()
            proc.wait(timeout=10)


def test_planted_bytecode_would_run_without_the_pin():
    """Control: proves the attack is real, so the test above is not vacuous."""
    marker = ROOT / "work/c1" / ("control_" + uuid.uuid4().hex)
    cached = plant_stale_bytecode("uri_core/reference_binding/facts.py", str(marker))
    try:
        r = run_isolated(f"import sys; sys.path.insert(0, {str(ROOT)!r}); import uri_core.reference_binding.facts")
        assert r.returncode == 0, r.stderr
        assert marker.exists()
    finally:
        cached.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)


def test_post_validation_drift_is_refused_for_lazy_imports():
    r = run_isolated(PRELUDE + textwrap.dedent("""
        files["uri_core/reference_binding/facts.py"] = "0" * 64
        install_source_pin(root, files)
        try:
            import uri_core.reference_binding.facts
        except ImportError as exc:
            print(exc)
    """))
    assert r.stdout.strip() == "C1_SOURCE_DRIFT", r.stderr


def test_unpinned_and_shadow_modules_are_refused():
    sourceless = ROOT / "uri_core/reference_binding/zz_c1_sourceless_probe.pyc"
    sourceless.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(compile("X=1", "x", "exec")))
    extra = ROOT / "work/c1" / ("portion_" + uuid.uuid4().hex)
    (extra / "uri_core").mkdir(parents=True)
    (extra / "uri_core/zz_c1_portion_probe.py").write_text("X=1\n")
    try:
        control = run_isolated(f"import sys, importlib.util; sys.path.insert(0, {str(ROOT)!r}); sys.path.append({str(extra)!r});"
                               "import uri_core.reference_binding.zz_c1_sourceless_probe, uri_core.zz_c1_portion_probe;"
                               "print(importlib.util.find_spec('scripts.killProcName').origin)")
        assert control.returncode == 0, control.stderr  # all three resolve without the pin
        assert "site-packages" in control.stdout  # pywin32 merges its 'scripts' dir into our namespace
        r = run_isolated(PRELUDE + textwrap.dedent(f"""
            import scripts.uri_server_launcher  # namespace imported before the pin, as in the real entrypoints
            install_source_pin(root, files)
            sys.path.append({str(extra)!r})
            for name in ("uri_core.reference_binding.zz_c1_sourceless_probe", "uri_core.zz_c1_portion_probe",
                         "uri_harness_adapters.zz_missing", "scripts.validate_c5_live", "scripts.killProcName"):
                try:
                    __import__(name)
                    print("LOADED", name)
                except ImportError as exc:
                    print(exc)
            print(sys.modules["scripts"].__path__ == [str(root / "scripts")])
        """))
        assert r.stdout.split() == ["C1_SOURCE_NOT_PINNED"] * 5 + ["True"], (r.stdout, r.stderr)
        # A foreign namespace portion that is present when the pin is installed fails closed.
        r = run_isolated(PRELUDE + textwrap.dedent(f"""
            import uri_core
            uri_core.__path__ = [{str(extra / "uri_core")!r}]
            try:
                install_source_pin(root, files)
            except Exception as exc:
                print(exc)
        """))
        assert r.stdout.strip() == "SOURCE_MODULE_UNPINNED", r.stderr
    finally:
        sourceless.unlink(missing_ok=True)


def test_already_imported_module_must_match_its_pin():
    r = run_isolated(PRELUDE + textwrap.dedent("""
        files["uri_core/core/runtime_identity.py"] = "0" * 64
        try:
            install_source_pin(root, files)
        except Exception as exc:
            print(exc)
    """))
    assert r.stdout.strip() == "SOURCE_MODULE_UNPINNED", r.stderr


def test_pinned_imports_still_work_and_adapters_are_covered():
    files = source_files(ROOT)
    assert "uri_harness_adapters/__init__.py" in files
    r = run_isolated(PRELUDE + textwrap.dedent("""
        install_source_pin(root, files)
        import uri_core.app.paired_server, uri_harness_adapters, uri_core.reference_binding.binding
        print(type(uri_core.app.paired_server.__loader__).__name__, uri_harness_adapters.__file__.endswith("__init__.py"))
    """))
    assert r.stdout.split() == ["_PinnedSourceLoader", "True"], (r.stdout, r.stderr)


def test_dpapi_round_trip_and_tamper():
    for data in (b"", b"\x00" * 3, os.urandom(32), os.urandom(5000)):
        blob = dpapi(data)
        assert blob != data and dpapi(blob, True) == data
    blob = bytearray(dpapi(os.urandom(32)))
    blob[-5] ^= 0xFF
    with pytest.raises(RuntimeIdentityError, match="PROTECTED_KEY_UNAVAILABLE"):
        dpapi(bytes(blob), True)
    with pytest.raises(RuntimeIdentityError, match="PROTECTED_KEY_UNAVAILABLE"):
        dpapi("not-bytes")


# ---- third review: the bootstrap imports themselves ------------------------------------------------
# Before this repair every entrypoint did sys.path.insert(0, source_root) and imported runtime_identity
# (and the launcher) through Python's normal PathFinder, before any pin existed. A root-level module
# shadowed any later stdlib/third-party import (proved: a planted psutil.py ran inside the launcher AND
# the running server, which still reported STARTED), and a package directory or extension module
# named like a bootstrap module ran before validation.

ENTRYPOINTS = ("scripts/uri_server_launcher.py", "scripts/run_uri_isolated_server.py",
               "scripts/uri_client_launcher.py", "scripts/run_uri_client_worker.py")


def _shadow(path, marker):
    path.write_text(f"open({str(marker)!r}, 'a').write('ran\\n')\nraise ImportError('planted')\n")
    return path


def test_root_level_modules_never_shadow_imports_of_any_entrypoint():
    marker = ROOT / "work/c1" / ("shadow_" + uuid.uuid4().hex)
    # Names each entrypoint imports from site-packages, before and after validation.
    planted = [_shadow(ROOT / (name + ".py"), marker) for name in ("psutil", "cryptography", "uvicorn", "pydantic")]
    try:
        for entry in ENTRYPOINTS:
            args = ["validate"] if "launcher" in entry else []
            r = subprocess.run([str(PYTHON), "-B", "-I", str(ROOT / entry), *args, "--manifest",
                                str(ROOT / "work/c1/missing" / uuid.uuid4().hex / "manifest.json")],
                               cwd=str(ROOT / "work/c1"), capture_output=True, text=True, timeout=120)
            assert r.returncode != 0, (entry, r.stdout, r.stderr)   # refused: no such manifest
            assert not marker.exists(), entry
    finally:
        for path in planted:
            path.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)


def test_root_level_shadow_never_runs_in_the_real_started_server():
    state = ROOT / "work/c1" / uuid.uuid4().hex
    manifest = RuntimeManifest(provision(ROOT, state, PYTHON, free_port(), composition=PAIRED_COMPOSITION))
    marker = ROOT / "work/c1" / ("shadow_" + uuid.uuid4().hex)
    planted = _shadow(ROOT / "psutil.py", marker)
    try:
        result = _start(manifest)
        assert result["result"] == "STARTED", result
        assert not marker.exists()
    finally:
        planted.unlink(missing_ok=True)
        _stop(manifest)
        marker.unlink(missing_ok=True)


def test_package_or_extension_named_like_a_bootstrap_module_never_runs():
    state = ROOT / "work/c1" / uuid.uuid4().hex
    manifest = RuntimeManifest(provision(ROOT, state, PYTHON, free_port(), composition=PAIRED_COMPOSITION))
    marker = ROOT / "work/c1" / ("shadow_" + uuid.uuid4().hex)
    package = ROOT / "uri_core/core/runtime_identity"
    package.mkdir()
    _shadow(package / "__init__.py", marker)
    try:
        result = _start(manifest)
        assert result["result"] != "STARTED", result   # C1_SOURCE_AMBIGUOUS: the launcher never starts
        assert listener(manifest.data["port"]) is None
        assert not marker.exists()
    finally:
        (package / "__init__.py").unlink()
        package.rmdir()
    # A (junk) extension module next to runtime_identity.py is never loaded: the source is.
    import importlib.machinery
    extension = ROOT / ("uri_core/core/runtime_identity" + importlib.machinery.EXTENSION_SUFFIXES[0])
    extension.write_bytes(b"MZ not a real module")
    try:
        result = _start(manifest)
        assert result["result"] == "STARTED", result
    finally:
        extension.unlink(missing_ok=True)
        _stop(manifest)
        marker.unlink(missing_ok=True)


def test_pin_requires_the_bootstrap_and_the_digest_of_what_actually_ran():
    # A process that imported Core the ordinary way has no record of the bytes it executed.
    r = run_isolated(textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from uri_core.core.runtime_identity import install_source_pin, source_files
        from pathlib import Path
        try:
            install_source_pin(Path({str(ROOT)!r}), source_files(Path({str(ROOT)!r})))
        except Exception as exc:
            print(exc)
    """))
    assert r.stdout.strip() == "C1_BOOTSTRAP_UNPINNED", r.stderr
    # With the bootstrap, a module whose file changed after it was compiled is refused at pin time
    # (the executed digest, not a re-read of the file, is compared).
    r = run_isolated(PRELUDE + textwrap.dedent("""
        import uri_core.reference_binding.facts as facts
        facts.__spec__.loader.executed_digest = "0" * 64
        try:
            install_source_pin(root, files)
        except Exception as exc:
            print(exc)
    """))
    assert r.stdout.strip() == "SOURCE_MODULE_UNPINNED", r.stderr


# ---- fourth review: the gate must not depend on the caller remembering -I ---------------------------------
def test_entrypoints_refuse_without_isolated_mode_before_importing_anything():
    """Without -I the script directory is sys.path[0]; a module planted there (not a pinned file) ran inside
    the real entrypoint before any validation. The bootstrap now refuses unless the interpreter is isolated.

    Fifth review: the gate must come before EVERY import, including the entrypoint's own stdlib imports
    (argparse), the bootstrap's own import (hashlib) and a sourceless bytecode module (secrets.pyc): each of
    these ran before the fourth-review gate, which lived behind them."""
    marker = ROOT / "work/c1" / ("flags_" + uuid.uuid4().hex)
    planted = [_shadow(ROOT / "scripts/psutil.py", marker), _shadow(ROOT / "scripts/argparse.py", marker),
               _shadow(ROOT / "scripts/hashlib.py", marker)]
    code = compile(f"open({str(marker)!r}, 'a').write('ran\\n')\nraise ImportError('planted')\n", "secrets.py", "exec")
    sourceless = ROOT / "scripts/secrets.pyc"
    sourceless.write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12 + marshal.dumps(code))
    planted.append(sourceless)
    try:
        for entry in ENTRYPOINTS:
            args = ["validate"] if "launcher" in entry else []
            r = subprocess.run([str(PYTHON), "-B", str(ROOT / entry), *args, "--manifest",
                                str(ROOT / "work/c1/missing" / uuid.uuid4().hex / "manifest.json")],
                               cwd=str(ROOT / "work/c1"), capture_output=True, text=True, timeout=120)
            assert r.returncode != 0 and "C1_ISOLATED_MODE_REQUIRED" in r.stderr, (entry, r.stdout, r.stderr)
            assert not marker.exists(), entry
    finally:
        for path in planted:
            path.unlink(missing_ok=True)
        marker.unlink(missing_ok=True)
