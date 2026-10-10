# Superseded: M1 architecture audit and plan

This report was first committed in `be55d19` and extended with §11 in `a6ef74f`. On 2026-10-10 its content was split
into the twelve required M1 reports. Its full text stays in git history (`git show a6ef74f:<this path>`).

Where each section now lives:

| Old section | New home |
|---|---|
| §0 Baseline, §1 Inventory | `M1_REPOSITORY_CAPABILITY_INVENTORY.md` |
| §2 Gap analysis | `M1_REPOSITORY_CAPABILITY_INVENTORY.md` §3-§4 and `M1_THREE_USER_SERVER_ARCHITECTURE.md` |
| §3 Three-user architecture | `M1_THREE_USER_SERVER_ARCHITECTURE.md` |
| §4 Harness terms | `M1_HARNESS_ACCESS_AND_LICENSING.md` |
| §5 App host | `M1_APP_HOSTING_DESIGN.md` |
| §6 Threat model | `M1_BROWSER_AUTOMATION_AND_SECURITY.md` §6 (consolidated) |
| §7 Slices S0-S9 | `M1_IMPLEMENTATION_SLICES.md`, renumbered (mapping table there) |
| §8 Audit procedure | `M1_IMPLEMENTATION_SLICES.md` header rules |
| §9 Cloud vs PC | `M1_OFFLINE_BLOCKERS_AND_STATUS.md` |
| §11 Storage | `M1_STORAGE_ACCESS_DESIGN.md` |
| Conclusion | `M1_RESEARCH_SUMMARY.md` |

**Correction carried forward:** the old threat model did not include SSRF. It was found and confirmed in this revision
as SSRF-1 / T-9.
