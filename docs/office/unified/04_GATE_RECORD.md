# URI Office Unified: gate record

Append-only. Each entry names its evidence. A gate is recorded only when its stated conditions are met.

## 2026-10-15: G0 (plan approval) effective; G1 and G1P (O2 and O2P implementation) activated

**Owner instruction** (chat, 2026-10-15, "O2 Plan Amendment & Conditional G0/G1 Approval"), quoted:
- "Treat this instruction as conditional approval of G0 and G1".
- "If the revised plan receives independent acceptance and licensing issues are resolved, record G0 approval. Only
  then activate G1 and begin isolated O2 implementation."

| Condition | Evidence | Met |
|---|---|---|
| Amend the O2 plan and record the PDF and printing decisions | `03_O2_AMENDMENT_A1_PDF_PRINT_DEVICES.md` (rev 3); 01 rev 4 header; 00 §12a row D-PDF | yes |
| Evaluate licensing and architecture | A1 §A2, §A4–A7; evidence `evidence/pdf_print_probe_20261015/` | yes |
| Update acceptance criteria, risks and dependencies | A1 §A3, §A8, §A9, §A11 | yes |
| Commit in the isolated planning branch | `phase/uri-office-unified-plan` @ `1d5c0695` (local only) | yes |
| Independent review of the amendments and their interactions | `02_O2_INDEPENDENT_REVIEW.md`. The O2 plan had three rounds, ending ACCEPT WITH FINDINGS at `d54f8905`. A1: REVISE, then **ACCEPT WITH FINDINGS** at `abb6fc99`. Its residuals were repaired at `1d5c0695`. | yes |
| Licensing resolved | Reviewer: "Licensing is resolved." PyMuPDF is removed from Office; there is no new dependency and no install. AC-O2-22 enforces the no-import rule. | yes |

**G0 is effective. G1 (O2) and G1P (O2P) are activated.** The owner's limits still apply in full:
- no installation, elevation, real printing, canonical integration, push or deployment;
- no protected path;
- no change to accepted M1/M2 behaviour, except the mechanical edits listed in rev 3.1 §5.1 that keep behaviour the same;
- OD-U12 and OD-U13 gate only O2P rows PR-5 and PR-6 and the printer-backed part of S11.

Implementation branches, cut from the plan tip `1d5c0695`, which is `5b958da0` plus planning documents only (no code):
- integration branch `phase/uri-office-u-2`;
- workstream sub-branch `phase/uri-office-u-2-a`, worktree `C:\Users\cheta\Development\uri-office-u2-a`.

The plan said to branch from `5b958da0`. Cutting from the plan tip instead carries the frozen plan with the code. The
code base is identical.

Still open (owner):
- OD-U3b (pypdfium2 install, fallback only);
- OD-U11 (PDF tables);
- OD-U12 (meaning of "harness");
- OD-U13 (virtual-printer test jobs);
- OD-U14 (Core PyMuPDF awareness);
- OD-U15 (repair of the Excel save gap);
- OD-U4 (Google scopes);
- the GPU window, the owner live check and physical-print authorization;
- G5, G6 and G7.
