# Bounded document layout repair and recheck design

Candidate within the User's direct repair request; not independent acceptance.
See ../research/DOCUMENT_LAYOUT_REVIEW_ROOT_CAUSE_AUDIT.md.

Use the existing generation/composition role and authenticated principal.
For PPTX, fit all bullet paragraphs in one reserved text region; bound pictures
in a separate rectangle, and keep title/footer regions separate. Use consistent
font metrics with explicit wrapping and conservative spacing. Never silently
truncate content. Inspect actual rendered slide geometry and extracted text.

Before FileStore writes, send that evidence and the original request/body back
to the Brain. Accept only a bounded review decision or revised body. Permit
one in-memory correction, validate its content through the existing document
validator, and rerender the same requested designs with the same image pool.
The Brain cannot change principal, workspace, approval, capabilities or labels.
Remaining geometry faults block publication. Unavailable model review is
reported as provisional, never visual/independent verification. Other Office
formats remain on their current path pending format-specific evidence/checks.

This is part of the existing authorized generation, with no new capability,
file selection authority, external transmission, credential access or harness
invocation. Independent Claude review and a new live desktop check remain
required before readiness; a model reviewing its own output is not an audit.
