"""Google Sheets through URI's existing Google sign-in (AC8, AC9, OFF-R2).

Credentials: the token URI's Google connection already stores (Gmail/Drive), read by absolute path with
`uri_core.core.google_auth_common.load_usable_credentials` — import only, uri_core is unchanged, no consent flow is ever
started here. Today's granted scopes are `gmail.readonly`, `gmail.compose`, `drive.readonly`, `drive.file`:

  read any sheet the owner can see            drive.readonly (Sheets API read)
  edit sheets URI created, copied or uploaded drive.file
  export a sheet to .xlsx                      drive.readonly
  "Share via Google" (upload + convert)        drive.file
  edit an existing sheet in place              needs https://www.googleapis.com/auth/spreadsheets  -> OFF-O1 (owner)

A pasted link is accepted only as https://docs.google.com/spreadsheets/d/<id>; only the ID is used and the URL itself is
never fetched. The file's Drive mimeType must be a Google Sheet before any content is read.
"""
from __future__ import annotations

import io
import json
import os
import re
from pathlib import Path

from . import refs
from .errors import OfficeError

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
SHEET_MIME = "application/vnd.google-apps.spreadsheet"
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_LINK = re.compile(r"^https://docs\.google\.com/spreadsheets/d/([A-Za-z0-9_-]{20,100})(?:[/?#][^\s]*)?$")
MAX_CELLS = 50_000


def parse_link(url) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise OfficeError("NOT_A_SHEETS_LINK", "paste a link that starts with https://docs.google.com/spreadsheets/d/")
    m = _LINK.match(url.strip())
    if not m:
        raise OfficeError("NOT_A_SHEETS_LINK", "paste a link that starts with https://docs.google.com/spreadsheets/d/")
    return m.group(1)


def _a1_sheet(name: str) -> str:
    return "'" + name.replace("'", "''") + "'"


class GoogleSheets:
    """`services` is injectable for tests: a callable returning (sheets_service, drive_service, granted_scopes)."""

    def __init__(self, state_dir: Path, token_path: str | None, services=None):
        self.state = Path(state_dir)
        self.token_path = token_path
        self._services = services
        self._owned_file = self.state / "google_owned.json"

    # ---- connection ----------------------------------------------------------------------------------------------
    def _connect(self):
        if self._services is not None:
            return self._services()
        if not self.token_path or not Path(self.token_path).is_file():
            raise OfficeError("GOOGLE_NOT_CONNECTED", "URI's Google connection is not set up on this PC", 409)
        from googleapiclient.discovery import build
        from uri_core.core.google_auth_common import load_usable_credentials
        creds = load_usable_credentials(token_path=str(self.token_path))
        if creds is None:
            raise OfficeError("GOOGLE_NOT_CONNECTED", "URI's Google sign-in has expired; reconnect Google in URI", 409)
        return (build("sheets", "v4", credentials=creds, cache_discovery=False),
                build("drive", "v3", credentials=creds, cache_discovery=False), set(creds.scopes or ()))

    def status(self) -> dict:
        try:
            _, _, scopes = self._connect()
        except OfficeError as exc:
            return {"connected": False, "code": exc.code}
        return {"connected": True, "can_edit_existing": SHEETS_SCOPE in scopes,
                "missing_permission": None if SHEETS_SCOPE in scopes else SHEETS_SCOPE}

    def _owned(self) -> set:
        try:
            return set(json.loads(self._owned_file.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            return set()

    def _add_owned(self, file_id):
        ids = self._owned() | {file_id}
        tmp = self._owned_file.with_suffix(".tmp")
        tmp.write_text(json.dumps(sorted(ids)), encoding="utf-8")
        os.replace(tmp, self._owned_file)

    # ---- reading -------------------------------------------------------------------------------------------------
    def check_sheet(self, file_id) -> dict:
        _, drive, _ = self._connect()
        meta = drive.files().get(fileId=file_id, fields="id,name,mimeType", supportsAllDrives=True).execute()
        if meta.get("mimeType") != SHEET_MIME:
            raise OfficeError("NOT_A_GOOGLE_SHEET", "the link is not a Google Sheet")
        return {"id": meta["id"], "name": str(meta.get("name", ""))[:200]}

    def read(self, file_id) -> dict:
        sheets_api, _, _ = self._connect()
        meta = sheets_api.spreadsheets().get(
            spreadsheetId=file_id, fields="sheets(properties(sheetId,title,index,gridProperties),merges)").execute()
        out = []
        total = 0
        for sh in meta.get("sheets", []):
            p = sh["properties"]
            rng = _a1_sheet(p["title"])
            vals = sheets_api.spreadsheets().values().get(spreadsheetId=file_id, range=rng,
                                                          valueRenderOption="UNFORMATTED_VALUE").execute().get("values", [])
            fml = sheets_api.spreadsheets().values().get(spreadsheetId=file_id, range=rng,
                                                         valueRenderOption="FORMULA").execute().get("values", [])
            cells, truncated = {}, False
            for r, row in enumerate(vals):
                for c, v in enumerate(row):
                    if v == "" or v is None:
                        continue
                    if total >= MAX_CELLS:
                        truncated = True
                        break
                    ref = refs.cell_ref(c + 1, r + 1)
                    entry = {"v": v}
                    f = fml[r][c] if r < len(fml) and c < len(fml[r]) else None
                    if isinstance(f, str) and f.startswith("="):
                        entry["f"] = f
                    cells[ref] = entry
                    total += 1
            merges = [f"{refs.cell_ref(m['startColumnIndex'] + 1, m['startRowIndex'] + 1)}:"
                      f"{refs.cell_ref(m['endColumnIndex'], m['endRowIndex'])}" for m in sh.get("merges", [])]
            g = p.get("gridProperties", {})
            out.append({"name": p["title"], "index": p.get("index", 0), "sheet_id": p["sheetId"],
                        "max_row": g.get("rowCount", 0), "max_col": g.get("columnCount", 0), "truncated": truncated,
                        "cells": cells, "merges": merges, "col_widths": {}, "row_heights": {}, "locked": []})
        return {"sheets": out, "styles": {}, "kept_not_shown": {"charts": 0, "images": 0, "pivot_tables": 0}}

    # ---- writing -------------------------------------------------------------------------------------------------
    def writable(self, file_id) -> bool:
        _, _, scopes = self._connect()
        return SHEETS_SCOPE in scopes or file_id in self._owned()

    def apply(self, file_id, body: dict) -> dict:
        """Re-read every edited cell; refuse if any differs from the shown `before`; then write."""
        if not self.writable(file_id):
            raise OfficeError("PERMISSION_NOT_GRANTED",
                              "editing this existing sheet needs the Google Sheets permission the owner has not "
                              "granted yet; use 'Edit a copy' instead", 403)
        sheets_api, _, _ = self._connect()
        edits = body["edits"]
        if edits:
            ranges = [f"{_a1_sheet(e['sheet'])}!{e['cell']}" for e in edits]
            now_v = sheets_api.spreadsheets().values().batchGet(
                spreadsheetId=file_id, ranges=ranges, valueRenderOption="UNFORMATTED_VALUE").execute()["valueRanges"]
            now_f = sheets_api.spreadsheets().values().batchGet(
                spreadsheetId=file_id, ranges=ranges, valueRenderOption="FORMULA").execute()["valueRanges"]
            for e, rv, rf in zip(edits, now_v, now_f):
                v = (rv.get("values") or [[None]])[0][0] if rv.get("values") else None
                f = (rf.get("values") or [[None]])[0][0] if rf.get("values") else None
                cur = {}
                if v not in (None, ""):
                    cur["v"] = v
                if isinstance(f, str) and f.startswith("="):
                    cur["f"] = f
                want = {k: x for k, x in (e["before"] or {}).items() if x not in (None, "")}
                if cur != want:
                    raise OfficeError("TARGET_CHANGED", f"{e['sheet']}!{e['cell']} changed in Google Sheets since it "
                                                        "was shown; review again", 409)
            raw = [{"range": f"{_a1_sheet(e['sheet'])}!{e['cell']}", "values": [[e["after"].get("v")]]}
                   for e in edits if not e["after"].get("f")]
            fml = [{"range": f"{_a1_sheet(e['sheet'])}!{e['cell']}", "values": [[e["after"]["f"]]]}
                   for e in edits if e["after"].get("f")]
            if raw:
                sheets_api.spreadsheets().values().batchUpdate(
                    spreadsheetId=file_id, body={"valueInputOption": "RAW", "data": raw}).execute()
            if fml:
                sheets_api.spreadsheets().values().batchUpdate(
                    spreadsheetId=file_id, body={"valueInputOption": "USER_ENTERED", "data": fml}).execute()
        if body["struct_ops"]:
            ids = {sh["properties"]["title"]: sh["properties"]["sheetId"] for sh in sheets_api.spreadsheets().get(
                spreadsheetId=file_id, fields="sheets(properties(sheetId,title))").execute().get("sheets", [])}
            reqs = []
            for op in body["struct_ops"]:
                if op["op"] in ("insert_rows", "delete_rows"):
                    if op["sheet"] not in ids:
                        raise OfficeError("TARGET_CHANGED", "a sheet was renamed or removed since it was shown", 409)
                    rng = {"sheetId": ids[op["sheet"]], "dimension": "ROWS", "startIndex": op["at"] - 1,
                           "endIndex": op["at"] - 1 + op["count"]}
                    reqs.append({"insertDimension": {"range": rng, "inheritFromBefore": op["at"] > 1}}
                                if op["op"] == "insert_rows" else {"deleteDimension": {"range": rng}})
                elif op["op"] == "add_sheet":
                    reqs.append({"addSheet": {"properties": {"title": op["name"]}}})
                elif op["op"] == "rename_sheet":
                    if op["sheet"] not in ids:
                        raise OfficeError("TARGET_CHANGED", "a sheet was renamed or removed since it was shown", 409)
                    reqs.append({"updateSheetProperties": {"properties": {"sheetId": ids[op["sheet"]], "title": op["name"]},
                                                           "fields": "title"}})
            sheets_api.spreadsheets().batchUpdate(spreadsheetId=file_id, body={"requests": reqs}).execute()
        return {"cells": len(edits), "struct_ops": len(body["struct_ops"])}

    def copy(self, file_id, name: str) -> dict:
        """A copy URI owns (drive.file), so it can be edited without the OFF-O1 permission. Not yet verified live."""
        _, drive, _ = self._connect()
        r = drive.files().copy(fileId=file_id, body={"name": name[:200]}, fields="id,name",
                               supportsAllDrives=True).execute()
        self._add_owned(r["id"])
        return {"id": r["id"], "name": r.get("name", "")}

    def upload_convert(self, path: Path, name: str) -> dict:
        from googleapiclient.http import MediaIoBaseUpload
        _, drive, _ = self._connect()
        media = MediaIoBaseUpload(io.BytesIO(Path(path).read_bytes()), mimetype=XLSX_MIME, resumable=False)
        r = drive.files().create(body={"name": name[:200], "mimeType": SHEET_MIME}, media_body=media,
                                 fields="id,name").execute()
        self._add_owned(r["id"])
        return {"id": r["id"], "name": r.get("name", "")}

    def export_xlsx(self, file_id, dest: Path) -> dict:
        _, drive, _ = self._connect()
        data = drive.files().export(fileId=file_id, mimeType=XLSX_MIME).execute()
        tmp = dest.with_name(dest.name + ".uri-office.tmp")
        tmp.write_bytes(data)
        os.replace(tmp, dest)
        return {"bytes": len(data)}


def open_url(file_id: str) -> str:
    return f"https://docs.google.com/spreadsheets/d/{file_id}/edit"
