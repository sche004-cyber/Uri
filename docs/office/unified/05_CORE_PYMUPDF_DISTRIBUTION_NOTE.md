# Core PyMuPDF dependency: note for a future distribution review (OD-U14)

Date: 2026-10-15. Status: **recorded for a separate future review. No change is authorized or made.**

## Facts (checked in source at `fb8fa084`, which carries Core unchanged from `5b958da0`)

| Item | Evidence |
|---|---|
| Core imports PyMuPDF | `uri_core/services/pdf_reader.py:4` (`import fitz`), PDF text extraction and an OCR fallback that renders pages at 2x (`:91`) |
| Core imports PyMuPDF to write PDFs | `uri_core/services/office_document_writer.py:28` (`import fitz`), `:137` A4 page rect, `:146` new document |
| Declared dependency | `requirements.txt:23` `pymupdf>=1.24` (comment at `:18-22` says it was used before it was declared) |
| Installed version on this PC | PyMuPDF 1.28.2 (MuPDF 1.28.2), from `import fitz` on 2026-10-15 |
| Office independence | URI Office (O2 onward) does not import `fitz` or `pymupdf`. AC-O2-22 enforces it with a test. Office never calls `pdf_reader.py` or `office_document_writer.py`. |

## Licensing consideration (not legal advice)

PyMuPDF and MuPDF are offered under the GNU AGPL v3, or under a commercial licence from Artifex. AGPL obligations can
apply when software that includes the library is **distributed**, or when users interact with it **over a network**.
URI today runs on the owner's own PC for the owner's own use. Whether that triggers any obligation, and what a future
distribution (installer, other users, a hosted service) would require, is for the owner's distribution review, not
for this programme.

## Options for that review (none chosen)

1. Keep PyMuPDF in Core and meet the AGPL terms for any distribution (source offer for the combined work).
2. Buy an Artifex commercial licence.
3. Replace Core's PyMuPDF use. The Office programme already measured permissive alternatives on this PC:
   Windows.Data.Pdf (built into Windows) for page images, pypdf (BSD) for text, and Tesseract for OCR
   (`03_O2_AMENDMENT_A1_PDF_PRINT_DEVICES.md` §A2). Writing PDFs (`office_document_writer.py`) would need another
   path, for example LibreOffice export or a permissive PDF writer. Replacing Core code needs the frozen-Core
   authorization.

## What this note does not do

It does not change Core, `requirements.txt` or any frozen path, and it does not widen O2's scope.
