"""Office sheet page: build-hash refusal (staging), page unit tests, and the AC15 page-layer probe in a real engine."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from uri_office import page_build as PB

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "uri_ui" / "office_web"
EDGE = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft" / "Edge" / "Application" / "msedge.exe"


# ---- staging refuses any bundle but the recorded one (runs everywhere, no npm) ------------------------------------
@pytest.fixture
def fake_bundle(tmp_path, monkeypatch):
    out = tmp_path / "office"
    (out / "assets").mkdir(parents=True)
    (out / "index.html").write_text("<html></html>")
    (out / "assets" / "index-x.js").write_text("console.log(1)")
    expected = tmp_path / "BUNDLE_SHA256"
    monkeypatch.setattr(PB, "EXPECTED", expected)
    return out, expected


def test_matching_bundle_is_accepted(fake_bundle):
    out, expected = fake_bundle
    expected.write_text(PB.bundle_hash(out) + "\n")
    assert PB.verify(out) == PB.bundle_hash(out)


@pytest.mark.parametrize("change", ["edit", "extra", "remove", "rename"])
def test_any_change_is_refused(fake_bundle, change):
    out, expected = fake_bundle
    expected.write_text(PB.bundle_hash(out))
    js = out / "assets" / "index-x.js"
    if change == "edit":
        js.write_text("console.log(2)")
    elif change == "extra":
        (out / "assets" / "evil.js").write_text("fetch('https://x')")
    elif change == "remove":
        js.unlink()
    else:
        js.rename(out / "assets" / "index-y.js")
    with pytest.raises(PB.BundleRefused, match="does not match"):
        PB.verify(out)


@pytest.mark.parametrize("recorded", [None, "", "abc", "Z" * 64])
def test_missing_or_malformed_record_is_refused(fake_bundle, recorded):
    out, expected = fake_bundle
    if recorded is not None:
        expected.write_text(recorded)
    with pytest.raises(PB.BundleRefused):
        PB.verify(out)


def test_missing_or_empty_bundle_is_refused(tmp_path):
    with pytest.raises(PB.BundleRefused):
        PB.bundle_hash(tmp_path / "nothing")
    (tmp_path / "empty").mkdir()
    with pytest.raises(PB.BundleRefused):
        PB.bundle_hash(tmp_path / "empty")


def test_recorded_hash_is_committed_and_well_formed():
    value = PB.expected_hash()
    assert len(value) == 64


def test_cli_exits_2_on_refusal(fake_bundle, monkeypatch):
    out, expected = fake_bundle
    monkeypatch.setattr(PB, "OUT", out)
    expected.write_text("0" * 64)
    assert PB.main(["verify"]) == 2
    expected.write_text(PB.bundle_hash(out))
    assert PB.main(["verify"]) == 0


def test_install_copies_and_verifies(fake_bundle, monkeypatch, tmp_path):
    out, expected = fake_bundle
    monkeypatch.setattr(PB, "OUT", out)
    expected.write_text(PB.bundle_hash(out))
    app = tmp_path / "app"
    (app / "data" / "office_page").mkdir(parents=True)
    (app / "data" / "office_page" / "stale.js").write_text("old")
    assert PB.install(app) == PB.bundle_hash(out)
    assert not (app / "data" / "office_page" / "stale.js").exists()
    assert PB.bundle_hash(app / "data" / "office_page") == PB.bundle_hash(out)


def test_install_refuses_unverified_bundle_or_non_app_folder(fake_bundle, monkeypatch, tmp_path):
    out, expected = fake_bundle
    monkeypatch.setattr(PB, "OUT", out)
    expected.write_text("0" * 64)
    (tmp_path / "app" / "data").mkdir(parents=True)
    with pytest.raises(PB.BundleRefused):
        PB.install(tmp_path / "app")
    assert not (tmp_path / "app" / "data" / "office_page").exists()
    expected.write_text(PB.bundle_hash(out))
    with pytest.raises(PB.BundleRefused, match="not a built URI app"):
        PB.install(tmp_path / "nothing")


# ---- page unit tests (node) ----------------------------------------------------------------------------------------
def test_page_unit_tests_pass():
    node = shutil.which("node")
    assert node, "node is required to test the Office page"
    r = subprocess.run([node, "--test", "--test-reporter=tap", "test/convert.test.mjs"], cwd=WEB, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout or "fail 0" in r.stdout


def test_page_guard_unit_tests_pass():
    """Network formula functions stay blocked after workbooks load (R1-01); structural grid edits are refused (R1-11)."""
    node = shutil.which("node")
    assert node, "node is required to test the Office page"
    r = subprocess.run([node, "--test", "--test-reporter=tap", "test/guard.test.mjs"], cwd=WEB, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout


@pytest.mark.skipif(not (WEB / "node_modules" / "@univerjs" / "sheets").is_dir(),
                    reason="needs `npm ci` in uri_ui/office_web (staging build); runs against the real Univer engine")
def test_page_guards_hold_in_the_real_univer_engine():
    r = subprocess.run([shutil.which("node"), "--test", "--test-reporter=tap", "test/guard.univer.test.mjs"], cwd=WEB, capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout


@pytest.mark.skipif(not (WEB / "node_modules" / "@univerjs" / "sheets-formula").is_dir(),
                    reason="needs `npm ci` in uri_ui/office_web (staging build); runs against the real Univer engine")
def test_shared_formula_edits_are_formulas_in_the_real_univer_engine():
    """Formula fill / insert-function cells carrying only a shared-formula id are sent as formulas, not clears (R2-01)."""
    r = subprocess.run([shutil.which("node"), "--test", "--test-reporter=tap", "test/edits.univer.test.mjs"], cwd=WEB, capture_output=True,
                       text=True, timeout=180)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "# fail 0" in r.stdout


# ---- AC15 page layers in a real Chromium engine (Windows-qualified: needs Microsoft Edge) -------------------------
@pytest.mark.skipif(os.name != "nt", reason="Windows-qualified only: needs Microsoft Edge (the panel runs on Windows)")
def test_page_blocks_every_network_attempt_in_edge(tmp_path):
    assert EDGE.is_file(), f"Microsoft Edge not found at {EDGE}"
    PB.verify()                     # the probe must run against the recorded bundle, not an arbitrary build
    out = tmp_path / "probe.json"
    r = subprocess.run([shutil.which("node"), "test/edge_probe.mjs", str(PB.OUT), str(EDGE), str(out)], cwd=WEB,
                       capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    rep = json.loads(out.read_text())
    ready = json.loads(rep["full"]["page_loaded_and_patched"])
    assert ready["canvas"] and ready["patched"] and ready["only_ready_sent"], ready
    assert ready["blocked_functions_present"] == [], ready
    for variant in ("full", "csp_only"):
        res = rep[variant]["results"]
        leaked = [k for k, v in res.items() if k != "navigation" and not v["blocked"]]
        assert leaked == [], (variant, leaked, {k: res[k]["canary_hits"] for k in leaked})
    # Top-level navigation is not a page-layer concern: the WebView2 host must cancel it (AC15 host layer).
    assert rep["full"]["results"]["navigation"]["blocked"] is False
