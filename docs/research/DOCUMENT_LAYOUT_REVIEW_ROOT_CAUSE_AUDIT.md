# Document layout and Brain review: evidence

2026-10-03. User requests correction of overlapping text and a Brain recheck
of generated documents. Running checkout remains uri-m37-m39-integration.

The supplied screenshot shows wrapped bullet lines colliding. The actual
PPTX renderer creates a 0.59-inch textbox per bullet at 0.66-inch increments,
with 20pt wrapped text. Two/three wrapped lines exceed that height. It also
silently drops bullets after seven and sizes pictures only by width, so a
portrait image can escape its content region. These are local renderer defects.

Generation currently composes once, renders/stores files, then asks the Brain
to phrase an outcome. That final wording call does not inspect slide layout
or correct the document body. Prior qualification checked file count, themes,
slide count and pictures; it did not certify rendered text fit. The User's
image is a failed live visual check, superseding any structural-only readiness.

Frozen M38, account stores, approval/grant boundaries and model provider
configuration remain outside this repair. LibreOffice is unavailable on this
host; geometric/font-metric checks must not be described as raster visual QA.
