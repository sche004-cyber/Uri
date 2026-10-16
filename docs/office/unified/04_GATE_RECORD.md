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

## 2026-10-15: owner decisions OD-U11, OD-U12, OD-U13, OD-U14, OD-U15; O2 implementation continues under G1

**Owner instruction** (chat, 2026-10-15, "O2 IMPLEMENTATION — OWNER DECISIONS AND DEVELOPMENT AUTHORIZATION"). The
decisions are recorded as the owner stated them. Quotes are short; the full text is in the chat.

| Decision | Ruling | Effect on the plan |
|---|---|---|
| OD-U13 virtual printing | **APPROVED**, narrowly scoped and standing: "automated print testing using the existing Microsoft Print to PDF virtual printer". Conditions: synthetic documents only; a dedicated temporary test folder; no overwrite of existing files; no physical printing; no driver install; no elevation or system configuration change; no unwanted print dialogs or unattended operations outside the test scope; validate real output files and print results; clean up safely. | Unblocks A8 row PR-5 and the printer-backed part of spike S11. Physical printing (PR-6 to PR-9) still needs separate owner authorization. Virtual printing never counts as physical qualification; O2P stays **PARTIAL** without a physical printer. |
| OD-U12 harness | **APPROVED WITH REFINEMENT.** Printer discovery and printing go through URI's existing application and service layer. No frozen Core change and no new agent-runner architecture. Design a **reusable capability interface** that can later be registered with the Brain and wider orchestration. Reuse the existing approval and permission mechanisms; no separate authorization system. Scanners stay architecturally possible but out of scope. | A6 stands. Added: `uri_devices/capability.py` exposes printing as a plain, transport-free capability descriptor (id, inputs, effects, approval kind) that the Office service routes call today and that a future Core registration could wrap without a redesign. No Core descriptor is written now. |
| OD-U11 PDF tables | **RETAIN AS DEFERRED.** Keep PDF tables → Excel in the roadmap. Install nothing. First investigate whether existing engines or lightweight deterministic methods can extract tables reliably (accuracy, layout, licensing, performance, complexity). Must not block O2. | O7/O4 row stays. A table-extraction investigation (pypdf text positions plus a deterministic column/row clustering) is a separate research item, not an O2 acceptance criterion. |
| OD-U15 Excel save safety | **SCOPED REPAIR APPROVED.** Separate isolated branch and worktree. Inspect the exact accepted Excel baseline. Atomic no-clobber save. Keep legitimate save behaviour. Verify real-path and symlink protection. Test concurrent destination creation, interrupted saves and recovery, and source integrity. Full relevant Excel regressions. Independent exact-commit acceptance. No unrelated Excel changes. No automatic merge into O2 or canonical. | Repair branch `repair/uri-office-xlsx-save-noclobber`, cut from the accepted Excel baseline `5b958da0`, in its own worktree. Not merged anywhere without the integration gate. |
| OD-U14 Core PyMuPDF | **ACKNOWLEDGED.** No Core change. Office stays independent of PyMuPDF (AC-O2-22). Record Core's licensing considerations for a separate future distribution review. Do not expand O2 scope. | Recorded in `05_CORE_PYMUPDF_DISTRIBUTION_NOTE.md`. |

**Physical printer qualification** (owner, restated): physical output, real offline handling and physical job
cancellation are **NOT VERIFIED** and stay in the O2P ledger. Missing hardware must not block unrelated O2 work.

**Implementation priorities** (owner order): 1 shared service interfaces and capability contracts; 2 engine and
validation pipeline; 3 B1 Flutter workspace; 4 PDF conversion, viewing, preview, Save as PDF and validation; 5 intent,
assistance, planning and the existing approvals; 6 O2P printing. O2 and O2P may run in parallel once the shared
interfaces are stable. O2P evidence and acceptance stay separate.

**Unchanged limits:** no push, merge, deployment or production activation because tests pass; no canonical
integration; no installation or elevation; no physical printing; no frozen Core change; no protected path.

Still open (owner): OD-U3b (pypdfium2, fallback only); OD-U4 (Google scopes); the GPU window; the owner live check;
physical-print authorization; G5, G6 and G7.
