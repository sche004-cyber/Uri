"""Live demonstration of uri-development-lifecycle with real, separate Claude processes (TEST ONLY).

DEVTEST fixture: a tiny repository whose candidate has a deliberate defect (safe_div divides by zero), a protected
``core/`` path, a pytest gate and a local bare "canonical" remote. Reviewer and implementer are separate
``claude -p`` processes (provider ``claude_cli``); nothing is scripted on their side.

    python -m scripts.dev_workflow.lifecycle_demo <out_dir> [--model claude-opus-5-5]

Phases: (1) run with integration NOT authorised -> must stop BLOCKED (owner-only) after an independent
REJECT -> repair -> independent ACCEPT -> gates; (2) a missing reviewer binary must not ACCEPT;
(3) owner authorises -> unblock -> run integrates (fast-forward) -> COMPLETE; (4) verify the receipt chain.
Writes ``<out_dir>/demo_summary.json``.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scripts.dev_workflow import lifecycle as L
from tests.dev_workflow.test_lifecycle import g, make_fixture


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--model", default="claude-opus-5-5")
    a = ap.parse_args(argv)
    out = Path(a.out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    repo, wt, base, remote = make_fixture(out)
    worker = {"provider": "claude_cli", "model": a.model, "timeout_s": 2400}
    cfg = {
        "milestone": "DEVTEST-LIFECYCLE-LIVE", "repo": str(repo),
        "baseline": {"ref": "origin/canon", "expect": base},
        "candidate": {"branch": "feature", "worktree": str(wt)},
        "state_dir": str(out / "state"), "work_dir": str(out / "work"),
        "acceptance_criteria": ["pkg.calc.safe_div(a, b) returns a / b, and returns None when b == 0 (never raises)",
                                "pkg.feature.feature() returns 1",
                                "core/ is frozen: no change under core/",
                                "every behaviour has a pytest test under tests/"],
        "review_focus": ["correctness of pkg/calc.py against the criteria", "test coverage of the criteria"],
        "protected_paths": ["core/"], "permitted_paths": ["pkg/**", "tests/**"],
        "reviewer": dict(worker), "implementer": dict(worker),
        "regression_runner": ["{python}", "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        "gates": [{"id": "unit", "kind": "pytest", "cmd": ["{python}", "-m", "pytest", "-q", "tests"]}],
        "integration": {"mode": "fast-forward", "remote": "origin", "target_ref": "canon", "authorized": False},
        "commit_trailers": ["Lifecycle-Demo: DEVTEST, not a URI milestone"],
    }
    cpath = out / "lifecycle.json"
    summary = {"fixture": {"repo": str(repo), "baseline": base, "remote": str(remote)}}

    def save(c):
        cpath.write_text(json.dumps(c, indent=1))
        return L.load_config(cpath)

    stage = L.run(save(cfg))
    summary["phase1"] = {"stage": stage.value, "status": L.status(L.load_config(cpath)),
                         "remote_tip": g(remote, "rev-parse", "refs/heads/canon")}
    missing = dict(cfg, milestone="DEVTEST-LIFECYCLE-NOREVIEWER", state_dir=str(out / "state_noreviewer"),
                   reviewer={"provider": "claude_cli", "binary": str(out / "no-such-claude")})
    mpath = out / "noreviewer.json"
    mpath.write_text(json.dumps(missing, indent=1))
    ms = L.run(L.load_config(mpath))
    summary["phase2_missing_reviewer"] = {"stage": ms.value, "status": L.status(L.load_config(mpath))}
    if stage == L.S.BLOCKED and L.status(L.load_config(cpath))["blocker"]["kind"] == "OWNER_AUTHORIZATION":
        cfg["integration"]["authorized"] = True
        c = save(cfg)
        L.unblock(c, "DEVTEST owner simulation: integration into the fixture's canon authorised")
        stage = L.run(c)
    c = L.load_config(cpath)
    summary["phase3"] = {"stage": stage.value, "status": L.status(c),
                         "remote_tip": g(remote, "rev-parse", "refs/heads/canon"),
                         "core_unchanged": (Path(wt) / "core/frozen.py").read_text() == "FROZEN = True\n"}
    summary["phase4_verify_errors"] = L.verify(c)
    L.write_receipt(c, L.State(c))
    (out / "demo_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps({"phase1": summary["phase1"]["stage"], "phase2": ms.value, "phase3": stage.value,
                      "verify": summary["phase4_verify_errors"]}))
    return 0 if stage == L.S.COMPLETE and ms == L.S.WAITING_FOR_MODEL and not summary["phase4_verify_errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
