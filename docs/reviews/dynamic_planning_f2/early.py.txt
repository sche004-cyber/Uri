# Patch the real function's code BEFORE the pin module captures it: M1's residual.
import sys, os, tempfile; sys.path.insert(0, "/home/claude/Uri"); sys.path.insert(0, os.path.dirname(__file__))
from uri_v1.execution.planning import actions
target = tempfile.mktemp()
src = open(actions.__file__).read()
ns = {}
code = compile("def inspect_structure(ctx, inputs, literals):\n    open(%r, 'w').write('x')\n    return {}\n" % target, actions.__file__, "exec")
exec(code, ns); actions.inspect_structure.__code__ = ns["inspect_structure"].__code__
import proto
key = (actions.INSPECT, "1")
print("M1 verdict on pre-capture code swap:", proto.pin_check(key, actions.inspect_structure) or "ACCEPTED")
res, exc, viol, th = proto.guarded(tempfile.mkdtemp(), actions.inspect_structure, None, {}, {})
print("M2 on same:", "violations" if viol else "none", "outside file exists:", os.path.exists(target))
