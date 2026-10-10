# M1 REA (Reverse Engineer Anything) evaluation

## 1. What REA is

The source is the project README (EXT-P: github.com/morluto/rea, README fetched 2026-10-10).

| Property | Value |
|---|---|
| Project | `morluto/rea`. A fork, `ChristopheAI/reverseengineeranything`, was archived on 2026-07-15 (EXT-S). |
| License | MIT |
| Form | An MCP server plus a CLI for coding agents (Claude Code, Codex and others). Installed with `npx rea-agents setup`. |
| Runtime | Node.js 22.19+ / 24.11+ / 26+ with npm |
| What it wraps | Ghidra, Hopper or IDA for native code; JADX for Android; Binwalk/Unblob for firmware; HAR and mitmdump for network; a Chrome-family browser for websites; static JS/Electron and .NET inspection |
| Windows | Ghidra on Windows is "experimental". Firmware, mitmdump and pwntools ELF features are Linux-only. Process capture is Linux and macOS only. |
| Execution | Static JS and .NET analysis read files without running them. Runtime capture "runs or interacts with the selected target using your user permissions". |
| Data | Analysis runs locally, but the agent's model provider sees what the agent sends |
| Its own caveat | "REA changes quickly"; features vary by provider |

**Not done here:** REA was not installed or run. No benefit has been measured, so every comparison below is analytical.

## 2. Comparison for URI's actual needs

| URI need | Better first tool | Would REA add value? |
|---|---|---|
| Understanding URI's own components | Direct source analysis. Every URI component is source in this repository. | **No** |
| Undocumented web application behaviour (for example, a government portal form for P4) | Browser DevTools, HAR export, Playwright trace viewer, the site's documentation | Marginal. REA's website mode wraps the same browser observation. |
| Social platforms | Official APIs (`M1_SOCIAL_PLATFORM_RESEARCH.md`) | **No, and inappropriate.** Reverse engineering private APIs to get around official access is exactly what the assignment prohibits. |
| Claude Code and Codex binaries or credential stores | Vendor documentation | **Prohibited.** Anthropic requires the binary to be unmodified and forbids intermediating credentials. Inspecting auth storage to reuse tokens would breach `M1_HARNESS_ACCESS_AND_LICENSING.md` §2. |
| A future third-party compiled app to be hosted, with no documentation | The vendor's SDK or documentation | **Possibly**, for interoperability analysis of an app the owner is licensed to use. Static inspection only. |
| Interop failures (for example, an Electron app's local IPC) | Logs, DevTools, Process Monitor | Possibly, for Electron/JS static inspection |
| Learning implementation techniques | Reading open-source projects | Low. Reproducing proprietary code is excluded. |

## 3. Verdict

- **REA is not an M1 dependency, at runtime or in the build.** Nothing in P0-P6 needs it.
- **Optional developer tool only**, and only under all of these conditions:
  - it runs on a **non-production** machine or VM, never on the URI server and never as the URI service account;
  - targets are software the owner is licensed to analyse, and the analysis does not breach that software's terms;
  - static modes are preferred; runtime-capture modes run only in a disposable VM;
  - findings are written up as human-reviewed notes, and no extracted code is copied into URI;
  - the model provider's data policy is acceptable for the target, since agent prompts may include target code.
- **Evaluation gate, if the owner wants evidence** (deferred; needs a non-production Windows or Linux machine):
  - time-box one question on a URI-owned target: "map the URI Flutter Windows build's local IPC";
  - compare against DevTools/HAR plus source reading, measuring hours saved and correctness of findings;
  - adopt as a documented dev tool only if it is ≥30% faster with no correctness loss.

## 4. Risks

- A fast-moving npm dependency tree is a supply-chain risk.
- Runtime capture executes targets with the user's permissions.
- Agent prompts send target material to a cloud model.
- Legal exposure from analysing software whose terms forbid reverse engineering.
