---
name: impeccable-design
description: "Design guidance and anti-pattern avoidance adapted from Impeccable for URI UI development. Use when auditing, polishing, refining layout, typography, animations, responsive adaptations, or edge-case handling for URI desktop companion and workspace screens. Enforces URI's 4 approved palettes and strictly prohibits generic SaaS tropes (purple gradients, un-tinted grays, nested cards, bouncy easing)."
---

# URI Impeccable Design Guidance (Advisory Skill)

This skill provides design evaluation playbooks and anti-pattern checks adapted from the Impeccable design framework (Paul Bakaus) tailored specifically for URI's Flutter desktop and mobile interface.

> **Operational Boundary:** This is an on-demand, documentation-only design skill for AI agents (Antigravity, Claude, Codex, Gemma). It executes purely through agent reasoning. It does not install external binaries or register automatic file-interception hooks.

---

## 1. Non-Negotiable URI Identity Rules

Before applying any design rule, ensure compatibility with URI's design authority:

1. **4 Approved Themes Only:** Always resolve colors through `UriColors.of(context)`:
   - **Graphite:** Canvas `#0C0D0F`, Surface `#17181B`, Border `#2A2C30`, Accent `#C8A25A` (Warm Gold).
   - **Deep Navy:** Canvas `#0A0F1A`, Surface `#101828`, Border `#243349`, Accent `#5B8FC7` (Slate Blue).
   - **Slate + Teal:** Canvas `#131619`, Surface `#1A1E22`, Border `#2C3238`, Accent `#4A9C92` (Teal).
   - **Light Professional:** Canvas `#F6F7F8`, Surface `#FFFFFF`, Border `#DDE1E5`, Accent `#3B5A78` (Steel Blue).
2. **Never Use Un-Tinted Grays/Blacks:** Pure `#000000` or `#808080` are forbidden. Dark surfaces must always carry subtle warm, blue, or slate undertones.
3. **No Purple-to-Blue Gradients:** Avoid standard SaaS gradient cliches.
4. **Never Nest Cards Inside Cards:** Use background surface tinting, dividers, or subtle borders to establish hierarchy without card bloat.
5. **No Bouncy/Elastic Motion:** Animations must use purposeful cubic easings (e.g. `Curves.easeOutCubic`, 150–250ms), never spring/bounce curves.

---

## 2. Command Playbooks for URI Agents

Agents can reference these guidelines when fulfilling design instructions:

### `/impeccable layout`
- Establish consistent visual rhythm using `UriSpace` constants (`xs: 4`, `sm: 8`, `md: 16`, `lg: 24`, `xl: 32`).
- Align related items (e.g. file attachment chip with its parent turn).
- Keep interactive button touch targets at minimum 40×40 logical pixels (44×44 for navigation rail items).

### `/impeccable polish`
- Inspect typography hierarchy: Primary headers (bold, 14–16px), turn narrative (regular, 13–14px), metadata/captions (muted, 11–12px).
- Verify status indicators: Routine turn completion should be calm and unobtrusive; human approval decision gates must be clearly distinguished with actionable contrast.

### `/impeccable harden`
- Prevent text overflows: Wrap file names, paths, and URLs in `TextOverflow.ellipsis` with a `Tooltip`.
- Empty states: Every collection, history list, or search view must have a helpful, structured `EmptyState` explaining what is missing and how to proceed.
- Error clarity: Never display a bare error status without an explanatory diagnosis and actionable retry or remediation step.

### `/impeccable animate`
- Restraint first: Motion should only communicate state change (window resize, expand-to-workspace, turn arrival).
- Duration: 150ms for micro-actions, 250ms for panel expansion.

---

## 3. Review Checklist for Agent Output

When reviewing a UI proposal or component:
- [ ] Are all colors bound to `UriColors.of(context)` rather than hardcoded hex values?
- [ ] Does the screen strictly reflect real URI backend data (no fabricated metrics or deadlines)?
- [ ] Are decision gates (Proposals requiring approval) visually distinct from completed records?
- [ ] Is layout responsive across Compact (`420×580`) and Workspace (`1280×900`) widths?
- [ ] Are all callbacks and event contracts preserved untouched?
