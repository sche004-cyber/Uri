# Presentation variants: implementation evidence and open repair scope

2026-10-03. Codex investigation of the User's two screenshots. This is a
Stage 1 evidence record, not an independent audit verdict or accepted design.

## Execution location

The Core listening on port 8000 (PID 16528 at inspection) has cwd
`C:/Users/cheta/Development/uri-m37-m39-integration`. The current chat workspace
is `_V1`. The two checkouts have different generation, renderer, composer,
orchestrator and planner code. The running installation was inspected read-only.
No production account, credential, transcript, presentation or application code
was modified. Only this evidence record was added in `_V1`.

## Actual turn and file evidence

The matching session's persisted conversation records:

1. Original Student Welfare / NIT Sikkim request: `web_search`, status `success`,
   zero attachments, 2026-10-03T02:52:41.482080Z.
2. Request to generate all three visual design templates: `generate_document`,
   status `success`, one attachment, 2026-10-03T02:54:34.544370Z.
3. "I don't see three PPTs. Can you check again?": `drive_search`, status
   `unavailable`, one attachment still recorded, 2026-10-03T02:56:02.086173Z.

The referenced local artifact is
`I_want_you_to_generate_all_three_design.pptx`: 36,543 bytes, six slides,
zero embedded media parts. Slides describe presentation overview, three
template options, comparative analysis and next steps. They are descriptions
of design approaches, rather than three topic-specific presentation drafts.
No separate matching files were found for that response. This inspection read
the matching attachment only; it did not enumerate unrelated slide content.

## Confirmed implementation behavior

In the running checkout:

- `uri_core/tools/generate_document.py`, `GenerateDocumentTool.generate`:
  one composer call, one render call and one FileStore save, returning singular
  `file`. It accepts a single theme and image flag. There is no per-invocation
  variants list or multiple-output contract.
- `uri_core/services/office_document_writer.py:207`: renderer accepts one
  theme for the whole presentation. Theme colors are chosen once at line 218.
  Image retrieval exists, so an inability to generate images directly does not
  establish an inability to retrieve licensed images. The real artifact has
  no images; the exact image flag proposed for this turn was not recovered.
- `uri_core/core/model_reasoning_adapter.py:225`: guidance defaults PPT
  creation to local `generate_document`. Lines 228-233 specifically tell the
  Brain to research, describe three options and wait for a choice. This is
  narrower than the User's request to render all three drafts. The later
  request did not result in three delivered artifacts.
- `uri_core/core/orchestrator.py`, `_build_query_context`: local session
  FileStore references and recent conversation are assembled as context.
  Persisted history confirms `drive_search` was selected for the correction.
  Therefore blanket absence of artifact context is not established; inspect
  the exact reasoning request and proposal before assigning that cause.
- The capability catalogue describes `generate_document` as one local Office
  file and exposes no interface schema for its supported theme/image/title
  parameters. `read_attached_file` exposes `file_id`; `drive_search` represents
  Google Drive search. The recorded Drive failure is genuine unavailable-service
  reporting following an inappropriate tool selection for local-output review.

This task used Main Brain / existing document tools. No recorded turn selected
the isolated Claude Code adapter. A passing adapter qualification does not
establish production Brain discovery or presentation generation integration.

## Deterministic reproduction

Used the running checkout's actual GenerateDocumentTool with an injected mock
composer and a disposable FileStore. Supplied the exact follow-up request plus
the preceding PPT request as recent conversation. Disabled image retrieval by
omitting its opt-in flag. No model, network, Google login or Claude execution.
The mock body contained all three design-option headings. Result: status
`success`, PPTX format, one stored file, one returned file reference. This
reproduces the singular-output behavior; it does not validate a repair.

## Repair decisions and acceptance still required

The User selected repair of the running uri-m37-m39-integration checkout on
2026-10-03. This record precedes its implementation. This evidence does not accept
a new architecture or authorize a merge between checkouts.

The repair must preserve Brain reasoning and runtime authorization: establish
how multiple proposed variants become separate authorized generation steps,
carry the original topic/research/image requirements, and evaluate delivered
artifact count/content before claiming task completion. It must ground local
artifact correction in actual session-owned references and distinguish that
from an explicit request to search cloud storage. Do not add a hard-coded
"three PPTs" phrase router, automatic cloud fallback, credential bypass or
automatic invocation of Claude Code.

Acceptance must include mock workflow/context regressions, original user-data
isolation and approval boundaries, then a live native UI run demonstrating
three distinct topic-specific downloadable presentations with accurate image
status and a local-artifact follow-up. An independent reviewer must assess the
actual repaired paths; this document cannot serve as that review.
