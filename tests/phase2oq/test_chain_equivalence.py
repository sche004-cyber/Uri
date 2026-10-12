"""OQ-R2-1: the Phase 1 equivalence gate must fail on any new failure, missing test or lost pass, even when another
test's change offsets the counts. Synthetic logs in the exact `-rfEsp` summary format."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("chain_oq", ROOT / "scripts" / "phase2close_chain.py")
ch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ch)

FAILS = ["FAILED a_test.py::test_f%d - boom" % i for i in range(11)]  # failed_ids() takes the ID before " - "
BASE_SKIPS = ["SKIPPED [12] live_test.py:10: Ollama service unavailable at http://127.0.0.1:11434: <urlopen error refused>"]


def log(tmp_path, name, passes, skips, fails=FAILS):
    lines = ["PASSED %s" % p for p in passes] + skips + fails
    lines.append("%d failed, %d passed, %d skipped in 1.0s" % (len(fails), len(passes),
                 sum(int(s.split("[")[1].split("]")[0]) for s in skips)))
    f = tmp_path / name
    f.write_text("\n".join(lines) + "\n")
    return f


def counts(f):
    return ch.pytest_counts(f)


def baseline(tmp_path):
    return log(tmp_path, "base.log", ["b_test.py::test_p%d" % i for i in range(2675)], BASE_SKIPS)


def test_identical_run_passes(tmp_path):
    b = baseline(tmp_path)
    ok, d = ch.phase1_equivalence(b, b, counts(b))
    assert ok, d


def test_a_live_test_moving_from_skip_to_named_pass_is_accepted(tmp_path):
    b = baseline(tmp_path)
    passes = ["b_test.py::test_p%d" % i for i in range(2675)] + ["live_test.py::test_live"]
    n = log(tmp_path, "now.log", passes, ["SKIPPED [11] live_test.py:10: Ollama service unavailable at http://127.0.0.1:9: <urlopen error x>"])
    ok, d = ch.phase1_equivalence(n, b, counts(n))
    assert ok, d


def test_a_lost_pass_offset_by_a_new_pass_is_refused(tmp_path):
    """The reviewer's case: one baseline test disappears (or stops passing) while a skipped one starts passing."""
    b = baseline(tmp_path)
    passes = ["b_test.py::test_p%d" % i for i in range(2674)] + ["other_test.py::test_new"]
    n = log(tmp_path, "now.log", passes, ["SKIPPED [12] live_test.py:10: Ollama service unavailable at http://x"])
    n2 = log(tmp_path, "now2.log", passes[:-1] + ["live_test.py::test_live"],
             ["SKIPPED [11] live_test.py:10: Ollama service unavailable at http://x",
              "SKIPPED [1] b_test.py:99: something else"])
    # Without a collection the counts alone cannot see the swap (the reviewer's point) ...
    ok, d = ch.phase1_equivalence(n, b, counts(n))
    assert ok
    # ... with the collection identity check it is refused.
    base_coll = ["b_test.py::test_p%d" % i for i in range(2675)] + ["live_test.py::t%d" % i for i in range(12)] + \
        ["a_test.py::test_f%d" % i for i in range(11)]
    now_coll = [t for t in base_coll if t != "b_test.py::test_p2674"] + ["other_test.py::test_new"]
    ok, d = ch.phase1_equivalence(n, b, counts(n), now_coll, base_coll)
    assert not ok and d["collection_missing"] == ["b_test.py::test_p2674"] and d["collection_added"] == ["other_test.py::test_new"]
    ok2, d2 = ch.phase1_equivalence(n2, b, counts(n2))
    assert not ok2 and d2["skips_not_in_baseline"]  # a baseline pass became a new kind of skip


def test_identical_collection_with_results_inside_it_passes(tmp_path):
    b = baseline(tmp_path)
    coll = ["b_test.py::test_p%d" % i for i in range(2675)] + ["live_test.py::t%d" % i for i in range(12)] + \
        ["a_test.py::test_f%d" % i for i in range(11)]
    ok, d = ch.phase1_equivalence(b, b, counts(b), coll, coll)
    assert ok, d


def test_a_new_failure_or_a_skip_moving_to_an_unnamed_pass_is_refused(tmp_path):
    b = baseline(tmp_path)
    n = log(tmp_path, "now.log", ["b_test.py::test_p%d" % i for i in range(2674)], BASE_SKIPS,
            FAILS + ["FAILED b_test.py::test_p2674 - new"])
    ok, d = ch.phase1_equivalence(n, b, counts(n))
    assert not ok and not d["SAME_FAILURE_SET"]
    passes = ["b_test.py::test_p%d" % i for i in range(2676)]      # the extra pass is not from the skipped file
    n2 = log(tmp_path, "now2.log", passes, ["SKIPPED [11] live_test.py:10: Ollama service unavailable at http://x"])
    ok2, d2 = ch.phase1_equivalence(n2, b, counts(n2))
    assert not ok2 and d2["gone_skips_without_named_pass"]


# ---- Review round 3 (OQ-R3-1, OQ-R3-2): per-test outcome identity and the accepted runner -----------------------------

def test_oq_r3_1_a_pass_skip_swap_is_refused():
    """The reviewer's counterexample: same IDs, same counts, same skip summary, but one test lost its pass and another
    gained one. Outcome identity per test ID refuses it."""
    base = {"live.py::test_pass": "passed", "live.py::test_s0": "skipped", "a.py::test_f": "failed"}
    now = {"live.py::test_pass": "skipped", "live.py::test_s0": "passed", "a.py::test_f": "failed"}
    ok, d = ch.outcome_identity(now, base)
    assert not ok and len(d["outcome_changed"]) == 2
    assert ch.outcome_identity(dict(base), base)[0]
    assert not ch.outcome_identity({**base, "new.py::t": "passed"}, base)[0]
    assert not ch.outcome_identity({k: v for k, v in base.items() if k != "a.py::test_f"}, base)[0]


def test_junit_outcomes_reads_every_outcome(tmp_path):
    x = tmp_path / "r.xml"
    x.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="f"><failure/></testcase>'
                 '<testcase classname="a" name="s"><skipped/></testcase><testcase classname="a" name="e"><error/></testcase>'
                 '</testsuite></testsuites>')
    assert ch.junit_outcomes(x) == {"a::p": "passed", "a::f": "failed", "a::s": "skipped", "a::e": "error"}


def test_oq_r3_2_the_runner_must_build_the_accepted_argv():
    """The Phase 1 runner is a Phase 1 input: its phase1-full argv must equal the accepted -f runner's plus exactly the
    tests/phase2oq ignore. A runner that selects anything else is detected."""
    accepted = ch.accepted_runner_source()
    current = (ROOT / "scripts" / "phase2d_regression.py").read_text(encoding="utf-8")
    assert ch.runner_argv(current) == ch.runner_argv(accepted) + [ch.OQ_EXTRA_IGNORE]
    tampered = current.replace('"--ignore=uri_ui", ', '"--ignore=uri_ui", "--ignore=test_c5_loop.py", ')
    assert tampered != current and ch.runner_argv(tampered) != ch.runner_argv(accepted) + [ch.OQ_EXTRA_IGNORE]


# ---- Review round 4 (OQ-R4-1): JUnit ids must be injective and complete ----------------------------------------------

def test_oq_r4_1_a_real_pytest_junit_collision_is_refused(tmp_path):
    """Two distinct test files whose JUnit classname::name collide (the reviewer's real-pytest case): the integrity check
    refuses the run, and the colliding id is never collapsed into one passed outcome."""
    import subprocess
    import sys
    for d in ("a.b", "a/b"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        (tmp_path / d / "test_same.py").write_text("def test_same():\n    assert True\n")
    xml = tmp_path / "r.xml"
    log = tmp_path / "r.log"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--import-mode=importlib",
                        "--rootdir", str(tmp_path), "--junitxml", str(xml), str(tmp_path)],
                       capture_output=True, text=True, cwd=str(tmp_path))
    log.write_text(r.stdout)
    integ = ch.junit_integrity(xml, ch.pytest_counts(log))
    assert integ["testcases"] == 2 and integ["unique_ids"] == 1 and not integ["ok"], (integ, r.stdout[-500:])
    assert list(ch.junit_outcomes(xml).values()) == ["conflict"]


def test_oq_r4_1_a_testcase_count_below_the_summary_is_refused(tmp_path):
    x = tmp_path / "r.xml"
    x.write_text('<testsuites><testsuite><testcase classname="a" name="p"/></testsuite></testsuites>')
    assert not ch.junit_integrity(x, {"passed": 2, "failed": 0, "skipped": 0, "errors": 0})["ok"]
    assert ch.junit_integrity(x, {"passed": 1, "failed": 0, "skipped": 0, "errors": 0})["ok"]


# ---- Review round 5 (OQ-R5-1, OQ-R5-2) ---------------------------------------------------------------------------------

def test_oq_r5_1_per_outcome_counts_must_agree(tmp_path):
    """The reviewer's probe: one pass + one skip in the XML, the summary claims two passes. Totals match; refused."""
    x = tmp_path / "r.xml"
    x.write_text('<testsuites><testsuite><testcase classname="a" name="p"/><testcase classname="a" name="s"><skipped/>'
                 '</testcase></testsuite></testsuites>')
    assert not ch.junit_integrity(x, {"passed": 2, "failed": 0, "skipped": 0, "errors": 0})["ok"]
    assert ch.junit_integrity(x, {"passed": 1, "failed": 0, "skipped": 1, "errors": 0})["ok"]


def test_oq_r5_2_the_stored_baseline_map_is_bound_to_its_xml():
    """The real stored baseline: its JSON outcome map equals what its own XML records (the gate rechecks this every
    run); a single changed outcome in the map would break the equality."""
    import json
    base = json.loads(ch.OUTCOME_BASELINE.read_text(encoding="utf-8"))["outcomes"]
    xml_map = ch.junit_outcomes(ch.ROOT.parent / "evidence" / "phase2oq" / "outcome_baseline" / "phase1_baseline.xml")
    assert xml_map == base
    some = next(iter(base))
    tampered = {**base, some: "skipped" if base[some] != "skipped" else "passed"}
    assert xml_map != tampered


# ---- Review round 6 (OQ-R6-1, OQ-R6-2) ---------------------------------------------------------------------------------

def test_oq_r6_2_baseline_files_are_pinned_and_a_joint_tamper_is_refused(tmp_path):
    """The real baseline matches the digests pinned in the gate script; the reviewer's joint XML+JSON alteration (copied
    into a scratch directory) does not."""
    import shutil
    ok, got = ch.baseline_pins_hold()
    assert ok, got
    src = ch.ROOT.parent / "evidence" / "phase2oq"
    (tmp_path / "outcome_baseline").mkdir()
    for rel in ch.BASELINE_PINS:
        shutil.copyfile(src / rel, tmp_path / rel)
    assert ch.baseline_pins_hold(tmp_path)[0]
    xml = tmp_path / "outcome_baseline" / "phase1_baseline.xml"
    xml.write_bytes(xml.read_bytes().replace(b"<skipped", b"<skipped ", 1))
    assert not ch.baseline_pins_hold(tmp_path)[0]


def test_oq_r6_1_only_the_expected_pytest_exit_is_accepted():
    """The gate source requires exit 1 (tests ran, the accepted failures failed); any other code fails the gate."""
    assert ch.PHASE1_EXPECTED_EXIT == 1
    src = (ch.ROOT / "scripts" / "phase2close_chain.py").read_text(encoding="utf-8")
    assert "code == PHASE1_EXPECTED_EXIT" in src

