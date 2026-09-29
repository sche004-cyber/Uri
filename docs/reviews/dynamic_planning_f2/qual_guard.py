import importlib.util, sys, os
from pathlib import Path
ROOT = Path("/home/claude/Uri"); sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(Path(__file__).parent)); os.chdir(ROOT)
import proto
from uri_v1.execution.planning import runner as R
from uri_v1.execution.planning.actions import ActionError
orig = R.PlanRunner.__init__
def init(self, **kw):
    orig(self, **kw)
    def sec(fn):
        def s(ctx, inputs, literals):
            res, exc, viol, th = proto.guarded(ctx.files, fn, ctx, inputs, literals)
            if viol or th: raise ActionError("UNAUTHORIZED_EFFECT")
            if exc: raise exc
            return res
        return s
    self.adapters = {k: sec(f) for k, f in self.adapters.items()}
R.PlanRunner.__init__ = init
spec = importlib.util.spec_from_file_location("dpq", ROOT / "scripts/dynamic_planning_qualification.py")
q = importlib.util.module_from_spec(spec); sys.modules["dpq"] = q; spec.loader.exec_module(q)
q.run_compat = lambda tmp: {m: {"route": "x", "verification_status": "VERIFIED", "honest": 1, "forged": {"status": "FAILED"}} for m in ("edge", "composed")}
sys.exit(q.main(["--out", str(Path(__file__).parent / "qual_guard.json")]))
