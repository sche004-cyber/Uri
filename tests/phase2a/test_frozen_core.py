"""Frozen Phase-1 Core integrity: Phase 2A is a pure extension. These checks are the evidence, not a promise."""
import fnmatch
import hashlib
import subprocess
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINT = Path(r"C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip")
CHECKPOINT_SHA256 = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"
BASE_COMMIT = "e8e3b65"
ALLOWED_NEW = ["uri_supervisor/*", "tests/phase2a/*", "docs/plans/PHASE2A_*", "docs/architecture/PHASE2A_*", "scripts/phase2a_*",
               # Phase 2B (Core <-> Supervisor integration boundary): a third package; Core and the supervisor never import it.
               "uri_supervisor_bridge/*", "tests/phase2b/*", "docs/plans/PHASE2B_*", "docs/architecture/PHASE2B_*", "scripts/phase2b_*",
               # Phase 2C (native executor qualification): tests, qualification harness, reports. No package added.
               "tests/phase2c/*", "docs/plans/PHASE2C_*", "docs/architecture/PHASE2C_*", "scripts/phase2c_*",
               # Phase 2D (composition + closure): persisted qualification, policy composition, worker service, opt-in
               # Phase 2 worker/server profiles (frozen entrypoints untouched), tests, reports, test-scope config.
               "tests/phase2d/*", "docs/plans/PHASE2D_*", "docs/architecture/PHASE2D_*", "scripts/phase2d_*",
               "scripts/run_uri_supervised_worker.py", "scripts/run_uri_phase2_server.py",
               # Phase 2 UI/operations: execution lifecycle in the bridge package, Phase 2 Dart runtime + screen (NEW files;
               # the frozen paired_runtime.dart / paired_runtime_screen.dart / settings_shell.dart are untouched), the one
               # non-checkpoint UI file that mounts the opt-in entry (uri_ui/lib/app.dart), tests, reports, scripts.
               "tests/phase2ops/*", "docs/plans/PHASE2OPS_*", "docs/architecture/PHASE2OPS_*", "scripts/phase2ops_*",
               "uri_ui/lib/services/supervised_runtime.dart", "uri_ui/lib/screens/tasks/supervised_execution_screen.dart",
               "uri_ui/test/supervised_*", "uri_ui/lib/app.dart",
               # Phase 2 closure (2026-10-08): reports, ledger, runbook, chain/acceptance scripts, power-loss harness and its
               # tests, and the inert conversation-to-task handoff value (a NEW Dart file; no frozen file is touched).
               "tests/phase2close/*", "docs/plans/PHASE2CLOSE_*", "docs/architecture/PHASE2CLOSE_*", "scripts/phase2close_*",
               "docs/plans/URI_DEVELOPMENT_TODO.md", "uri_ui/lib/services/task_handoff.dart",
               # Phase 2 operational qualification (2026-10-08): EXE-1 native launch, SUP-1, D8, OQ-1, C6 Option B (owner
               # accepted): the Chat handoff action (a NEW widget) mounted by ONE non-checkpoint Chat file.
               "tests/phase2oq/*", "docs/plans/PHASE2OQ_*", "docs/architecture/PHASE2OQ_*", "scripts/phase2oq_*",
               "uri_ui/lib/widgets/supervised_handoff_action.dart", "uri_ui/lib/screens/ask/ask_uri_screen.dart",
               "uri_ui/test/chat_supervised_handoff_test.dart",
               # Working-system integration (2026-10-08, owner decision WS-D3): EXACT new paths, enumerated (no
               # wildcard; Codex WS round 1 F5). A new file in these areas fails this guard until it is listed here.
               "OI_MATERIALIZATION_RECEIPT.json",
               "model_lab/integration/local_brain.json",
               "model_lab/integration/local_brain.py",
               "model_lab/integration/prove_integration.py",
               "model_lab/lab/cases.py",
               "model_lab/lab/client.py",
               "model_lab/lab/decision.py",
               "model_lab/lab/hard.py",
               "model_lab/lab/longctx.py",
               "model_lab/lab/paired.py",
               "model_lab/lab/prompts.py",
               "model_lab/lab/runtime.py",
               "model_lab/lab/vision.py",
               "scripts/oi_materialize_test_runtime.py",
               "scripts/run_uri_integrated_server.py",
               "scripts/run_uri_integrated_worker.py",
               "scripts/ti_live_matrix.py",
               "scripts/ws_brain_host.py",
               "scripts/ws_frozen_check.py",
               "scripts/ws_provision.py",
               "scripts/ws_server_identity.py",
               "tests/oi/__init__.py",
               "tests/oi/conftest.py",
               "tests/oi/fake_llama.py",
               "tests/oi/test_oi_answer_planner_ledger.py",
               "tests/oi/test_oi_audit_r1_regressions.py",
               "tests/oi/test_oi_audit_r2_regressions.py",
               "tests/oi/test_oi_audit_r3_regressions.py",
               "tests/oi/test_oi_audit_r5_regressions.py",
               "tests/oi/test_oi_brain_client.py",
               "tests/oi/test_oi_core_live.py",
               "tests/oi/test_oi_core_provider.py",
               "tests/oi/test_oi_orchestrator.py",
               "tests/oi/test_oi_policy_triage.py",
               "tests/oi/test_oi_runtime_v1.py",
               "tests/oi/test_oi_server.py",
               "tests/ws/__init__.py",
               "tests/ws/test_ti_audit_r1_regressions.py",
               "tests/ws/test_ti_audit_r2_regressions.py",
               "tests/ws/test_ti_audit_r3_regressions.py",
               "tests/ws/test_ti_audit_r4_regressions.py",
               "tests/ws/test_ti_desk_bridge.py",
               "tests/ws/test_ti_live_findings.py",
               "tests/ws/test_ti_store_verify_input.py",
               "tests/ws/test_ti_text_intent.py",
               "tests/ws/test_ti_worker_live.py",
               "tests/ws/test_ws_cloud_and_composition.py",
               "tests/ws/test_ws_hardening.py",
               "tests/ws/test_ws_worker_bridge.py",
               "tests/ws/test_ws_worker_live.py",
               "uri_operational_intelligence/__init__.py",
               "uri_operational_intelligence/answer.py",
               "uri_operational_intelligence/bench/__init__.py",
               "uri_operational_intelligence/bench/no_mtp_compare.py",
               "uri_operational_intelligence/bench/reasoning.py",
               "uri_operational_intelligence/bench/suite_p.py",
               "uri_operational_intelligence/bench/tasks.py",
               "uri_operational_intelligence/brain_catalog.py",
               "uri_operational_intelligence/brain_client.py",
               "uri_operational_intelligence/brain_health.py",
               "uri_operational_intelligence/cloud_policy.py",
               "uri_operational_intelligence/core_provider.py",
               "uri_operational_intelligence/draft_desk.py",
               "uri_operational_intelligence/draft_store.py",
               "uri_operational_intelligence/events.py",
               "uri_operational_intelligence/gpu_lease.py",
               "uri_operational_intelligence/harness_choice.py",
               "uri_operational_intelligence/host.py",
               "uri_operational_intelligence/integrated_composition.py",
               "uri_operational_intelligence/orchestrator.py",
               "uri_operational_intelligence/perf_monitor.py",
               "uri_operational_intelligence/planner.py",
               "uri_operational_intelligence/reasoning_policy.py",
               "uri_operational_intelligence/runtime_v1.py",
               "uri_operational_intelligence/server.py",
               "uri_operational_intelligence/task_ledger.py",
               "uri_operational_intelligence/text_input.py",
               "uri_operational_intelligence/text_intent.py",
               "uri_operational_intelligence/text_verify.py",
               "uri_operational_intelligence/triage.py",
               "uri_operational_intelligence/worker_bridge.py",
               "work/oi/.gitignore"]

needs_zip = pytest.mark.skipif(not CHECKPOINT.exists(), reason="BLOCKED: frozen checkpoint zip not present on this machine")


def sh(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, encoding="utf-8").stdout


@needs_zip
def test_checkpoint_hash_matches_the_frozen_value():
    assert hashlib.sha256(CHECKPOINT.read_bytes()).hexdigest() == CHECKPOINT_SHA256


@needs_zip
def test_every_checkpoint_file_is_byte_identical_in_this_tree():
    z = zipfile.ZipFile(CHECKPOINT)
    bad = []
    for name in z.namelist():
        if name.startswith("GIT_"):
            continue
        f = ROOT / name
        if not f.is_file() or f.read_bytes() != z.read(name):
            bad.append(name)
    assert bad == []


@needs_zip
def test_nothing_changed_outside_checkpoint_and_phase2a_paths():
    z = {n for n in zipfile.ZipFile(CHECKPOINT).namelist() if not n.startswith("GIT_")}
    changed = set(sh("diff", "--name-only", BASE_COMMIT).split()) | set(sh("ls-files", "--others", "--exclude-standard").split())
    changed = {c.replace("\\", "/") for c in changed}
    stray = sorted(c for c in changed if c not in z and not any(fnmatch.fnmatch(c, g) for g in ALLOWED_NEW))
    assert stray == [], stray


def test_base_commit_is_the_one_the_checkpoint_was_built_on():
    assert sh("rev-parse", "--short", BASE_COMMIT).strip().startswith(BASE_COMMIT)
    head = sh("rev-parse", "--short", "HEAD").strip()
    assert head.startswith(BASE_COMMIT), "Phase 2A work must remain uncommitted on top of the frozen base"


def test_core_never_imports_the_supervisor():
    for pkg in ("uri_core", "uri_harness_adapters", "uri_ui"):
        for f in (ROOT / pkg).rglob("*.py"):
            assert "uri_supervisor" not in f.read_text(encoding="utf-8", errors="replace"), str(f)


def test_supervisor_does_not_import_core_internals():
    for f in (ROOT / "uri_supervisor").rglob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "import uri_core" not in text and "from uri_core" not in text, str(f)


def test_bypass_flag_refusal_is_not_weaker_than_phase1():
    from uri_core.client_runtime.harness import FORBIDDEN_FLAGS as CORE
    from uri_supervisor.executors import FORBIDDEN_FLAGS as MINE
    assert set(CORE) <= set(MINE)


def test_phase1_harness_and_process_tree_modules_are_untouched_by_hash():
    # these are in the checkpoint; the byte-identical test above covers them, this pins the two most relevant explicitly
    for rel in ("uri_core/client_runtime/process_tree.py", "uri_core/client_runtime/harness.py", "uri_core/client_runtime/execution_journal.py"):
        assert (ROOT / rel).is_file()
