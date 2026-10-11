# Placeholder modules for Google client libraries absent from this venv: server.py imports them at module level only;
# the Graphify/user-context path under test never calls them. Only missing top-level packages are stubbed.
import importlib.abc, importlib.machinery, importlib.util, sys, types
from unittest import mock
_STUB_ROOTS = ("google", "googleapiclient", "google_auth_oauthlib", "google_auth_httplib2")
class _Stub(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in _STUB_ROOTS:
            return importlib.machinery.ModuleSpec(name, self, is_package=True)
        return None
    def create_module(self, spec):
        m = mock.MagicMock(name=spec.name); m.__path__ = []; m.__spec__ = spec; m.__name__ = spec.name
        return m
    def exec_module(self, module):
        pass
for root in _STUB_ROOTS:
    if importlib.util.find_spec(root) is None if root not in sys.modules else False:
        pass
sys.meta_path.insert(0, _Stub())
