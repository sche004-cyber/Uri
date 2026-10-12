"""GRAPHIFY-LEAK-1 tests import uri_core.app.server, which imports the Google client libraries at module level. Where
those packages are not installed (some test hosts), import-only placeholders stand in for them; the Graphify path
under test never calls them. Installed packages are never replaced. The placeholders exist only while server.py is
imported here and are removed from sys.modules afterwards, so no other test in the same run can see them. A throwaway
credential secret is set only if none is present."""
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from unittest import mock

_ROOTS = tuple(root for root in ("google", "googleapiclient", "google_auth_oauthlib", "google_auth_httplib2")
               if root not in sys.modules and importlib.util.find_spec(root) is None)


class _ImportOnlyPlaceholder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in _ROOTS:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None

    def create_module(self, spec):
        module = mock.MagicMock(name=spec.name)
        module.__path__ = []
        module.__spec__ = spec
        module.__name__ = spec.name
        return module

    def exec_module(self, module):
        pass


os.environ.setdefault("URI_EXTERNAL_CREDENTIAL_SECRET", "graphify-leak-1-test-only")
if _ROOTS:
    _finder = _ImportOnlyPlaceholder()
    sys.meta_path.insert(0, _finder)
    try:
        import uri_core.app.server  # noqa: F401  (bound to the placeholders once, here)
    finally:
        sys.meta_path.remove(_finder)
        for _name in [n for n in sys.modules if n.split(".")[0] in _ROOTS]:
            del sys.modules[_name]
