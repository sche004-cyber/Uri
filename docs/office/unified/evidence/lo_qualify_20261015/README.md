# LibreOffice pre-freeze qualification probe, 2026-10-15

This is research evidence for the O2 plan. It is not product code and not a phase qualification.

- Run: 2026-10-15 08:21–08:23 +0530 on the owner's Windows 11 PC (`environment.txt`).
- Command: `python -I lo_qualify.py %LOCALAPPDATA%\Temp\uri_lo_qualify_out`. Exit 0; full output in `lo_qualify_result.json`.
- Engine: `%LOCALAPPDATA%\URI\engines\libreoffice-26.8.1\program\soffice.com`.
  - Version: `LibreOffice 26.8.1.1 bf6ef2662401c7d6dce671ab4deb26ee0af3a7c1`.
  - `soffice.bin` SHA-256: `cb08cffd…2fa1`.
  - This is the same user-folder extract as `../libreoffice_probe_20261015/`.
- Conditions: no installer, no elevation, no UAC prompt. Every run used a fresh private profile in `%TEMP%`. All fixtures are synthetic.

## Results

| Check | Result |
|---|---|
| Per-call conversion (hardened profile) | DOCX: 18.4 s cold, 6.1 s warm. PPTX (11 slides): 6.5 s and 5.7 s. Peak tree RSS 345–356 MB. rc 0 for every call. |
| Persistent listener (`--accept=pipe` plus a UNO client in LibreOffice's own `python.exe`) | Start-up to first result about 10.6 s. First DOCX 1.31 s. Warm DOCX 0.36 s (twice). PPTX 0.53 s, then 0.42 s. Peak tree RSS 409 MB. Idle RSS after the calls 390 MB. |
| Fidelity | `per_call_order_p1.png` shows the header, the centred heading, the 41-row grid table and the PAGE field footer. `listener_deck_chart.png` shows the native chart. Page counts: order 1, deck 11, the same in both modes. **Not checked:** a pixel comparison between per-call and listener output. |
| Job Object (`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`) | `soffice.com` plus 1 child (`soffice.bin`) were running. Closing the job left **0** processes alive. |
| External-link canary, **default** private profile | **The canary was fetched** (`GET /canary.png`) in both per-call and listener mode. A DOCX with an external linked image makes LibreOffice open a network connection by default. |
| External-link canary, **hardened** profile | **0** fetches in both modes. |

The hardened profile is the `HARDENED_XCU` text in `lo_qualify.py`. It sets these values:
- macro security level 3, and macro execution disabled;
- `BlockUntrustedRefererLinks` true;
- manual proxy `127.0.0.1:9`, with an empty no-proxy list;
- OpenCL off;
- usage collection off.

## Consequences for the O2 plan

1. **Use a persistent listener, not one process per call.**
   - A warm conversion is about 17 times faster (0.36 s against 6.1 s).
   - The cost is about 390 MB resident while the listener is up.
   - Start it on demand, and stop it after an idle timeout.
2. **The default profile is not safe for untrusted documents.** O2 must:
   - always use the hardened profile;
   - prove it with the canary on every qualification run;
   - remove external relationships from the copy it renders (defence in depth).

   This probe does not show which single setting stopped the fetch, so all of them stay.
3. **Not covered by this probe.** These are O2 test items:
   - other external-reference types: `INCLUDETEXT` / `INCLUDEPICTURE` fields, OLE links, `altChunk`, PPTX linked media, hyperlinks;
   - documents with macros;
   - a crash or hang during conversion;
   - running two clients at the same time;
   - UNC paths (`\\host\share`) as link targets, which could leak NTLM credentials.
