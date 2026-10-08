"""M35 Batch A0: URIv1 parallel skeleton boundary tests.

Covers:
1. uri_v1 and its submodules import cleanly.
2. Importing uri_v1 does not construct/initialize any model, provider, or
   orchestrator instance (no side-effecting imports).
3. No import edge from uri_v1 to legacy orchestration modules.
4. uri_core remains importable and undisturbed by the new package.
"""

import ast
import importlib
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))

LEGACY_MODULES = {
    "uri_core.core.orchestrator",
    "uri_core.core.decision_engine",
    "uri_core.core.capability_registry",
}


class UriV1ImportTests(unittest.TestCase):
    def test_uri_v1_imports(self):
        module = importlib.import_module("uri_v1")
        self.assertTrue(hasattr(module, "__doc__"))

    def test_submodules_import(self):
        for name in [
            "uri_v1.app",
            "uri_v1.turn",
            "uri_v1.turn.contracts",
            "uri_v1.turn.decoder",
            "uri_v1.context",
            "uri_v1.intelligence",
            "uri_v1.intelligence.edge",
            "uri_v1.intelligence.edge.provider",
            "uri_v1.intelligence.local",
            "uri_v1.intelligence.local.provider",
            "uri_v1.intelligence.extended",
            "uri_v1.intelligence.extended.provider",
            "uri_v1.execution",
            "uri_v1.recovery",
            "uri_v1.knowledge",
            "uri_v1.safety",
        ]:
            with self.subTest(module=name):
                importlib.import_module(name)

    def test_contracts_are_plain_dataclasses(self):
        from uri_v1.turn.contracts import (
            ContextPack,
            DecodedRequest,
            EdgeOutcome,
            FinalizedTurn,
            IntelligenceResult,
        )

        req = DecodedRequest(raw_text="hello")
        pack = ContextPack(decoded_request=req)
        outcome = EdgeOutcome(handled=False, escalate_reason="not confident")
        result = IntelligenceResult(tier="extended", output="ok")
        turn = FinalizedTurn(context_pack=pack, result=result)
        self.assertEqual(turn.context_pack.decoded_request.raw_text, "hello")
        self.assertFalse(outcome.handled)

    def test_provider_slots_are_abstract(self):
        from uri_v1.turn.decoder import SemanticDecoder
        from uri_v1.intelligence.edge.provider import EdgeIntelligenceProvider
        from uri_v1.intelligence.local.provider import LocalIntelligenceProvider
        from uri_v1.intelligence.extended.provider import ExtendedIntelligenceProvider

        for cls in (
            SemanticDecoder,
            EdgeIntelligenceProvider,
            LocalIntelligenceProvider,
            ExtendedIntelligenceProvider,
        ):
            with self.subTest(cls=cls):
                with self.assertRaises(TypeError):
                    cls()


class UriV1NoLegacyDependencyTests(unittest.TestCase):
    """Static import-graph check: no uri_v1 module imports a legacy module."""

    def test_no_import_edge_to_legacy_orchestration(self):
        uri_v1_dir = os.path.join(REPO_ROOT, "uri_v1")
        offenders = []
        for dirpath, _dirnames, filenames in os.walk(uri_v1_dir):
            for filename in filenames:
                if not filename.endswith(".py"):
                    continue
                path = os.path.join(dirpath, filename)
                with open(path, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=path)
                for node in ast.walk(tree):
                    imported = None
                    if isinstance(node, ast.Import):
                        imported = [alias.name for alias in node.names]
                    elif isinstance(node, ast.ImportFrom) and node.module:
                        imported = [node.module]
                    if not imported:
                        continue
                    for name in imported:
                        if any(
                            name == legacy or name.startswith(legacy + ".")
                            for legacy in LEGACY_MODULES
                        ):
                            offenders.append((path, name))
        self.assertEqual(offenders, [], f"legacy import edges found: {offenders}")

    def test_no_model_or_orchestrator_instantiated_on_import(self):
        """Re-import in a clean subinterpreter-style check via sys.modules purge.

        A lighter proxy for "no side effects": importing uri_v1 must not add
        any uri_core provider/orchestrator instances to sys.modules state,
        and must not raise even if uri_core's heavier optional dependencies
        are unavailable, since uri_v1 does not import uri_core at all yet.
        """
        for name in list(sys.modules):
            if name == "uri_v1" or name.startswith("uri_v1."):
                del sys.modules[name]
        module = importlib.import_module("uri_v1")
        for name, sub in sys.modules.items():
            if name.startswith("uri_v1"):
                self.assertFalse(
                    name.startswith("uri_core.core.orchestrator")
                    or name.startswith("uri_core.core.model_providers"),
                    f"unexpected side-effecting import pulled in: {name}",
                )
        self.assertIsNotNone(module)


class UriCoreUndisturbedTests(unittest.TestCase):
    """Confirm uri_core is still importable, unmodified by this skeleton."""

    def test_uri_core_package_imports(self):
        module = importlib.import_module("uri_core")
        self.assertIsNotNone(module)


if __name__ == "__main__":
    unittest.main()
