import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from uri_v1.turn.qwen_multi_feed_runtime import QwenMultiFeedRuntime
from uri_v1.turn.lfm_envelope_battery import build_operation_retention_battery

runtime = QwenMultiFeedRuntime()
cases = build_operation_retention_battery()
for c in cases:
    res = runtime.execute_mode_d(
        text=c.user_text,
        referring_expression=c.expected_reference_expression,
        candidate_pool=c.candidate_pool,
        turn_frame=c.turn_frame,
        active_context=c.active_context,
        run_parallel=True
    )
    req = [op.name for op in res.decoded_request.operations if op.status.value == "requested"]
    pro = [op.name for op in res.decoded_request.operations if op.status.value == "prohibited"]
    print(f"{c.case_id}: \"{c.user_text}\"")
    print(f"  Exp Req: {c.expected_requested_ops} | Act Req: {req}")
    print(f"  Exp Pro: {c.expected_prohibited_ops} | Act Pro: {pro}\n")
