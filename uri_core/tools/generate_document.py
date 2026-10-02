"""Capability: generate a real Office file (DOCX/XLSX/PPTX/PDF) from a
request (M19).

This is the generic counterpart to draft_institutional_note/
draft_institutional_order: it never assumes the document is an
institutional note or order, and it never emits a template. The
requested output FORMAT (docx/xlsx/pptx/pdf) is detected from the
request; the Brain then authors the actual content, exactly the same
way M17's institutional drafting does - by reusing
services/institutional_drafting.py's policy/evidence/soul assembly and
services/document_composer.py's Brain-authoring call, just without the
note/order-specific framing. The rendered bytes are stored through
FileStore (containment-checked, size/type-validated, session-scoped),
so the result is downloadable via the existing GET
/files/{file_id}/content - no second storage path.
"""

import re
from typing import Any, Dict, Optional

from uri_core.config.institutional_rules import load_institutional_rules
from uri_core.core.file_store import FileStore, FileValidationError, sanitize_filename
from uri_core.services.document_composer import DocumentComposer
from uri_core.services.drafting_guidance import build_drafting_brief
from uri_core.services.document_writer_service import DocumentWriterService
from uri_core.services.institutional_drafting import (
    extract_drafting_rules,
    gather_session_evidence,
    read_text_file,
    POLICY_PATH,
    SOUL_PATH,
)
from uri_core.services.office_document_writer import (
    render_pdf_bytes,
    render_pptx_bytes,
    render_xlsx_bytes,
)


_MEDIA_TYPES = {
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "pdf": "application/pdf",
}

# Ordered so a more specific phrase ("slide deck") is checked before a
# more general one; the first match wins. Deliberately keyword-based
# (the same discipline drafting_guidance.classify_purpose already
# uses) - the FORMAT is the one thing that must be deterministic, since
# it decides which renderer runs; everything about the CONTENT is left
# to the Brain.
_FORMAT_KEYWORDS = (
    (
        "pptx",
        (
            "powerpoint", "presentation", "slide deck", "slides", "slide",
            "slideshow", "pptx", "ppt",
        ),
    ),
    ("xlsx", ("excel", "spreadsheet", "workbook", "xlsx")),
    ("pdf", ("pdf",)),
)

_KIND_LABELS = {
    "pptx": "presentation",
    "xlsx": "spreadsheet",
    "pdf": "report",
    "docx": "report",
}


def infer_output_format(request_text: str, requested_output: str = "") -> str:
    """docx is the default - a generic written document is the common
    case, and always safe to open/edit further."""

    text = f"{requested_output} {request_text}".lower()
    for format_id, keywords in _FORMAT_KEYWORDS:
        if any(keyword in text for keyword in keywords):
            return format_id
    return "docx"


def _has_format_hint(text: str) -> bool:
    lowered = text.lower()
    return any(word in lowered for _, words in _FORMAT_KEYWORDS for word in words) or bool(
        re.search(r"\b(docx|word document)\b", lowered)
    )


def _derive_filename(request_text: str, output_format: str) -> str:
    words = re.findall(r"[A-Za-z0-9]+", request_text)[:8]
    stem = "_".join(words) if words else "document"
    return sanitize_filename(f"{stem}.{output_format}")


class GenerateDocumentTool:
    """Detects the requested file format, has the Brain author the
    content (reusing the exact M17 drafting assembly), renders it into
    real Office bytes, and stores it via FileStore. `composer` is
    injectable for tests; the default lazily constructs the real
    (Ollama-backed) composer and falls back to a plain honest draft if
    the model is unreachable - this tool never requires a running model
    to return a file."""

    def __init__(self, composer: Optional[DocumentComposer] = None, file_store: Optional[FileStore] = None):
        self._composer = composer
        self._file_store = file_store or FileStore()

    def generate(self, **kwargs) -> Dict[str, Any]:
        request_text = kwargs.get("request_text", "") or ""
        session_id = kwargs.get("session_id")
        decision_context = kwargs.get("decision_context") or {}
        requested_output = kwargs.get("requested_output", "") or ""
        proposed_format = kwargs.get("output_format")
        title = kwargs.get("title") if isinstance(kwargs.get("title"), str) else ""
        title = title.strip()
        theme = kwargs.get("theme", "modern")
        include_images = kwargs.get("include_images") is True
        image_queries = kwargs.get("image_queries") or []

        recent = decision_context.get("recent_conversation")
        fallback_request = request_text
        if proposed_format is None and not _has_format_hint(f"{requested_output} {request_text}") and isinstance(recent, list):
            for turn in reversed(recent[-5:]):
                prior_request = turn.get("user", "") if isinstance(turn, dict) else ""
                if isinstance(prior_request, str) and _has_format_hint(prior_request):
                    fallback_request = f"{prior_request} {request_text}"
                    break
        output_format = proposed_format if proposed_format in _MEDIA_TYPES else infer_output_format(fallback_request, requested_output)
        document_type = _KIND_LABELS.get(output_format, "report")
        composition_request = f"{title}\n{request_text}" if title else request_text

        rules = load_institutional_rules()
        policy_rules = extract_drafting_rules(read_text_file(POLICY_PATH))
        soul_text = read_text_file(SOUL_PATH)

        evidence = gather_session_evidence(session_id, self._file_store)
        if isinstance(decision_context.get("verified_evidence"), dict):
            evidence = {**decision_context["verified_evidence"], **evidence}
        if isinstance(recent, list):
            evidence["recent_conversation"] = [
                {"user": str(turn.get("user", ""))[:2000], "uri": str(turn.get("uri", ""))[:4000]}
                for turn in recent[-5:] if isinstance(turn, dict)
            ]

        preferences = {}
        if isinstance(decision_context.get("user_preferences"), dict):
            preferences = decision_context["user_preferences"]

        brief = build_drafting_brief(
            request_text=composition_request,
            requested_output=requested_output,
            document_type=document_type,
            evidence=evidence,
            preferences=preferences,
            institutional_rules=rules,
            policy_rules=policy_rules,
        )
        # Additive-only field document_composer.py reads to shape the
        # Brain's output for a non-prose format; never set for note/
        # order drafting, which is unaffected.
        brief["output_format"] = output_format

        principal = kwargs.get("principal") or decision_context.get("principal")
        composer = self._composer or DocumentComposer(principal=principal)
        result = composer.compose(
            brief=brief,
            request_text=composition_request,
            evidence=evidence,
            preferences=preferences,
            soul_text=soul_text,
            principal=principal,
        )
        body = result["body"]

        try:
            images = []
            image_diagnostics = {}
            if output_format == "pptx" and include_images:
                from uri_core.services.office_document_writer import find_openverse_images
                if not image_queries:
                    slide_titles = [line[2:].strip() for line in body.splitlines() if line.startswith("# ")]
                    image_queries = [f"{title} {slide}".strip() for slide in slide_titles[1:5]]
                    if not image_queries:
                        image_queries = [title or slide_titles[0]] if title or slide_titles else []
                images = find_openverse_images(image_queries, diagnostics=image_diagnostics)
            content_bytes = self._render(
                output_format, body, theme=theme, include_images=include_images,
                images=images,
            )
        except Exception as error:
            return {
                "status": "error",
                "message": f"URI could not render the {output_format.upper()} file.",
                "error": str(error),
            }

        filename = _derive_filename(title or request_text, output_format)

        try:
            record = self._file_store.save(
                filename=filename,
                content=content_bytes,
                media_type=_MEDIA_TYPES.get(output_format, "application/octet-stream"),
                session_id=session_id,
            )
        except FileValidationError as error:
            return {
                "status": "error",
                "message": "URI generated the document but could not store it.",
                "error": str(error),
            }

        image_note = None
        if output_format == "pptx" and include_images and not images:
            image_note = {
                "offline": "Image search was unavailable, so the presentation was created without photos.",
                "downloads_failed": "Licensed images were found, but their downloads failed; the presentation was created without photos.",
                "no_results": "Image search found no usable licensed images; the presentation was created without photos.",
            }.get(image_diagnostics.get("reason"), "Images could not be added; the presentation was created without photos.")

        return {
            # Propagates the composer's own honest status - "success"
            # only when the Brain actually authored the content actually
            # rendered into this file, "degraded" when a plain fallback
            # template was rendered instead. See docs/plans/
            # URI_NATIVE_TOOL_AUDIT.md Root Cause A.
            "status": result["status"],
            "file": record.to_reference(),
            "output_format": output_format,
            "composed_by": result["composed_by"],
            "detail": result.get("detail"),
            "preview": body[:500],
            "images_requested": include_images if output_format == "pptx" else False,
            "images_added": len(images) if output_format == "pptx" else 0,
            "image_note": image_note,
        }

    @staticmethod
    def _render(output_format: str, body: str, *, theme: str = "modern", include_images: bool = False, images=None) -> bytes:
        if output_format == "xlsx":
            return render_xlsx_bytes(body)
        if output_format == "pptx":
            return render_pptx_bytes(body, theme=theme, images=images or [])
        if output_format == "pdf":
            return render_pdf_bytes(body)
        return DocumentWriterService().render_docx_bytes(body)
