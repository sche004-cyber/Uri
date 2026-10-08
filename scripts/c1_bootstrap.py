"""C1 bootstrap import gate. Loaded by exact path, before anything is imported from the source root.

The source root is never put on sys.path, so a module planted there cannot shadow a standard-library
or third-party module. Pinned packages resolve only through this finder, to plain source files under
the root: an extension module, sourceless or cached bytecode, or a name that is both a module file and
a package directory is never executed. Each loader records the SHA-256 of the exact bytes it compiled,
and install_source_pin later requires that digest to equal the manifest pin.
"""
import sys

# Fifth review: the gate must precede this module's own imports. Without -I the script directory is
# sys.path[0], so a module planted there (e.g. scripts/hashlib.py) would run before install() could refuse.
if not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")

import hashlib
import importlib.machinery
import importlib.util
import os

PINNED_PACKAGES = ("uri_core", "uri_harness_adapters", "scripts")


class SourceOnlyLoader(importlib.machinery.SourceFileLoader):
    """Compile the source bytes; never consult cached bytecode. Records what actually ran."""
    executed_digest = None

    def get_code(self, fullname):
        data = self.get_data(self.path)
        self.executed_digest = hashlib.sha256(data).hexdigest()
        return self.source_to_code(data, self.path)


class BootstrapFinder:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in PINNED_PACKAGES:
            return None
        base = os.path.join(self.root, *fullname.split("."))
        package, module = os.path.join(base, "__init__.py"), base + ".py"
        is_package, is_module = os.path.isfile(package), os.path.isfile(module)
        if is_package and is_module:
            raise ImportError("C1_SOURCE_AMBIGUOUS", name=fullname)
        if is_package or is_module:
            origin = package if is_package else module
            return importlib.util.spec_from_file_location(
                fullname, origin, loader=SourceOnlyLoader(fullname, origin),
                submodule_search_locations=[base] if is_package else None)
        if os.path.isdir(base):
            # Namespace package: the source-root portion only, never portions from other sys.path entries.
            spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [base]
            return spec
        raise ImportError("C1_SOURCE_NOT_FOUND", name=fullname)


def install(root):
    # The launched path is always `-I` (process_identity requires it). Without isolated mode the script
    # directory, PYTHONPATH and user site-packages are importable before any validation, so a module
    # planted there would run first. Refuse before the entrypoint's first import.
    if not sys.flags.isolated:
        raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
    root = os.path.abspath(root)
    sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.abspath(p or os.curdir)) != os.path.normcase(root)]
    sys.meta_path.insert(0, BootstrapFinder(root))
