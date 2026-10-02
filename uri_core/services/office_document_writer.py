"""M19: renders Brain-composed text into XLSX/PPTX/PDF bytes.

Mirrors document_writer_service.py's DOCX discipline exactly - pure
rendering, no reasoning, no reasoning about content, never writes to
disk itself (the caller, generate_document.py, hands the returned
bytes to FileStore, the one containment-checked/validated place a
generated file is stored). Reuses libraries already in this
repository's dependency set (openpyxl, already used for reading
spreadsheets; pymupdf/fitz, already used for reading PDFs) rather than
adding a new PDF-writing library.

Content shape the Brain is asked to produce (see generate_document.py's
prompt) and these functions parse:
  - XLSX: the same "|cell|cell|" markdown table syntax
    document_writer_service.py already parses for DOCX tables - the
    first row is treated as a header row.
  - PPTX: "# Slide Title" markdown headings, one per slide, with each
    following non-empty line becoming one bullet on that slide.
  - PDF: plain paragraphs, paginated by a generous line budget.
"""

import io
import ipaddress
from typing import List
from urllib.parse import urlparse

import requests
from PIL import Image

from openpyxl import Workbook
from openpyxl.styles import Font
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.util import Inches, Pt
import fitz


def _parse_markdown_table(text: str) -> List[List[str]]:
    """The same "|cell|cell|" parsing document_writer_service.py's
    _build_document already applies for DOCX tables, extracted here so
    both DOCX and XLSX rendering read identical table syntax the Brain
    was given identical instructions to produce. Returns every row
    found across the whole text (a document with more than one table is
    flattened into one sheet - deliberately simple, matching the scope
    of a single generated spreadsheet)."""

    rows: List[List[str]] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        if "---" in stripped:
            continue
        cells = [cell.strip() for cell in stripped.split("|")[1:-1]]
        rows.append(cells)
    return rows


def render_xlsx_bytes(content: str) -> bytes:
    """Renders markdown-table rows into a real .xlsx workbook (first
    row as header, bold). When the Brain's output contains no table at
    all, each non-empty line becomes one cell in column A instead of
    failing outright - a plain but honest spreadsheet rather than no
    file."""

    rows = _parse_markdown_table(content)

    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"

    if rows:
        for row_index, row in enumerate(rows, start=1):
            for col_index, value in enumerate(row, start=1):
                cell = sheet.cell(row=row_index, column=col_index, value=value)
                if row_index == 1:
                    cell.font = Font(bold=True)
    else:
        for row_index, line in enumerate(
            (line.strip() for line in content.split("\n") if line.strip()),
            start=1,
        ):
            sheet.cell(row=row_index, column=1, value=line)

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


_THEMES = {
    "modern": (RGBColor(16, 36, 62), RGBColor(24, 153, 184), RGBColor(244, 248, 250)),
    "academic": (RGBColor(24, 52, 84), RGBColor(185, 132, 57), RGBColor(249, 247, 241)),
    "warm": (RGBColor(79, 48, 65), RGBColor(214, 113, 91), RGBColor(252, 247, 243)),
}


def _safe_image_url(url: str) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return False
    try:
        port = parsed.port
    except ValueError:
        return False
    if port not in {None, 443}:
        return False
    try:
        ipaddress.ip_address(parsed.hostname)
    except ValueError:
        # Hostnames are allowed; literal IP addresses are not.
        return True
    return False


def _download_image(url: str) -> bytes:
    if not _safe_image_url(url):
        raise ValueError("Unsafe image URL")
    with requests.get(url, stream=True, timeout=6, allow_redirects=True) as download:
        if len(download.history) > 3 or not all(
            _safe_image_url(hop.url) for hop in [*download.history, download]
        ):
            raise ValueError("Unsafe image redirect")
        download.raise_for_status()
        if not download.headers.get("Content-Type", "").lower().startswith("image/"):
            raise ValueError("Response is not an image")
        data = bytearray()
        for chunk in download.iter_content(65536):
            data.extend(chunk)
            if len(data) > 5_000_000:
                raise ValueError("Image exceeds 5 MB")
    with Image.open(io.BytesIO(data)) as image:
        image.verify()
    return bytes(data)


def find_openverse_images(queries: List[str], *, diagnostics: dict = None) -> List[dict]:
    """Best-effort CC photo retrieval, with an optional plain-language failure reason."""
    images = []
    search_failed = False
    search_succeeded = False
    download_failed = False
    for query in queries[:4]:
        if len(images) >= 4:
            break
        if not isinstance(query, str) or not query.strip():
            continue
        try:
            response = requests.get(
                "https://api.openverse.org/v1/images/",
                params={"q": query[:120], "page_size": 5, "license_type": "commercial"},
                timeout=5,
            )
            response.raise_for_status()
            results = response.json().get("results", [])[:5]
            search_succeeded = True
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError, AttributeError):
            search_failed = True
            continue
        for item in results:
            try:
                if item.get("license", "").lower() not in {"cc0", "by", "by-sa"}:
                    continue
                url = item.get("url")
                embedded_data = None
                for candidate in (item.get("thumbnail"), url):
                    try:
                        embedded_data = _download_image(candidate)
                        break
                    except (requests.RequestException, OSError, ValueError, TypeError, SyntaxError):
                        download_failed = True
                if embedded_data is None:
                    continue
                images.append({
                    "data": embedded_data,
                    "credit": f"{item.get('title') or 'Image'} — {item.get('creator') or 'Unknown creator'}; "
                              f"{item.get('license', '').upper()} {item.get('license_version') or ''}; "
                              f"{item.get('foreign_landing_url') or url}; "
                              f"{item.get('license_url') or ''}",
                })
                break
            except (ValueError, TypeError, AttributeError):
                continue
    if diagnostics is not None:
        diagnostics["reason"] = (
            "downloads_failed" if download_failed else
            "offline" if search_failed and not search_succeeded else "no_results"
        ) if not images else None
    return images


def _text_box(slide, x, y, width, height, text, *, size, color, bold=False):
    box = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(height))
    frame = box.text_frame
    frame.word_wrap = True
    paragraph = frame.paragraphs[0]
    paragraph.text = text
    paragraph.font.name = "Aptos"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = bold
    paragraph.font.color.rgb = color
    return box


def render_pptx_bytes(content: str, *, theme: str = "modern", images: List[dict] = None) -> bytes:
    """Renders "# Slide Title" sections into real presentation slides -
    each subsequent non-empty, non-heading line becomes one bullet on
    that slide. Content with no "# " headings at all becomes a single
    slide (title from the first non-empty line, the rest as bullets),
    so a Brain response that forgot the heading syntax still produces a
    real presentation rather than an empty one."""

    presentation = Presentation()
    presentation.slide_width = Inches(13.333)
    presentation.slide_height = Inches(7.5)
    title_color, accent, background = _THEMES.get(theme, _THEMES["modern"])
    images = images or []

    slides: List[tuple] = []
    current_title = None
    current_bullets: List[str] = []

    def _flush():
        if current_title is not None or current_bullets:
            slides.append((current_title or "Untitled slide", list(current_bullets)))

    for raw_line in content.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            _flush()
            current_title = line[2:].strip()
            current_bullets = []
        else:
            bullet = line[2:].strip() if line.startswith("- ") else line
            current_bullets.append(bullet)
    _flush()

    if not slides:
        slides = [("Untitled presentation", [])]

    used_credits = []
    for number, (title, bullets) in enumerate(slides, start=1):
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        fill = slide.background.fill
        fill.solid()
        fill.fore_color.rgb = title_color if number == 1 else background
        ink = RGBColor(255, 255, 255) if number == 1 else title_color
        bar = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(0.13), presentation.slide_height)
        bar.fill.solid()
        bar.fill.fore_color.rgb = accent
        bar.line.fill.background()
        # Native vector motif: editable and sharp at any display size.
        for offset in (0, 0.19, 0.38):
            icon = slide.shapes.add_shape(
                MSO_SHAPE.OVAL, Inches(11.1 + offset), Inches(0.68),
                Inches(0.23), Inches(0.23),
            )
            icon.fill.solid()
            icon.fill.fore_color.rgb = accent
            icon.line.fill.background()
        _text_box(slide, 0.7, 0.6 if number == 1 else 0.45, 11.7, 1.2, title,
                  size=36 if number == 1 else 30, color=ink, bold=True)
        picture = images[number - 2] if number > 1 and number - 2 < len(images) else None
        content_width = 7.5 if picture else 11.5
        for index, bullet in enumerate(bullets[:7]):
            _text_box(slide, 0.85, 2.05 + index * 0.66, content_width, 0.59,
                      "• " + bullet, size=20, color=ink)
        if picture:
            try:
                stream = io.BytesIO(picture["data"]) if "data" in picture else picture["path"]
                slide.shapes.add_picture(stream, Inches(8.75), Inches(2.05), width=Inches(3.8))
                if picture.get("credit"):
                    used_credits.append(str(picture["credit"]))
            except (KeyError, ValueError, OSError):
                pass
        _text_box(slide, 11.75, 7.05, 0.9, 0.25, str(number), size=11, color=ink)

    if used_credits:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        slide.background.fill.solid()
        slide.background.fill.fore_color.rgb = background
        _text_box(slide, 0.7, 0.5, 11.6, 0.8, "Image credits", size=30, color=title_color, bold=True)
        for index, credit in enumerate(used_credits[:6]):
            _text_box(slide, 0.85, 1.6 + index * 0.83, 11.7, 0.76,
                      credit, size=13, color=title_color)

    buffer = io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


# Rough character budget per PDF page - generous enough for a normal
# paragraph-per-page administrative document; a page that would overflow
# it simply continues onto the next page rather than being truncated.
_PDF_CHARS_PER_PAGE = 2800
_PDF_PAGE_RECT = fitz.paper_rect("a4")
_PDF_MARGIN = 50


def render_pdf_bytes(content: str) -> bytes:
    """Renders plain text into a real, paginated PDF using pymupdf -
    already a dependency of this repository for PDF *reading*, reused
    here for writing rather than adding a new PDF library."""

    document = fitz.open()
    paragraphs = content.split("\n")

    page = None
    text_box = None
    consumed = 0

    def _new_page():
        nonlocal page, text_box, consumed
        page = document.new_page(width=_PDF_PAGE_RECT.width, height=_PDF_PAGE_RECT.height)
        text_box = fitz.Rect(
            _PDF_MARGIN,
            _PDF_MARGIN,
            _PDF_PAGE_RECT.width - _PDF_MARGIN,
            _PDF_PAGE_RECT.height - _PDF_MARGIN,
        )
        consumed = 0

    _new_page()
    buffer_text = ""

    for paragraph in paragraphs:
        candidate = f"{buffer_text}\n{paragraph}" if buffer_text else paragraph
        if len(candidate) - consumed > _PDF_CHARS_PER_PAGE:
            page.insert_textbox(text_box, buffer_text, fontsize=11, fontname="helv")
            consumed += len(buffer_text)
            _new_page()
            buffer_text = paragraph
        else:
            buffer_text = candidate

    if buffer_text:
        page.insert_textbox(text_box, buffer_text, fontsize=11, fontname="helv")

    data = document.tobytes()
    document.close()
    return data
