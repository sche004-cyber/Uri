"""GRAPHIFY-LEAK-1 tests import uri_core.app.server, which imports the Google client libraries at module level. Where
those packages are not installed (some test hosts), import-only placeholders stand in for them; the Graphify path
under test never calls them. Installed packages are never replaced.

The placeholders exist only while a test module here runs (the `graphify_server` fixture, module scope), never at
collection. On teardown every module imported during that window that is a placeholder, part of uri_core (server and
what it pulled in) or bound a placeholder is removed from sys.modules and from its parent package, so later tests in
the same run import them afresh and never see a placeholder. A throwaway credential secret is set for the same window only, if none is present.
"""
import importlib
import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys
from unittest import mock

import pytest

_ROOTS = ("google", "googleapiclient", "google_auth_oauthlib", "google_auth_httplib2")


class _ImportOnlyPlaceholder(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def __init__(self, roots):
        self.roots = roots

    def find_spec(self, name, path, target=None):
        if name.split(".")[0] in self.roots:
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


def _bound_to_a_placeholder(module):
    if module is None or isinstance(module, mock.MagicMock):
        return True
    return any(isinstance(value, mock.MagicMock) for value in list(vars(module).values()))


def _forget_modules_added_since(before, roots):
    """Removes the placeholders, every uri_core module, and any other module that bound a placeholder, all only if
    imported during the window. Other third-party modules imported meanwhile are real and stay."""
    added = [n for n in sys.modules if n not in before]
    doomed = [n for n in added
              if n.split(".")[0] in roots + ("uri_core",) or _bound_to_a_placeholder(sys.modules.get(n))]
    for name in doomed:
        module = sys.modules.pop(name, None)
        parent_name, _, child = name.rpartition(".")
        parent = sys.modules.get(parent_name) if parent_name else None
        if parent is not None and getattr(parent, child, None) is module:
            try:
                delattr(parent, child)
            except AttributeError:
                pass


@pytest.fixture(scope="module")
def graphify_server():
    roots = tuple(root for root in _ROOTS if root not in sys.modules and importlib.util.find_spec(root) is None)
    with pytest.MonkeyPatch.context() as patch:
        if not os.environ.get("URI_EXTERNAL_CREDENTIAL_SECRET"):
            patch.setenv("URI_EXTERNAL_CREDENTIAL_SECRET", "graphify-leak-1-test-only")
        if not roots:
            yield importlib.import_module("uri_core.app.server")
            return
        before = set(sys.modules)
        finder = _ImportOnlyPlaceholder(roots)
        sys.meta_path.insert(0, finder)
        try:
            yield importlib.import_module("uri_core.app.server")
        finally:
            sys.meta_path.remove(finder)
            _forget_modules_added_since(before, roots)
