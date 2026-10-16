# O2 day-1 spikes, 2026-10-15 (G1 active)

Run: `python -I spikes.py %LOCALAPPDATA%\Temp\uri_o2_spikes`, 10:00:55 to 10:03:33 +0530, exit 0. Full output:
`spikes_result.json`.
- Nothing was installed or printed.
- PyMuPDF was not imported (`pymupdf_imported: false`).
- The first attempt exited 1, because the S7 bridge produced no rows. That failure is the S1 finding below. The script
  was then fixed and re-run.

| Spike | Result | Plan consequence |
|---|---|---|
| S1: `uno` under `-I` | **Plain `-I` fails** (`ModuleNotFoundError: No module named 'uno'`; LibreOffice's python finds uno only through its environment). **The fallback works:** `-I`, plus `bridge_isolated.py`, which adds only the integrity-checked LibreOffice `program` folder to `sys.path`. A 25-section DOCX converted in 2.06 s. | `lo_bridge.py` runs as `python.exe -I <run copy of the bridge>`. The bridge adds the program folder itself. No `PYTHONPATH`, user site or current-directory imports. |
| S3: ctypes Job Object | Assignment succeeded with no pywin32. On closing the job, `soffice.com` and its one child left **0** processes alive. | Selected as planned |
| S4: persistent re-seeded profile | First result at 5.7 s from a cold start with a persistent profile, against 13.35 s with a fresh profile | AC-O2-3 start-up ≤ 15 s is met, with margin |
| S6: engine manifest | Full tree: 19,458 files, 1.60 GB, **107 s**. Executables and DLLs (244 files, `.exe`/`.dll`/`.com`/`.bin`/`.pyd`): **4.3 s** | **Change:** a full-tree check at service start is too slow. The full manifest is checked when the engine is first qualified and from a manual "Verify engine" diagnostic. At service start there is a fast check of the file list, sizes and modification times. Executables, DLLs, `python.exe` and the bridge's Python library files are hashed at every engine launch (about 4.3 s, so launch ≈ 4.3 + 5.7 s ≈ 10 s, still within 15 s). The engine is pre-started when the owner opens a document. A same-user attacker who keeps sizes and times unchanged is the residual risk, as for every same-user process (R11). |
| S7: listener timing | 37-page DOCX: median 0.71 s (bridge-reported), 0.85 s wall including bridge start. 60-page DOCX: 0.77 s and 0.91 s. 5 runs each. | AC-O2-3 warm ≤ 2 s is met. U12 thresholds stay. |
| S9: pypdf positions and sizes | 37 spans on page 1, with the start of each line. Sizes read correctly (11 and 14 pt); y from 97.9 to 682.4 on a 612×792 page. **No line widths:** `x_range` is the left start only. | Minimum font size, and top, bottom and left overflow, use pypdf. **Right-edge overflow uses the WinRT edge-ink check** (labelled weaker). |
| S10: language mode | `FullLanguage`. Constrained Language Mode is not active on this PC. | The CLM check stays as a start-up guard |
| S10: malformed corpus in a Job Object (1.5 GB limit) | Truncated, garbage, zero-byte and deep-nesting PDFs each **failed cleanly**: rc 1, 1.4–1.7 s, 66 MB peak, no PNG. A valid 60-page PDF rendered all 60 pages at 1240 px in 4.1 s, 144 MB peak. | AC-O2-20 behaviour is confirmed for the worker. The service maps rc ≠ 0 to "Preview unavailable". |
| S10: WinRT-raster OCR at 300 dpi | 2-page scan: rasterized in 1.81 s wall (including PowerShell start-up). Tesseract took 616 ms and 534 ms per page, and the text was read correctly. | The O4 OCR path is confirmed |

Not run today:
- **S2** (live WebView2 overlay) needs the built UI.
- **S5** (per-call against listener pixel parity) moves to WS-A setup.
- **S8** (Brain host prompt logging) is already mitigated by sending no file names or titles.
- **S11** (print raster spool) needs OD-U13 to target a printer. Its memory-only part can run without printing.
