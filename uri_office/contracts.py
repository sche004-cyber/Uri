"""O2 shared contract (`docs/office/unified/O2_API_CONTRACT.md`, contract `o2.1`).

Plain data: the contract version, the closed value sets, the Finding shape and the error catalogue with a fixed
owner-facing message and recovery action per code (plan refinement 7). No framework and no I/O. The service, the
workflow runner, the validators and (O2P) the device layer import from here so every surface uses the same words.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

CONTRACT_VERSION = "o2.1"

KINDS = ("xlsx", "docx", "pptx", "pdf")
STEP_KINDS = ("D", "E", "B")
SEVERITIES = ("error", "warning", "info")
CHECK_KINDS = ("structural", "render", "visual", "integrity", "fidelity")
ENGINE_STATES = ("unverified", "verifying", "ready", "starting", "running", "idle_stopped", "unavailable")
WORKFLOW_STATES = ("planned", "waiting_approval", "running", "interrupted", "needs_review", "ready_to_save", "saved",
                   "cancelled", "failed", "discarded")
STEP_STATES = ("pending", "running", "done", "failed", "skipped", "cancelled")
EFFECTS = ("reads_files", "writes_new_file", "sends_to_printer", "uses_brain")
APPROVALS = ("none", "plan_and_outputs", "print_job")
OFFICE_VIEWS = ("home", "recent", "documents", "spreadsheets", "presentations", "pdfs", "templates", "workflows",
                "devices")
SUBJECT_KINDS = ("workbook", "plan", "output_files", "print_job")
# Where a finding points. Never a path or document text.
LOCATION_FILES = ("source", "output")

# Page image widths in pixels (contract §4). 440/880/1240 are on-screen, zoom and 300-dpi-class; 160 is a thumbnail.
PAGE_WIDTHS = (160, 440, 880, 1240)

# Routes added in O2 (method, path pattern). `<id>` is 16-32 lowercase hex; `<n>` a 1-based page number.
ROUTES = (
    ("GET", "/contract"), ("GET", "/capabilities"), ("GET", "/engines"), ("POST", "/engines/verify"),
    ("POST", "/open/document"), ("GET", "/document/<id>"), ("GET", "/document/<id>/page/<n>"),
    ("POST", "/document/<id>/search"), ("POST", "/document/<id>/close"),
    ("POST", "/request"), ("POST", "/workflow"), ("GET", "/workflow/<id>"), ("POST", "/workflow/<id>/answer"),
    ("POST", "/workflow/<id>/cancel"), ("POST", "/workflow/<id>/resume"), ("POST", "/workflow/<id>/accept_warnings"),
    ("POST", "/workflow/<id>/propose_save"), ("GET", "/workflow/<id>/output/page/<n>"), ("GET", "/workflows"),
    ("GET", "/recent"), ("POST", "/recent/remove"), ("POST", "/recent/clear"),
)


@dataclass(frozen=True)
class ErrorInfo:
    message: str
    recovery: tuple          # recovery action ids the UI shows as buttons, in order; () = nothing to do


# Owner-facing text for every code the O2 routes can return. Existing M1/M2 codes keep their own panel texts.
ERRORS: dict[str, ErrorInfo] = {
    "ENGINE_MISSING": ErrorInfo("The document engine is not installed on this PC.", ("help_engine",)),
    "ENGINE_INTEGRITY": ErrorInfo("The document engine failed its safety check and was not started.",
                                  ("verify_engine", "help_engine")),
    "ENGINE_START_FAILED": ErrorInfo("The document engine did not start.", ("retry",)),
    "ENGINE_TIMEOUT": ErrorInfo("The document took too long to process.", ("retry",)),
    "ENGINE_CRASHED": ErrorInfo("The document engine stopped unexpectedly. It will restart on the next try.",
                                ("retry",)),
    "ENGINE_UNAVAILABLE": ErrorInfo("Previews and conversions are not available right now.",
                                    ("verify_engine", "help_engine")),
    "WORKER_INTEGRITY": ErrorInfo("A helper program failed its safety check and was not run.", ("help_engine",)),
    "CLM_ACTIVE": ErrorInfo("Windows security policy on this PC blocks the PDF renderer.", ("help_engine",)),
    "PREVIEW_UNAVAILABLE": ErrorInfo("This page could not be shown.", ("retry", "open_other")),
    "PAGE_NOT_READY": ErrorInfo("This page is still being prepared.", ()),
    "NO_TEXT_LAYER": ErrorInfo("This PDF has no searchable text (it may be a scan).", ()),
    "UNSUPPORTED_KIND": ErrorInfo("URI Office opens Word, PowerPoint, Excel and PDF files only.", ("open_other",)),
    "ENCRYPTED": ErrorInfo("This file is password-protected, so URI cannot open it.", ("open_other",)),
    "ARCHIVE_REFUSED": ErrorInfo("This file looks damaged or unsafe and was not opened.", ("open_other",)),
    "XML_REFUSED": ErrorInfo("This file contains content URI does not read for safety reasons.", ("open_other",)),
    "FILE_TOO_LARGE": ErrorInfo("This file is larger than URI Office accepts.", ("open_other",)),
    "TOO_MANY_PAGES": ErrorInfo("This PDF has more pages than URI Office accepts.", ("open_other",)),
    "TOO_MANY_OPEN": ErrorInfo("Too many files are open. Close one first.", ("close_one",)),
    "PATH_REFUSED": ErrorInfo("URI cannot use that location.", ("choose_location",)),
    "NO_GRANT": ErrorInfo("This file was not chosen by you in this session.", ("open_again",)),
    "UNKNOWN_DOCUMENT": ErrorInfo("That document is no longer open.", ("open_again",)),
    "UNKNOWN_WORKFLOW": ErrorInfo("That task no longer exists.", ()),
    "UNSAVED_CHANGES": ErrorInfo("Save your changes first, or discard them.", ("save", "discard")),
    "CAPABILITY_PLANNED": ErrorInfo("This is not available yet.", ()),
    "DESTINATION_EXISTS": ErrorInfo("A file with that name already exists. URI never replaces files.",
                                    ("choose_name",)),
    "HAS_ERRORS": ErrorInfo("The result has problems that must be fixed before it can be saved.", ("show_findings",)),
    "WARNINGS_NOT_ACCEPTED": ErrorInfo("Review the warnings and accept them before saving.", ("show_findings",)),
    "INPUT_CHANGED": ErrorInfo("A file changed since this task started, so it was stopped.", ("start_again",)),
    "NOT_CANCELLABLE": ErrorInfo("This task has already finished.", ()),
    "STALE_PLAN": ErrorInfo("The plan changed after it was shown. Review it again.", ("show_plan",)),
    "WRITE_FAILED": ErrorInfo("The file could not be written. Nothing was left half-written.",
                              ("retry", "choose_location")),
    "DISK_FULL": ErrorInfo("The disk is full. Nothing was left half-written.", ("choose_location",)),
    "INTERRUPTED": ErrorInfo("This task was interrupted.", ("resume", "discard")),
    "BAD_REQUEST": ErrorInfo("The request was not understood.", ()),
    # O2P printing (review round 3, m2)
    "UNKNOWN_PRINTER": ErrorInfo("That printer is no longer installed.", ("check_printers",)),
    "PRINTER_NOT_SUPPORTED": ErrorInfo("URI cannot print to this printer without opening another program.",
                                       ("choose_printer",)),
    "PRINTER_UNAVAILABLE": ErrorInfo("The printer is not ready (offline, out of paper or needing attention).",
                                     ("check_printers", "choose_printer")),
    "SETTING_NOT_SUPPORTED": ErrorInfo("The printer cannot do one of the chosen settings.", ("choose_printer",)),
    "PRINT_TOO_LARGE": ErrorInfo("Print fewer pages at a time.", ()),
    "UNKNOWN_PRINT_JOB": ErrorInfo("That print job no longer exists.", ()),
    "PRINT_TIMEOUT": ErrorInfo("Printing took too long and was stopped.", ("retry",)),
    "PRINT_FAILED": ErrorInfo("Printing failed. Nothing more will be sent.", ("retry", "check_printers")),
    "PAPER_NOT_SUPPORTED": ErrorInfo("The printer does not have that paper size.", ("choose_printer",)),
    "PRINTER_NOT_FOUND": ErrorInfo("Windows could not find that printer.", ("check_printers",)),
}

RECOVERY_ACTIONS = ("help_engine", "verify_engine", "retry", "open_other", "close_one", "choose_location", "open_again",
                    "save", "discard", "choose_name", "show_findings", "start_again", "show_plan", "resume",
                    "check_printers", "choose_printer")


def error_view(code: str, detail: str = "") -> dict:
    """The JSON body for an O2 error: code, short detail (never content), message and recovery actions."""
    info = ERRORS.get(code)
    out = {"error": code, "detail": detail}
    if info:
        out["message"] = info.message
        out["recovery"] = list(info.recovery)
    return out


@dataclass
class Finding:
    id: str
    check: str
    kind: str                     # CHECK_KINDS
    severity: str                 # SEVERITIES
    message: str
    file: str = "output"          # LOCATION_FILES
    page: int | None = None       # 1-based page or slide
    repair_kind: str = "owner"    # "rule" | "brain" | "owner"
    rule_id: str | None = None
    weak: bool = False            # the check is a weaker heuristic (e.g. edge-ink overflow), labelled in the UI

    def __post_init__(self):
        if self.kind not in CHECK_KINDS or self.severity not in SEVERITIES or self.file not in LOCATION_FILES:
            raise ValueError("bad finding")
        if self.repair_kind not in ("rule", "brain", "owner"):
            raise ValueError("bad repair kind")
        if len(self.message) > 300:
            raise ValueError("finding message too long")

    def view(self) -> dict:
        d = asdict(self)
        return {"id": d["id"], "check": d["check"], "kind": d["kind"], "severity": d["severity"],
                "location": {"file": d["file"], "page": d["page"]}, "message": d["message"],
                "repair": {"kind": d["repair_kind"], "rule_id": d["rule_id"]}, "weak": d["weak"]}


@dataclass
class Findings:
    items: list = field(default_factory=list)

    def add(self, check, kind, severity, message, **kw) -> Finding:
        f = Finding(f"f-{len(self.items) + 1}", check, kind, severity, message, **kw)
        self.items.append(f)
        return f

    @property
    def errors(self) -> list:
        return [f for f in self.items if f.severity == "error"]

    @property
    def warnings(self) -> list:
        return [f for f in self.items if f.severity == "warning"]

    def view(self) -> list:
        return [f.view() for f in self.items]


def contract_view() -> dict:
    return {"contract": CONTRACT_VERSION, "routes": [f"{m} {p}" for m, p in ROUTES], "kinds": list(KINDS),
            "views": list(OFFICE_VIEWS)}
