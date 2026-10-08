# Presentation variant repair: bounded implementation design

2026-10-03. User directly assigned Codex the running-checkout repair. Based on
[Stage 1](../research/PRESENTATION_VARIANTS_ROOT_CAUSE_AUDIT.md). This is an
implementation design within that assignment, not a self-approved milestone,
independent review or release. Governing authority remains ADR-018, the Model /
Runtime Contract and the active milestone record.

Reuse `generate_document`, FileStore, canonical gate and the existing PPTX
renderer. Add an optional `variants` list of label/theme pairs, bounded by the
three distinct renderer themes. The Brain decides whether variants are wanted,
their labels, original topic and content. Runtime validates the physical input
shape and bounds before any composition, rendering, image retrieval or write.
Author actual topic slides once, render the same content into distinct requested
themes, and return each real saved FileStore reference. Report exact requested
and created counts and incomplete outcomes; no fake files or silent retry.
Images are retrieved once and shared across variants with the existing credit
and truthful failure behavior. Preserve the existing single-file contract.
Report actual total slide counts including the existing image-credit slide.
Use a slide-specific composition prompt, preserving identity, applicable policy
and the existing document validator; administrative-note conventions must not
invent headers/reference numbers in subject slides. Reject a reply that denies
photos when the actual renderer counted embedded pictures.
Expose the generator's actual declared content schema to the preselected
canonical Brain, including its one legacy action and bounded variant inputs.
This is discovery data, not dispatch or execution authority. The second live
failure showed prompt guidance alone was insufficient: a multi-action proposal
could enter legacy fallback, losing those inputs and creating extra files.

Project bounded `session_files` metadata from the authenticated user's existing
FileStore for this session into canonical decision and native-loop context.
This is evidence only, with no path, content, capability or authority. The Brain
uses this and recent dialogue to distinguish local-artifact review from explicit
cloud work. No phrase router, forced cloud fallback or new tool is introduced.

Extend the existing Flutter ActionResult with real multiple-file references and
render a chip for each. Keep the legacy single-file constructor and getter
behavior. The authenticated content endpoint remains the only download path.
Native continuation keeps the same bounded context and actual accumulated
tool results, and carries runtime-owned generated references into the reply.
No screen redesign, account changes or provider changes are required.

Frozen M36-M39 implementations and their qualification anchors stay untouched.
Existing desktop allowlisted Core/UI paths receive only this repair. Preserve
unrelated dirty changes, especially the current reference-clarification edits.
Claude's independent review/re-pinning remains required before release; Codex
does not rewrite frozen guard pins to make its implementation appear accepted.
