# Spike S11: print raster memory and spool size (O2P), 2026-10-15

Authority: owner decision OD-U13 (standing approval for automated tests with the existing Microsoft Print to PDF
virtual printer: synthetic documents, a dedicated temporary folder, no overwrite, no physical printing, no driver
install, no elevation, no dialogs, outputs checked and then removed).

Run: the print worker (`uri_office/workers/print_job.ps1`) inside a Job Object with a 1,536 MiB process limit, a
synthetic 3-page text PDF, fit to A4, to `Microsoft Print to PDF` with the output file set through the API (so no
Save dialog opened), in a new folder under `%TEMP%` (`uri_o2p_print_test_*`). All four runs exited 0 and wrote a
3-page PDF. The folder was then deleted, and `Get-PrintJob` showed 0 jobs left in the queue. Full numbers in
`s11_result.json`.

| Resolution | Peak process memory (Job Object) | Time | Output per page |
|---|---|---|---|
| 300 dpi | 221–253 MB | about 3.9 s for 3 pages (including PowerShell start-up) | about 136 KB |
| 600 dpi | 497–621 MB | about 5.5 s | about 524 KB |

Decisions taken from this (recorded in `uri_office/printing.py`):
- Default resolution **300 dpi**; 600 dpi on request.
- Job Object limit for the print worker **1,536 MiB** (2.5 times the 600 dpi peak).
- Per-job spool budget: **300 pages at 300 dpi, 100 pages at 600 dpi**, counting copies. A larger job is refused with
  "Print fewer pages at a time".

What this does not show:
- **Physical printer spool size, memory and timing: NOT VERIFIED.** A real driver can spool very differently from the
  virtual PDF printer. No physical printer is installed on this PC.
- Colour against black and white: the virtual printer wrote the same size for both; its colour setting does not show
  in the output. The setting is passed to the driver as approved.
- A real document with images or many pages was not measured here (synthetic text only).
- Visual check: the printed page 1 was rendered back with Windows.Data.Pdf and inspected: the text appears on an A4
  page, scaled to fit the printable area.
