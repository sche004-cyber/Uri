# LibreOffice headless probe, 2026-10-15

- Package: LibreOffice 26.8.1.1 (MPL-2.0), official MSI from download.documentfoundation.org through winget. Its SHA-256 matches the winget manifest (`installer_sha256.txt`).
- Install method: the owner approved the install (OD-U2). Both elevated installs ended without installing. The first `winget` run exited with code 255 while a UAC prompt stayed open. The second elevated `msiexec` returned "The operation was canceled by the user".
- What was used instead: an administrative extract (`msiexec /a ... TARGETDIR=%LOCALAPPDATA%\URI\engines\libreoffice-26.8.1`). It needs no admin rights, makes no system-wide install and adds no registry install entries.
- Microsoft VC++ x64 runtime 14.51 was already present.
- Every conversion used a fresh private profile (`-env:UserInstallation`), `--headless`, `--norestore` and `--nolockcheck`.
- Results:
  - `lo_probe_result_rerun.json` (second run);
  - first run: DOCX cold 26.5 s / 418 MB peak RSS; DOCX warm 7.6 s / 361 MB; PPTX 11 slides 7.4 s / 369 MB.
- Fidelity, checked visually in `lo_order_p1.png` and `lo_deck_chart_slide.png`: the header, centred heading, 41-row table, PAGE field footer and native chart all render. Compare this with the PyMuPDF base renders in `../engine_probe_20261014/`.
- Quality finding for O5: python-pptx's default chart value axis does not start at zero (12.4 to 14.2). This exaggerates small differences. The O5 validator must check it.
- Stderr line `Could not find platform independent libraries <prefix>`: comes from LibreOffice's bundled Python in the extracted layout. Conversion is unaffected (rc 0). Not investigated further.
- Design consequence: a process per conversion costs 7–26 s. O2 must measure a persistent listener (`soffice --accept` / UNO) against per-call conversion before freeze.
