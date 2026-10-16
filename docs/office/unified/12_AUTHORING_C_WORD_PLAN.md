# Office authoring, milestone C (Word structured creation and editing): plan and acceptance criteria

Owner decisions: OD-A1 (structured editing with python-docx, LibreOffice preview, existing services and approvals; no
new editor framework or server), OD-A3 (order A, B, then C), OD-A4 (isolated branch; rebased on the integrated
baseline before qualification), OD-A5 (templates: blank, existing documents, the owner's templates, built-in
layouts). Branch `milestone/office-authoring-c-word-20261016`, from the A/B tip `16e040e7`.

## 1. What is reused (milestone A)

The authoring session (`uri_office/authoring/session.py`) unchanged in behaviour: working copy from the original's
exact bytes through the edit's own open grant, ordered change list in plain words, undo/redo with count and memory
caps, preview of the working copy through `Documents.open_bytes` (LibreOffice render), the hash-bound save card
(`Approvals.propose_authoring_save`), Save (backup first, refused when the file changed on disk) and Save as (never
replaces; the edit continues on the new file), the `/authoring/*` routes. Milestone C makes the session dispatch by
kind (`pptx` to `pptx_ops`, `docx` to `docx_ops`) and adds `POST /authoring/new` with `kind: "docx"`.

## 2. Addresses

Word body blocks have no stable ids. A block is addressed by its index among the body's paragraphs and tables
(`block`), and every op that names a block also carries `expect`: the first 12 hex characters of the SHA-256 of that
block's text as the last view showed it. A mismatch is refused (`STALE_BLOCK`), so an op never lands on a block
that moved. The UI always sends ops against the latest view.

## 3. Closed op set (docx_ops)

| Op | Address | Behaviour |
|---|---|---|
| `insert_paragraph` | `after` (block or null = start), `text`, optional `style` | new paragraph; style from the document's paragraph styles |
| `set_paragraph_text` | block | replaces the text; keeps the first run's formatting |
| `delete_block` | block | paragraph or table; refused for a paragraph that carries a section break |
| `move_block` | block, `to` | reorder body blocks (section-break paragraphs refused) |
| `set_style` | block, style name | paragraph styles that exist in the document only |
| `format_text` | block, bold / italic / underline / size / colour / alignment | whole paragraph's runs |
| `insert_table` | `after`, cell texts (1..20 x 1..20) | the document's "Table Grid" style when present |
| `set_table_cell` | table block, row, col, text | |
| `add_table_row` / `delete_table_row` | table block, row | |
| `insert_image` | `after`, picked image (grant kind `image`, used once), width as a fraction of the text width | inline picture |
| `insert_page_break` | `after` | |
| `set_header_text` / `set_footer_text` | text | first section; a linked header is unlinked first |
| `insert_page_number` | `where` header or footer, alignment | PAGE field |
| `set_page_setup` | orientation, margins in cm | every section |
| `replace_text` | `find`, `replace`, `match_case` | replaces matches that lie inside one run (formatting kept); matches split across runs are counted and named, not changed |

Content URI does not own (comments, tracked changes, content controls, fields other than the page number it adds,
embedded objects, footnotes) is kept byte-identical; an op that would need to change it is refused with a named
reason (`AUTHORING_NOT_SUPPORTED`). Tracked-change drafting and comparison are milestone D/E.

## 4. New documents (OD-A5)

`POST /authoring/new {kind: "docx", template?: <built-in id>, template_path?: <owner's .docx/.dotx>}`. Built-in
layouts made by code, A4 with 2.54 cm margins: Blank, Letter, Office order, Notice, Memo, Minutes of a meeting,
Report. Each is a few headings and placeholder paragraphs in the document's own styles, so the owner replaces the
words; nothing is pre-filled with names, numbers or dates. A .dotx is converted to a document (main part content
type), its styles, headers and page setup kept.

## 5. UI

The Office document view gains Edit for a .docx (and New document on Office Home, with the built-in layouts and
"from a template"). Same editor frame as PowerPoint: left = block list (headings indented, tables and pictures named),
centre = preview pages of the working copy, right = the selected block's editor (text with Apply, style menu,
formatting, table cells, insert after: paragraph, table, picture, page break; delete, move up/down), plus a Page
section (header, footer, page numbers, orientation, margins) and Find and replace. Top bar and states as milestone B.

## 6. Acceptance criteria

| ID | Criterion | Evidence |
|---|---|---|
| C-1 | Working copy byte-identical to the original at start; the original written only through an approved Save | tests (hash) |
| C-2 | Every op in section 3 works on synthetic fixtures (letter with header/footer, report with tables and a picture, a document with comments and tracked changes) and the result reopens in python-docx and converts in LibreOffice | unit + real-engine tests |
| C-3 | Untouched parts stay byte-identical (comments, footnotes, media, numbering, theme) after any op set | part-hash tests |
| C-4 | A stale address is refused (`STALE_BLOCK`), never applied to another block | tests |
| C-5 | Undo/redo restore the exact earlier working copy; the save card lists every change in plain words | tests |
| C-6 | Built-in layouts and the owner's .dotx produce documents that open, render and save | tests + real engine |
| C-7 | Unsupported content is refused with a named reason, never half-done | tests |
| C-8 | Real app: new from a layout and from a template; edit text, style, table, picture, header/footer, page number, page setup, find and replace; Save as; reopen; PDF; undo; leave with unsaved; refused op | Stage 8 live journeys |
| C-9 | Independent review ACCEPT (or AwF) on the exact commit; gates pass | driver receipt |

Not in C: Brain-assisted drafting and rewriting (D), tracked-change drafts and comparison (D/E), comments, mail
merge, LibreOffice hand-off (OD-A2), printing (O2P).
