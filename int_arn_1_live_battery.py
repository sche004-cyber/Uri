"""Small authenticated INT-ARN-1 live diagnostic battery (standard library only).

Run against a desktop backend started with URI_INT_ARN_1_ENABLED=1 and
URI_INT_ARN_1_DIAGNOSTICS=1. --model labels the run; account settings choose
the actual Brain. No token or fixture content is printed.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path


BASE_URL = "http://127.0.0.1:8000"
FIXTURES = {
    "q3_report.txt": "Sales report Q3 2025. North: 120 units. South: 95 units. Total: 215 units.\n",
    "q4_report.txt": "Sales report Q4 2025. North: 135 units. South: 105 units. Total: 240 units.\n",
    "budget_2025.csv": "department,amount\nResearch,1000\nOperations,800\n",
    "budget_2026.csv": "department,amount\nResearch,1200\nOperations,850\n",
}
CASES = (
    ("single_attachment", ("q3_report.txt",), "Summarize this attached report.", None),
    ("similar_reports", ("q3_report.txt", "q4_report.txt"), "Summarize the sales report.", None),
    ("compare_them", ("q3_report.txt", "q4_report.txt"), "Compare them.", None),
    ("two_budgets", ("budget_2025.csv", "budget_2026.csv"), "Open the budget file.", None),
    ("named_file", ("q3_report.txt", "q4_report.txt"), "Summarize q4_report.txt.", None),
    ("earlier_turn", ("q3_report.txt", "q4_report.txt"), "Summarize the one I sent before.",
     "I sent a Q3 sales report earlier. Please remember that for my next question."),
    ("chat_control", (), "What is 7 plus 5?", None),
    ("consequential_ambiguous", ("q3_report.txt", "q4_report.txt"),
     "Convert the report to Word.", None),
)


def request(path: str, token: str, *, body: bytes, content_type: str) -> dict:
    req = urllib.request.Request(BASE_URL + path, data=body, method="POST", headers={
        "Authorization": "Bearer " + token,
        "Content-Type": content_type,
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=120) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"HTTP {exc.code} on {path}") from None


def upload(token: str, session_id: str, path: Path) -> str:
    boundary = "uri-battery-" + uuid.uuid4().hex
    parts = [
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"session_id\"\r\n\r\n{session_id}\r\n".encode(),
        (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
         f"Content-Type: {mimetypes.guess_type(path.name)[0] or 'application/octet-stream'}\r\n\r\n").encode(),
        path.read_bytes(), f"\r\n--{boundary}--\r\n".encode(),
    ]
    response = request("/files", token, body=b"".join(parts),
                       content_type=f"multipart/form-data; boundary={boundary}")
    return response["file"]["file_id"]


def ask(token: str, session_id: str, text: str, ids: list[str], clarification=None) -> tuple[dict, float]:
    payload = {"session_id": session_id, "text": text, "attached_file_ids": ids}
    if clarification is not None:
        payload["clarification_response"] = clarification
    started = time.monotonic()
    result = request("/ask", token, body=json.dumps(payload).encode("utf-8"),
                     content_type="application/json")
    return result, round((time.monotonic() - started) * 1000, 1)


def summarize(response: dict, latency_ms: float) -> dict:
    card = response.get("clarification") or {}
    reply = response.get("narrative") or response.get("response") or {}
    if isinstance(reply, dict):
        reply = reply.get("message") or reply.get("text") or ""
    execution = response.get("execution") or {}
    diagnostics = response.get("reference_diagnostics") or {}
    return {
        "latency_ms": latency_ms,
        "serving_model": response.get("serving_model"),
        "reference_diagnostics": response.get("reference_diagnostics"),
        "execution_status": execution.get("status"),
        "execution_capability": (execution.get("capability") or
                                 (response.get("plan") or {}).get("capability") or
                                 diagnostics.get("capability") or
                                 (response.get("semantic_analysis") or {}).get("capability")),
        "clarification_card": bool(card),
        "option_labels": [item.get("label") for item in card.get("options", [])],
        "reply": str(reply)[:200],
    }


def first_choice(card: dict) -> dict | None:
    options = card.get("options") or []
    if not options:
        return None
    option = options[0]
    return {
        "ambiguity_id": card["ambiguity_id"], "response_kind": "CANDIDATE",
        "candidate_id": option["candidate_id"], "option_key": option["option_key"],
        "candidate_set_fingerprint": card["candidate_set_fingerprint"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-file", type=Path, required=True, help="JSON file containing a token key")
    parser.add_argument("--model", required=True, help="Report label only; does not switch the account Brain")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--answer-first-option", action="store_true")
    args = parser.parse_args()
    token = json.loads(args.token_file.read_text(encoding="utf-8"))["token"]
    if not isinstance(token, str) or not token:
        parser.error("token file must contain a non-empty token")

    report = {"model_label": args.model, "backend": BASE_URL, "cases": []}
    with tempfile.TemporaryDirectory(prefix="uri-int-arn-battery-") as directory:
        fixture_paths = {}
        for name, content in FIXTURES.items():
            path = Path(directory) / name
            path.write_text(content, encoding="utf-8")
            fixture_paths[name] = path
        for case_name, names, text, preturn in CASES:
            session_id = "int-arn-battery-" + uuid.uuid4().hex
            row = {"case": case_name, "session_id": session_id}
            try:
                ids = [upload(token, session_id, fixture_paths[name]) for name in names]
                if preturn:
                    pre, elapsed = ask(token, session_id, preturn, ids[:1])
                    row["setup_turn"] = summarize(pre, elapsed)
                    # The target is an earlier-turn reference, with no new attachment.
                    ids = []
                response, elapsed = ask(token, session_id, text, ids)
                row["first"] = summarize(response, elapsed)
                if args.answer_first_option and response.get("clarification"):
                    choice = first_choice(response["clarification"])
                    if choice:
                        follow, follow_elapsed = ask(token, session_id, "", [], choice)
                        row["follow_up"] = summarize(follow, follow_elapsed)
            except (OSError, ValueError, KeyError, RuntimeError) as exc:
                row["error"] = str(exc)[:200]
            report["cases"].append(row)
            first = row.get("first") or {}
            diag = first.get("reference_diagnostics") or {}
            print(f"{case_name:26} {str(first.get('latency_ms', '-')):>8} ms  "
                  f"{str(first.get('serving_model') or '-'):18.18}  "
                  f"{str(diag.get('outcome') or '-'):8}  "
                  f"card={str(first.get('clarification_card', False)):5}  "
                  f"{row.get('error', '')}")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
