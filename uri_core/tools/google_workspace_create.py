"""Approved creation of new Google Workspace files in the caller's Drive."""

from __future__ import annotations

from googleapiclient.discovery import build

from uri_core.core.google_auth_common import load_usable_credentials
from uri_core.services.google_errors import classify_google_error


MIME = {
    "folder": "application/vnd.google-apps.folder",
    "sheet": "application/vnd.google-apps.spreadsheet",
    "doc": "application/vnd.google-apps.document",
    "slides": "application/vnd.google-apps.presentation",
}
API = {"sheet": "sheets", "doc": "docs", "slides": "slides", "form": "forms"}
LINK = {"folder": "drive.google.com/drive/folders", "sheet": "docs.google.com/spreadsheets/d",
        "doc": "docs.google.com/document/d", "slides": "docs.google.com/presentation/d",
        "form": "docs.google.com/forms/d"}


def _fallback_link(kind, file_id):
    suffix = "" if kind == "folder" else "/edit"
    return f"https://{LINK[kind]}/{file_id}{suffix}"


def _strings(value, label, maximum=100):
    if not isinstance(value, list) or len(value) > maximum or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise ValueError(f"{label} must be a list of nonempty text values (up to {maximum}).")
    return [item.strip() for item in value]


def _validate(kwargs):
    kind = kwargs.get("kind")
    title = kwargs.get("title")
    folder = kwargs.get("folder_name")
    if kind not in {*MIME, "form"}:
        raise ValueError("kind must be folder, sheet, doc, slides, or form.")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("title is required.")
    if folder is not None and (not isinstance(folder, str) or not folder.strip()):
        raise ValueError("folder_name must be nonempty text.")
    if kind == "folder" and folder is not None:
        raise ValueError("folder_name is not used when creating a folder.")
    allowed = {"kind", "title", "folder_name", "session_id", "principal", "principal_context", "request_text", "decision_context", "current_turn_attachment_ids", "grants_store"}
    if kind == "sheet":
        allowed |= {"headers", "empty_rows", "format"}
        headers = _strings(kwargs.get("headers"), "headers", 50)
        if not headers:
            raise ValueError("headers must contain at least one column heading.")
        rows = kwargs.get("empty_rows", 0)
        if type(rows) is not int or not 0 <= rows <= 1000:
            raise ValueError("empty_rows must be an integer from 0 to 1000.")
        if kwargs.get("format", "professional") != "professional":
            raise ValueError("format must be professional.")
        content = {"headers": headers, "empty_rows": rows, "format": "professional"}
    elif kind == "doc":
        allowed |= {"heading", "body"}
        content = {key: kwargs.get(key, "") for key in ("heading", "body")}
        if any(not isinstance(value, str) for value in content.values()):
            raise ValueError("heading and body must be text.")
    elif kind == "slides":
        allowed.add("slide_titles")
        content = {"slide_titles": _strings(kwargs.get("slide_titles", []), "slide_titles", 30)}
    elif kind == "form":
        allowed.add("questions")
        questions = kwargs.get("questions", [])
        if not isinstance(questions, list) or len(questions) > 100:
            raise ValueError("questions must be a list of up to 100 text questions.")
        for item in questions:
            if not isinstance(item, dict) or set(item) - {"title", "required"} or not isinstance(item.get("title"), str) or not item["title"].strip() or type(item.get("required", False)) is not bool:
                raise ValueError("Each question needs a title and optional boolean required flag.")
        content = {"questions": questions}
    else:
        content = {}
    if set(kwargs) - allowed:
        raise ValueError("Unsupported arguments for this kind: " + ", ".join(sorted(set(kwargs) - allowed)))
    return kind, title.strip(), folder.strip() if folder else None, content


def _exact_files(drive, name, parent=None, mime=None):
    escaped = name.replace("\\", "\\\\").replace("'", "\\'")
    query = f"name = '{escaped}' and trashed = false"
    if parent:
        query += f" and '{parent}' in parents"
    if mime:
        query += f" and mimeType = '{mime}'"
    found = []
    page = None
    while True:
        result = drive.files().list(q=query, fields="nextPageToken, files(id,name,mimeType,webViewLink,parents)", pageSize=100, pageToken=page).execute()
        found.extend(result.get("files", []))
        page = result.get("nextPageToken")
        if not page:
            return found


def _sheet_requests(headers, empty_rows):
    columns = len(headers)
    count = empty_rows + 1
    color = {"red": 0.10, "green": 0.22, "blue": 0.38}
    return [
        {"updateSheetProperties": {"properties": {"sheetId": 0, "gridProperties": {"frozenRowCount": 1, "rowCount": count, "columnCount": max(26, columns)}}, "fields": "gridProperties.frozenRowCount,gridProperties.rowCount,gridProperties.columnCount"}},
        {"updateCells": {"start": {"sheetId": 0, "rowIndex": 0, "columnIndex": 0}, "rows": [{"values": [{"userEnteredValue": {"stringValue": h}} for h in headers]}], "fields": "userEnteredValue"}},
        {"repeatCell": {"range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": 1, "startColumnIndex": 0, "endColumnIndex": columns}, "cell": {"userEnteredFormat": {"backgroundColor": color, "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}, "verticalAlignment": "MIDDLE"}}, "fields": "userEnteredFormat"}},
        {"updateDimensionProperties": {"range": {"sheetId": 0, "dimension": "COLUMNS", "startIndex": 0, "endIndex": columns}, "properties": {"pixelSize": 180}, "fields": "pixelSize"}},
        {"updateDimensionProperties": {"range": {"sheetId": 0, "dimension": "ROWS", "startIndex": 0, "endIndex": 1}, "properties": {"pixelSize": 38}, "fields": "pixelSize"}},
        {"addBanding": {"bandedRange": {"range": {"sheetId": 0, "startRowIndex": 0, "endRowIndex": count, "startColumnIndex": 0, "endColumnIndex": columns}, "rowProperties": {"headerColor": color, "firstBandColor": {"red": 1, "green": 1, "blue": 1}, "secondBandColor": {"red": 0.95, "green": 0.97, "blue": 0.99}}}}},
    ]


class GoogleWorkspaceCreateTool:
    def __init__(self, user_id=None, build_service=build, credential_loader=load_usable_credentials):
        self.user_id = user_id
        self._build = build_service
        self._credentials = credential_loader

    def generate(self, **kwargs):
        try:
            kind, title, folder_name, content = _validate(kwargs)
        except ValueError as exc:
            return {"status": "input_required", "message": str(exc)}
        if not self.user_id:
            return {"status": "unavailable", "message": "Sign in to URI and connect your Google account first."}
        creds = self._credentials(user_id=self.user_id)
        if creds is None:
            return {"status": "unavailable", "message": "Connect Google in URI, then retry."}
        created_id = None
        api = "drive"
        try:
            drive = self._build("drive", "v3", credentials=creds, cache_discovery=False)
            folder = None
            if folder_name:
                matches = _exact_files(drive, folder_name, mime=MIME["folder"])
                if len(matches) > 1:
                    return {"status": "input_required", "message": f"Multiple folders named '{folder_name}' are visible. Choose a unique folder name."}
                folder = matches[0] if matches else drive.files().create(body={"name": folder_name, "mimeType": MIME["folder"]}, fields="id,name,webViewLink").execute()
            parent = folder["id"] if folder else None
            # A matching name is never silently duplicated in the target location.
            if _exact_files(drive, title, parent=parent or "root"):
                return {"status": "already_exists", "message": f"A file named '{title}' already exists in the target folder. Choose another title."}
            if kind == "form":
                api = "forms"
                forms = self._build("forms", "v1", credentials=creds, cache_discovery=False)
                created = forms.forms().create(body={"info": {"title": title, "documentTitle": title}}).execute()
                created_id = created["formId"]
                if folder:
                    api = "drive"
                    # Only the just-created form is moved from My Drive root.
                    existing_parents = drive.files().get(fileId=created_id, fields="parents").execute().get("parents", [])
                    drive.files().update(fileId=created_id, addParents=parent, removeParents=",".join(existing_parents), fields="id,parents").execute()
                api = "forms"
                requests = [{"createItem": {"item": {"title": q["title"].strip(), "questionItem": {"question": {"required": q.get("required", False), "textQuestion": {"paragraph": False}}}}, "location": {"index": i}}} for i, q in enumerate(content["questions"])]
                if requests:
                    forms.forms().batchUpdate(formId=created_id, body={"requests": requests}).execute()
            else:
                body = {"name": title, "mimeType": MIME[kind]}
                if parent:
                    body["parents"] = [parent]
                created = drive.files().create(body=body, fields="id,name,webViewLink").execute()
                created_id = created["id"]
                if kind == "sheet":
                    api = "sheets"
                    sheets = self._build("sheets", "v4", credentials=creds, cache_discovery=False)
                    sheets.spreadsheets().batchUpdate(spreadsheetId=created_id, body={"requests": _sheet_requests(**{k: content[k] for k in ("headers", "empty_rows")})}).execute()
                elif kind == "doc" and (content["heading"] or content["body"]):
                    api = "docs"
                    docs = self._build("docs", "v1", credentials=creds, cache_discovery=False)
                    heading = content["heading"].strip()
                    text = (heading + "\n" if heading else "") + content["body"]
                    requests = [{"insertText": {"endOfSegmentLocation": {}, "text": text}}]
                    if heading:
                        requests.append({"updateParagraphStyle": {"range": {"startIndex": 1, "endIndex": 1 + len(heading)}, "paragraphStyle": {"namedStyleType": "HEADING_1"}, "fields": "namedStyleType"}})
                    docs.documents().batchUpdate(documentId=created_id, body={"requests": requests}).execute()
                elif kind == "slides" and content["slide_titles"]:
                    api = "slides"
                    slides = self._build("slides", "v1", credentials=creds, cache_discovery=False)
                    requests = []
                    for i, heading in enumerate(content["slide_titles"]):
                        slide_id, shape_id = f"uri_slide_{i}", f"uri_title_{i}"
                        requests += [{"createSlide": {"objectId": slide_id, "slideLayoutReference": {"predefinedLayout": "BLANK"}}}, {"createShape": {"objectId": shape_id, "shapeType": "TEXT_BOX", "elementProperties": {"pageObjectId": slide_id, "size": {"width": {"magnitude": 600, "unit": "PT"}, "height": {"magnitude": 60, "unit": "PT"}}, "transform": {"scaleX": 1, "scaleY": 1, "translateX": 50, "translateY": 45, "unit": "PT"}}}}, {"insertText": {"objectId": shape_id, "text": heading}}]
                    slides.presentations().batchUpdate(presentationId=created_id, body={"requests": requests}).execute()
            link = created.get("webViewLink") if kind != "form" else None
            return {"status": "success", "file_id": created_id, "name": title, "webViewLink": link or _fallback_link(kind, created_id), "folder": folder_name, "applied": content}
        except Exception as exc:
            failure = classify_google_error(exc, api)
            result = {"status": "unavailable", "message": failure["message"], "error": failure["kind"]}
            if created_id:
                result.update({"file_id": created_id, "webViewLink": _fallback_link(kind, created_id), "message": failure["message"] + " A new file was created; check it before retrying to avoid a duplicate."})
            return result
