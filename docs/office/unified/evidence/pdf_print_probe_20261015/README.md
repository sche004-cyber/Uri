# PDF engine and printer discovery probe, 2026-10-15 (amendment A1 research)

This is research evidence only. Nothing was installed, nothing was printed, and no setting was changed. PyMuPDF was not
imported (`pdf_print_probe_result.json`, `"pymupdf_imported": false`).

| Step | Command | Result |
|---|---|---|
| LibreOffice listener (hardened profile, Job Object): PDF and per-page PNG | `python -I pdf_print_probe.py %LOCALAPPDATA%\Temp\uri_pdf_print_probe` | The DOCX (10 pages; named `report20` but 10 pages long), PPTX (11 slides) and XLSX all became PDFs. Warm DOCX→PDF took 0.07 s. **Writer per-page PNG ignores `PageRange`:** every page PNG is page 1 (`lo_writer_png_pagerange2_is_page1.png`, identical hashes). Impress per-slide PNG works (`lo_impress_png_slide11.png`). |
| pypdf (BSD-3) | same script | Text, outline, fonts and search work. The 10-page extraction took 279 ms. On the scanned PDF, the page images were extracted and Tesseract read them correctly (554 ms and 223 ms). |
| Windows.Data.Pdf (built into Windows) | `powershell -NoProfile -ExecutionPolicy Bypass -File winrt_pdf_render.ps1 <pdf> <out> 900` | 10 pages: open 159 ms, first page 169 ms, then 27 ms per page. Wall time 1.97 s including PowerShell start-up. All pages distinct. Fidelity is good (`winrt_report20_p6.png`). |
| Printers: winspool, read-only | same Python script | 2 printers, both virtual: "Microsoft Print to PDF" (default, `PORTPROMPT:`) and "OneNote (Desktop)" (`nul:`). Capabilities were read in 167 ms. **No physical printer is installed.** |
| Printers: .NET `PrinterSettings`, read-only | `printer_caps.ps1` | Same 2 printers. It reports duplex, colour, copies, paper sizes and resolutions. Took 934 ms. |
| Spooler and PnP | `Get-Service Spooler`; `Get-PnpDevice -Class PrintQueue` | Spooler is running (automatic start). Only print queues are present. The command exited 1 because the `Printer` device class has no devices. |

Consequences: see `../../03_O2_AMENDMENT_A1_PDF_PRINT_DEVICES.md`, sections A2 and A6.
