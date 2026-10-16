"""Writes uri_ui/test/office/fixtures/authoring_save_card.json: a real save card made by the Python service
(`Approvals.propose_authoring_save` through an authoring session), so the Flutter editor tests render the same messages
the service sends. Run from the repository root: python tests/office_u2/make_authoring_card_fixture.py"""
import io
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from test_authoring_pptx import FakeDocuments, deck_bytes  # noqa: E402
from uri_office.approvals import Approvals  # noqa: E402
from uri_office.authoring.session import Authoring  # noqa: E402
from uri_office.grants import Grants  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t)
        p = tmp / "Quarterly Review.pptx"
        p.write_bytes(deck_bytes())
        (tmp / "state").mkdir()
        grants = Grants([tmp])
        docs = FakeDocuments(grants)
        appr = Approvals(tmp / "state", "owner")
        a = Authoring(tmp / "state", docs, grants, appr)
        v = a.edit_document(docs.add_opened(p, grants))
        aid = v["authoring_id"]
        a.apply(aid, {"op": "set_title", "slide": v["deck"]["slides"][0]["id"], "text": "Quarterly Review 2026"})
        msgs = a.propose_save(aid)["messages"]
        appr.db.close()
        text = json.dumps(msgs, ensure_ascii=False, indent=1)
        # the temporary folder as it appears inside JSON strings (backslashes escaped)
        text = text.replace(json.dumps(str(tmp))[1:-1], json.dumps("C:\\Users\\me\\Documents")[1:-1])
    out = ROOT / "uri_ui" / "test" / "office" / "fixtures" / "authoring_save_card.json"
    out.write_text(text + "\n", encoding="utf-8", newline="\n")
    print(out, aid)


if __name__ == "__main__":
    main()
