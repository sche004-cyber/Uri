"""Verify historical runtime output separately from the accepted source checker.

Owner authorization 2026-10-14 permits exactly the two canonical security blobs.
The receipt is descriptive, never authority: expected bytes come from pinned Git
objects and the clean, canonically descended source candidate. No Core edit or
checkpoint reset is performed by verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
if str(SOURCE) not in sys.path:
    sys.path.insert(0, str(SOURCE))
from scripts import ws_frozen_check as F

ACCEPTED_SOURCE = "e0b5c298d046622d52550f1455ab649070165602"
# Published canonical integration. A candidate that descends from canonical but not from the accepted
# Assist/Office line (FCV-20261014 recovery) is verified against canonical's own accepted bytes.
CANONICAL_SOURCE = "1b5423bc15fd7e5da9161c862cf839925da9f2eb"
# Only these inherited paths differ between canonical and ACCEPTED_SOURCE (Assist repair). On the
# canonical lineage they must hold canonical's exact bytes; None means the path is absent there.
CANONICAL_SCOPE_BLOBS = {
    "uri_assist/onscreen.py": "55d7e674e1f16bed2a8050bff15e81626db56ca1a9f70783f7ca03176a6dca17",
    "tests/assist/test_subpixel_render.py": None,
}
PATCH_PATH = "docs/governance/windows_restoration/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch"
AUTHORITY_PATH = "docs/governance/windows_restoration/OWNER_RUNTIME_AUTHORIZATION.json"
PATCH_SHA256 = "ba9249dad002e62c6cf1698284e8a2ada325d0afa1444579a371af7fa9caea02"
BEFORE = {
    "uri_core/app/server.py": "7b455f05ae97f7f6cbc944ba5c93998ea64063402568ea9750b70356db4f366b",
    "uri_core/tools/fetch_url.py": "f097006211c2b2c4abc9a4aaf7aa64063ee00a55030559caf857724ce2af9bff",
}


# Exact content of existing accepted e0 paths newly recognized by the historical scope gates.
INHERITED_SCOPE_BLOBS = {
    "tests/assist/fixtures/run_selection.cjs": "9dd01567e426ca908b181c983f1dfaf1f7329dfd09d52c06fd8d62b83601348c",
    "tests/assist/fixtures/selection_page.html": "bdbaa9da8e4994036e3fa0ff6c8605a65e325fe7e6b97826889b6f47bafa0173",
    "tests/assist/fixtures/text_surfaces.html": "60e850b265e59be30ba13bdfceefcc9bd406af848c88a28eece815545cefe7be",
    "tests/assist/test_a0_d10_pixel_checked_text.py": "031c2935fdabff686fed007658f2f0684fcb1d643feb43312cd9470eca46c91c",
    "tests/assist/test_a0_d8_fail_closed.py": "9573174122d7ec8bf172311f1fb16bd74168a529bcae6d4ab51536731b8da218",
    "tests/assist/test_a0_r10_review_regressions.py": "aab7d9f54fb7a27833d88cabcb7cef5a5fc4406a7b22e3a6ba2016fcd45c268c",
    "tests/assist/test_a0_r11_review_regressions.py": "0258dbceeef10e475f97854796056eacce0d88e8a8c0c2c82c35c80dd78e8d33",
    "tests/assist/test_a0_r12_review_regressions.py": "7abf7847efab81ea7e9dcc4784c730ba228c2e96d06e70fe351d93ca38dd56e5",
    "tests/assist/test_a0_r13_differential_render.py": "fd2ceddd5c04f834b7675bcd85b296ac2479b85a9abec98b6a9e0ca877957559",
    "tests/assist/test_a0_r14_review_regressions.py": "3d74465ff1af068a426e00d05ed3722128d201d785b6d9b175d28ca36f38c9fb",
    "tests/assist/test_a0_r15_review_regressions.py": "e2e64c1863235fbbd1a1ddc667278f04c46b87bdba3a404ead81a21fb3df81bb",
    "tests/assist/test_a0_r16_url_secret_regressions.py": "7fc7b1f293a40901135bff311d60213ab3375996a08c806b56fb105913689f52",
    "tests/assist/test_a0_r1_review_regressions.py": "d9517bb3e2741d5a3e43736cb8b1a534f5831afad4ea4463448a2af4ddab9509",
    "tests/assist/test_a0_r2_decoration_regressions.py": "133a5ecf0671fc61bdb8c0b506d11aabe6aaeaf6408e4b756271888c803ada30",
    "tests/assist/test_a0_r3_review_regressions.py": "331840b5e51079436a5c2827d8b85873cd566e53198da3ce185968e5412a98ed",
    "tests/assist/test_a0_r41_review_regressions.py": "c811ab56473f88e60de2a5a30003c67ed487037097ebd3f24e9ddf9a1efe776f",
    "tests/assist/test_a0_r42_review_regressions.py": "62eca7e324eb1c0c9d560f597be36a423fc184b881cb3e4323f451dbb0f6f7b8",
    "tests/assist/test_a0_r4_review_regressions.py": "464160d8322e373e29ce179d3c4f0d0cd00d3736331c645ee0d3e04a7769a5ac",
    "tests/assist/test_a0_r5_review_regressions.py": "ecf6f2056b0b3690d6c366d3083cdb78d573cd5596fb6c084c9243a470ca1a7a",
    "tests/assist/test_a0_r6_review_regressions.py": "6d308ce93a5fdcee6402833b4caeaddeb90024aa9598bb45f2d8d709503fc419",
    "tests/assist/test_a0_r9_review_regressions.py": "541c4aeb734b27b071ab5f9d28239f8ac71cf99e7adfb6b03c7101b2152add01",
    "tests/assist/test_subpixel_render.py": "b744485eab4aeec93ae40ab3a9b1b7c96f87ac6d0cc159cd076519e0cfa4b62b",
    "tests/web/d7_invariant.py": "9fe62d9ce183cb6dad8b1a643c53de5ea6f80144b87690a44d38e7f501c05ecb",
    "tests/web/test_idn_1.py": "936a6f57a31b992e6ab104ac2b5760cf811de9184250d401b2088f7f11ebe292",
    "tests/web/test_idn_1_r1.py": "6b9f76895b888f6f50a40ef89d76db7b66d49c1e62f29729fddd92556c947796",
    "tests/web/test_idn_1b.py": "dcb49e513bb352b4412071f0a19122eb7de2cbd3016fb986e1d0b23343e0a2e2",
    "tests/web/test_w1_closure_d15_review_regressions.py": "0dfc89ba84d2ee4e59b57fa64b2b96709ac25279cb0dfb35c1764ef5f6ca1b2d",
    "tests/web/test_w1_closure_d16_review_regressions.py": "640d15193e2bba7b2168be447570831fcbc2cd22d02eee67a7ba6ce589a26d72",
    "tests/web/test_w1_closure_d31_plain_writing.py": "7d125be0afa56a7955e036a5c349bf5a7606c41c0f6fe672c3eabe3bf2f17744",
    "tests/web/test_w1_closure_r11_review_regressions.py": "254229ce3a9e2db9b14df7e4a637a89650683af6044de9793da330e9872b155f",
    "tests/web/test_w1_closure_r12_review_regressions.py": "2d9c9779aef8099582c8fd21e78e4a6ebcc74a41b06dc418d8b2993f6769cb1e",
    "tests/web/test_w1_closure_r13_review_regressions.py": "3fd5046ab5f2f837571dfdf5bacc8557274ff6eab6c24fbbf9bc1be1e6c1bc32",
    "tests/web/test_w1_closure_r14_review_regressions.py": "79c21abc68a2bdbef919fc578bfbb7668a7c11e5a7d26d42b4e0b74426f79306",
    "tests/web/test_w1_closure_r16_review_regressions.py": "521061948763d6b20e04606dbd2249bbfb60b18a0f415047b18b2bf74481dc1e",
    "tests/web/test_w1_closure_r17_review_regressions.py": "e5eb532c4bbf3476487d7453fac18a4797f315d61e38020d29954e990befe1c9",
    "tests/web/test_w1_closure_r18_review_regressions.py": "50cdee2c7f43c90ee1f5f31cef52479edae15942f7eb84600a6b495af9a7cf80",
    "tests/web/test_w1_closure_r19_review_regressions.py": "65125030384264eded2ed042de51e54f7019168b26754d7556add51fbb448aed",
    "tests/web/test_w1_closure_r20_review_regressions.py": "fe268d99b696e746d14c5d3712909bec9d2a85aad25da9dc45010d7860ce9be6",
    "tests/web/test_w1_closure_r21_review_regressions.py": "1348b4852fb171fa3e58a636aa0ebc11eb0b1172decea5302cb723527f16095e",
    "tests/web/test_w1_closure_r22_review_regressions.py": "256679b3fc871756794c054e11c5208f57b1d376d8fdfa60f918b78b6bc51603",
    "tests/web/test_w1_closure_r23_review_regressions.py": "68a5381b89dbc7e086f759234f5a835bb5d92ef07c3f50f5bf6f2a6c1b07c49b",
    "tests/web/test_w1_closure_r24_review_regressions.py": "88090b45be54229658e8d52ef7cfacd7b3b866a7f1ceb813994adc425e9b7d86",
    "tests/web/test_w1_closure_r25_review_regressions.py": "733f6e30cbb699239224381d3b7c9b10d297096b20c00edc49ccaf67fad1a085",
    "tests/web/test_w1_closure_r26_review_regressions.py": "9eb110c8f39fcc84c70c96d46663380efdf208538299a88f0ec6d9af4e0253d0",
    "tests/web/test_w1_closure_r27_review_regressions.py": "2c7466adfd0dcc0932d0668d8020fcc030b56f5137f93ade81f7ccc7cbd252e6",
    "tests/web/test_w1_closure_r28_review_regressions.py": "db53c48f6c6f7a55623a0b6cb5cd165ff9162f18d0eaef3ead053b22561238e2",
    "tests/web/test_w1_closure_r29_review_regressions.py": "e44a0c8e486800a8af8913bcb5d7b4dcd702a582906f23f6a311849414a15813",
    "tests/web/test_w1_closure_r30_review_regressions.py": "bd8b880b66921181233f9cdfe622f517d1825a4be2ee0aaf6f8cac268f6a5ef5",
    "tests/web/test_w1_closure_r31_review_regressions.py": "a1134541caa778603a5946f394025f5d0a0787ae0df6847742d0912027f64e22",
    "tests/web/test_w1_closure_r32_review_regressions.py": "bce6909adb8c9b63adb9ac107745541e0bac540aff1bbec5d22fc2d08f5f79e5",
    "tests/web/test_w1_closure_r33_review_regressions.py": "26b56393c181272843fd1cd576118e18bbfa984285e9e50114a7dad09b4c47dd",
    "tests/web/test_w1_closure_r34_review_regressions.py": "db9acdc3205c7a9792caf180e7315ffed63003ce8003ef4cf3e43e322a773939",
    "tests/web/test_w1_closure_r35_review_regressions.py": "256a81be9ce4e5eae020895a108e710c2963e5a53d426d0810c15e5abf09fa82",
    "tests/web/test_w1_closure_r36_review_regressions.py": "aeb7e9ac542f51a035b2636545b49588c305cee910975fa6d0b4f59be1c3f30a",
    "tests/web/test_w1_closure_r37_review_regressions.py": "77fc1504b50fc0f356ee51a26ff146011676152fbe45b335e144197191ef6586",
    "tests/web/test_w1_closure_r38_review_regressions.py": "a6ebd71ff1d205f024d93a313f6603e583c4c14952bf73f6c7e44fb83b265811",
    "tests/web/test_w1_closure_r39_review_regressions.py": "5270411c8031874aa11055024dc13a0aa111863a71d7da227dd3384676970524",
    "tests/web/test_w1_closure_r40_review_regressions.py": "c51bc5a7595c838ee5125aa052f4a069b1d46f53a045b51c7c63d7060d918313",
    "tests/web/test_w1_closure_r41_review_regressions.py": "2930cfa38f5ce5ea0f6fcd539dace8df6729bf3f0432e9d99bfb454c213987c0",
    "tests/web/test_w1_closure_r43_review_regressions.py": "00413cfb9ac3310858af31b91672dc8c50ca875d8d4adf699c89402a8c581367",
    "tests/web/test_w1_closure_r4_review_regressions.py": "4662fb1ac5d6eb1f2f76cef01884c8eb59b07b49c9c3b5b449aef604fc3b0edb",
    "tests/web/test_w1_closure_r5_review_regressions.py": "9f799b93463faac1f0963e1d8b87f321122678b2b89f2deab9842dbec194d555",
    "tests/web/test_w1_closure_r6_review_regressions.py": "4bacb7d16fe83479cd3a84e7581187d2ece146e641a12a7ae76ef5a67712649b",
    "tests/web/test_w1_closure_r7_review_regressions.py": "5c0d3def6b11ab02751f56d5fbbee588a30a51f799c41ffcab11ae7c8aaed225",
    "tests/web/test_w1_closure_r8_review_regressions.py": "eeac0399af7ea2b5b6cc20dcbd3cfff769c79a6ed7fb59cbd3942bf701741574",
    "tests/web/test_w1_closure_r9_review_regressions.py": "c7d3485b387f2763f7fb7ecba0ecf241636a6d3ebb914eae86b7ee48f87d8a23",
    "tests/web/test_w1_d7_verbatim_numbers.py": "2005183bce64b9f6b6861d439f58bb7ab85fa89a06a664ff6817b2aa9df5367b",
    "tests/web/test_w1_env_keys.py": "8bee68458b30f91991b361d6f2aec694029b92ba6a2029df5c9490fe749aee16",
    "tests/web/test_w1_r16_review_regressions.py": "e25bc5cba3fd2ddde72d9b1822730e6f44702ca18c25154a38110ddb5ef69f1f",
    "tests/web/test_w1_r1_review_regressions.py": "fa7c4d149fc78c143bf9e4bd6d1eebf4fda687f1f87c421c2aee0bc90ce9069f",
    "tests/web/test_w1_r2_review_regressions.py": "af78cb1b1c02f36019064c4a46e7c8ed433f581bf3e39e6091992c612197ccc4",
    "tests/web/test_w1_r3_review_regressions.py": "ba23ee1299da967160a532f610f12c44f0881e72e5536c9900e18db62953530a",
    "tests/web/test_w1_r4_review_regressions.py": "2ddcdadeee9c0ce81d072baa3df7234ae0e482883cb548bb0e76fffe2f60096b",
    "tests/web/test_w1_r5_review_regressions.py": "1587afe1807f59231478202bdf80b3047af26186a71703413b517af55010c884",
    "tests/web/test_w1_r6_review_regressions.py": "385026d362e22efb930893eea308a3f936a04fb008542e87662cc846a79d57cb",
    "tests/web/test_w1_r9_review_regressions.py": "6759fc3b7bb2811c981a0da584cb096880398dc621afe4269bfe70a8af79d0ee",
    "tests/ws/test_ws_flake_1_request_stamp.py": "226603f83ecbfaf7bef725e5245f7a69b0e2f684525a9f2507fd4af4811b7442",
    "uri_assist/browser_extension/probe.js": "c3b6cfef8c2aaa113ef895db2bb8a4824a9a0a128584ee064fd4f69c2a6fa8a9",
    "uri_assist/onscreen.py": "67dac9221309cd8c3254cc412f1a444be5392b6faafa70c911c9edde30558a51",
    "uri_web/confusables_ascii.py": "edd780d1bc6e1de63eb6ddcfdb5bb64ffcc89c8e28d056396bc3e87eb6b98680",
    "uri_web/tld_list.py": "dae544929456ec27528abff389a78735c01d23a6770a627a6a2bf895ee85bb41"
}


class VerificationError(ValueError):
    pass


def git(root, *args):
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if p.returncode:
        raise VerificationError("GIT_REFUSED:" + " ".join(args[:2]))
    return p.stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def blob_id(data):
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def raw(root, name):
    parts = PurePosixPath(name)
    if parts.is_absolute() or ".." in parts.parts or "\\" in name or ":" in name:
        raise VerificationError("UNSAFE_PATH:" + name)
    root = Path(root).absolute()
    for parent in (root, *root.parents):
        if parent.is_symlink() or (hasattr(parent, "is_junction") and parent.is_junction()):
            raise VerificationError("ROOT_LINK")
    p = root
    for part in parts.parts:
        p = p / part
        if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
            raise VerificationError("LINK_REFUSED:" + name)
    if not stat.S_ISREG(p.stat().st_mode):
        raise VerificationError("NOT_REGULAR:" + name)
    return p.read_bytes()


def tree(root, revision):
    result = {}
    for row in git(root, "ls-tree", "-r", "-z", revision).split(b"\0"):
        if not row:
            continue
        meta, name = row.split(b"\t", 1)
        mode, kind, oid = meta.decode().split()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise VerificationError("UNSUPPORTED_GIT_MODE:" + name.decode())
        result[name.decode()] = (mode, oid)
    return result


def source_authority(source):
    source = Path(source).absolute()
    if Path(git(source, "rev-parse", "--show-toplevel").decode().strip()).resolve() != source.resolve():
        raise VerificationError("SOURCE_ROOT")
    anchor = accepted_anchor(source)
    if git(source, "diff", "--name-only") or git(source, "diff", "--cached", "--name-only"):
        raise VerificationError("SOURCE_DIRTY")
    frozen = F.check(source)
    if not frozen["ok"]:
        raise VerificationError("SOURCE_FROZEN_REFUSED")
    files = tree(source, "HEAD")
    # Raw comparisons also reject filters/attributes hiding a tool or authority edit.
    for name in (PATCH_PATH, AUTHORITY_PATH, "scripts/oi_materialize_test_runtime.py",
                 "scripts/ws_materialized_verify.py", "scripts/ws_frozen_check.py"):
        if name not in files or blob_id(raw(source, name)) != files[name][1]:
            raise VerificationError("SOURCE_TOOL_OR_AUTHORITY_CHANGED:" + name)
    if digest(raw(source, PATCH_PATH)) != PATCH_SHA256:
        raise VerificationError("PATCH_IDENTITY")
    authority = json.loads(raw(source, AUTHORITY_PATH))
    if authority != {
        "decision": "OWNER_WINDOWS_RESTORATION_20261014",
        "patch_sha256": PATCH_SHA256,
        "historical_head": "e8e3b65259c45fc823addc3ef8969425a265bd1b",
        "checkpoint_sha256": F.ZIP_SHA,
        "approved_blobs": {p: F.APPROVED[p]["sha256"] for p in BEFORE},
        "scope": "Fresh isolated historical runtime only; no other protected change, GPU override or cutover",
    }:
        raise VerificationError("OWNER_AUTHORITY_CHANGED")
    verify_inherited_scope(source, require_all=True, anchor=anchor)
    return files, frozen


def accepted_anchor(source):
    """The accepted line the source descends from; anything else is refused."""
    for anchor in (ACCEPTED_SOURCE, CANONICAL_SOURCE):
        p = subprocess.run(["git", "-C", str(source), "merge-base", "--is-ancestor", anchor, "HEAD"],
                           capture_output=True)
        if p.returncode == 0:
            return anchor
        if p.returncode != 1:
            raise VerificationError("GIT_REFUSED:merge-base --is-ancestor")
    raise VerificationError("SOURCE_NOT_ACCEPTED_LINEAGE")


def verify_inherited_scope(root, *, require_all=False, anchor=None):
    """Path recognition never authorizes a change to these inherited bytes.

    With no known anchor (an output gate without a source), the exact bytes of either accepted line
    are recognized; full output verification still compares every file with its own source.
    """
    for name, expected in INHERITED_SCOPE_BLOBS.items():
        allowed = {expected}
        if name in CANONICAL_SCOPE_BLOBS and anchor != ACCEPTED_SOURCE:
            allowed = {CANONICAL_SCOPE_BLOBS[name]} if anchor == CANONICAL_SOURCE else allowed | {CANONICAL_SCOPE_BLOBS[name]}
        present = (Path(root) / name).exists()
        if not present and None in allowed and require_all:
            continue
        if require_all or present:
            if digest(raw(root, name)) not in allowed:
                raise VerificationError("INHERITED_SCOPE_BLOB_CHANGED:" + name)


def expected_files(source, *, exclude_tests=False):
    from scripts import oi_materialize_test_runtime as M
    source = Path(source)
    files, _ = source_authority(source)
    expected = tree(source, M.BASE)
    overlay_data = raw(source, M.OVERLAY_LIST)
    if overlay_data != git(source, "show", accepted_anchor(source) + ":" + M.OVERLAY_LIST):
        raise VerificationError("OVERLAY_LIST_CHANGED")
    overlay = tree(source, M.OVERLAY_COMMIT)
    for path in overlay_data.decode().splitlines():
        if path.strip():
            expected[path.strip()] = overlay[path.strip()]
    for prefix in M.OI_PATHS:
        if exclude_tests and prefix in M.TEST_PATHS:
            continue
        chosen = {p: entry for p, entry in files.items() if p == prefix or p.startswith(prefix + "/")}
        if set(chosen) & set(expected):
            raise VerificationError("CANDIDATE_PATH_COLLISION:" + prefix)
        expected.update(chosen)
    for path in M.REPLACED_PATHS:
        expected[path] = files[path]
    for path in BEFORE:
        expected[path] = files[path]
    return expected


def reconcile(source, runtime):
    source_authority(source)
    for path, sha in BEFORE.items():
        if digest(raw(runtime, path)) != sha:
            raise VerificationError("TRANSITION_BEFORE_CHANGED:" + path)
    patch = Path(source) / PATCH_PATH
    git(runtime, "apply", "--check", str(patch))
    git(runtime, "apply", str(patch))
    result = {}
    for path, before in BEFORE.items():
        after = digest(raw(runtime, path))
        if after != F.APPROVED[path]["sha256"]:
            raise VerificationError("TRANSITION_AFTER_CHANGED:" + path)
        result[path] = {"before_sha256": before, "after_sha256": after}
    return result


def verify(source, runtime):
    from scripts import oi_materialize_test_runtime as M
    source, runtime = Path(source).absolute(), Path(runtime).absolute()
    result = {"ok": False, "source": str(source), "runtime": str(runtime)}
    try:
        for root in (source, runtime):
            if root.is_symlink() or (hasattr(root, "is_junction") and root.is_junction()):
                raise VerificationError("ROOT_LINK")
        source_authority(source)
        head = git(source, "rev-parse", "HEAD").decode().strip()
        source_tree = git(source, "rev-parse", "HEAD^{tree}").decode().strip()
        if Path(git(runtime, "rev-parse", "--show-toplevel").decode().strip()).resolve() != runtime.resolve():
            raise VerificationError("RUNTIME_ROOT")
        if git(runtime, "rev-parse", "HEAD").decode().strip() != M.BASE:
            raise VerificationError("HISTORICAL_HEAD_CHANGED")
        if git(runtime, "diff", "--cached", "--name-only", M.BASE):
            raise VerificationError("RUNTIME_INDEX_CHANGED")
        hidden = [r for r in git(runtime, "ls-files", "-v", "-z").decode().split("\0") if r and r[0] != "H"]
        if hidden:
            raise VerificationError("HIDDEN_INDEX_FLAGS")
        receipt = json.loads(raw(runtime, "OI_MATERIALIZATION_RECEIPT.json"))
        if (Path(receipt["candidate_source"]).resolve() != source.resolve()
                or receipt["candidate_head"] != head or receipt["candidate_tree"] != source_tree
                or receipt["head"] != M.BASE or receipt["overlay_commit"] != M.OVERLAY_COMMIT
                or receipt["security_patch_sha256"] != PATCH_SHA256
                or receipt["security_transitions"] != {
                    p: {"before_sha256": before, "after_sha256": F.APPROVED[p]["sha256"]}
                    for p, before in BEFORE.items()}):
            raise VerificationError("RECEIPT_IDENTITY")
        if type(receipt["oi_tests_included"]) is not bool:
            raise VerificationError("RECEIPT_TEST_SCOPE")
        expected = expected_files(source, exclude_tests=not receipt["oi_tests_included"])
        mismatches = []
        for name, (mode, oid) in expected.items():
            if blob_id(raw(runtime, name)) != oid:
                mismatches.append(name)
            # Windows has no POSIX execute bit; its Git index mode was checked
            # above. On hosts with real execution bits, verify those as well.
            if os.name != "nt" and bool((runtime / name).stat().st_mode & 0o111) != (mode == "100755"):
                raise VerificationError("OUTPUT_EXECUTION_MODE_CHANGED:" + name)
        if mismatches:
            raise VerificationError("OUTPUT_CHANGED:" + ",".join(mismatches[:10]))
        extras = []
        for current, dirs, names in os.walk(runtime, followlinks=False):
            rel = Path(current).relative_to(runtime)
            if not rel.parts:
                dirs[:] = [d for d in dirs if d not in (".git", ".venv", "work")]
            for d in dirs:
                p = Path(current) / d
                if p.is_symlink() or (hasattr(p, "is_junction") and p.is_junction()):
                    raise VerificationError("OUTPUT_DIRECTORY_LINK:" + p.relative_to(runtime).as_posix())
            for name in names:
                path = (rel / name).as_posix()
                if path not in expected and path not in (".git", "OI_MATERIALIZATION_RECEIPT.json"):
                    extras.append(path)
        if extras:
            raise VerificationError("UNKNOWN_OUTPUT:" + ",".join(sorted(extras)[:10]))
        # The two runtime security transitions. The FCV-01 rollback amendment is a source-tree tool change; the
        # historical runtime keeps the overlay's original rollback script (checked as an expected file above).
        for path in BEFORE:
            if digest(raw(runtime, path)) != F.APPROVED[path]["sha256"]:
                raise VerificationError("APPROVED_BLOB_CHANGED:" + path)
        # Provenance of the two runtime transitions (the runtime carries exactly these records).
        for path in sorted({w for p in BEFORE for w in F.APPROVED[p]["provenance"]}):
            if digest(raw(runtime, path)) != F.PROVENANCE[path]:
                raise VerificationError("PROVENANCE_CHANGED:" + path)
        result.update(ok=True, source_head=head, source_tree=source_tree, historical_head=M.BASE,
                      checked_files=len(expected), checkpoint_sha256=F.ZIP_SHA,
                      approved_blobs={p: F.APPROVED[p]["sha256"] for p in BEFORE},
                      note="Execution dependencies/state retain existing C1 identity and permission gates; this verifies source output, not live qualification.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        result["error"] = str(exc)
    return result


def verified_transitions(runtime):
    """Narrow reconciliation for original historical integrity gates.

    No receipt means original byte-identity behavior. A new receipt requires
    full output proof; it never grants permission merely by naming an exception.
    """
    verify_inherited_scope(runtime)
    receipt_path = Path(runtime) / "OI_MATERIALIZATION_RECEIPT.json"
    if not receipt_path.exists():
        return set()
    receipt = json.loads(raw(runtime, "OI_MATERIALIZATION_RECEIPT.json"))
    if "security_patch_sha256" not in receipt:
        return set()  # historical materializations retain their original gates
    result = verify(receipt["candidate_source"], runtime)
    if not result["ok"]:
        raise VerificationError("MATERIALIZED_GATE_REFUSED:" + result.get("error", "UNKNOWN"))
    return set(BEFORE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("runtime")
    ap.add_argument("--source", default=str(SOURCE))
    args = ap.parse_args()
    result = verify(args.source, args.runtime)
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
