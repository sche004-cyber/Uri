import json
import time

from uri_supervisor.narration import narrate, format_claim


def test_read_task_completes_via_terminal_success(env):
    env.task("t1")
    a = env.sup.admit_next()
    assert a and a.task_id == "t1"
    r = env.run(a, "ok_read")
    assert env.state("t1") == "COMPLETE", (r, env.L.task("t1")["reason_code"])
    assert r.decision["outcome"] == "COMPLETE"


def test_local_write_complete_needs_uri_verification(env, tmp_path):
    target = tmp_path / "out dir" / "файл ✓.txt"
    target.parent.mkdir()
    env.task("t2", effects=[{"op_class": "local_write", "operation": "write", "target": str(target), "paths": [str(target)]}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(target)}}])
    a = env.sup.admit_next()
    r = env.run(a, "ok_write", path=str(target))
    assert env.state("t2") == "COMPLETE", (r.decision["reason_code"], env.L.task("t2")["reason_code"])
    print([format_claim(c) for c in narrate(env.L, "t2")])
