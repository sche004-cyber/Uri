# 10 — Strategic Vision: URI Core → URI Office → future URI versions

## The one-sentence identity

**URI is the persistent, trustworthy companion that understands what the user means, decides what may happen, hands the work to the best available engine, and proves the result. The engines underneath are replaceable.**

## What URI owns (evidence-based)

Commodity execution is available externally: agent loops, browsers, terminals, computer use, and tool ecosystems. Research found **no external equivalent** for the following, so this is what stays uniquely URI's:

1. **The relationship.** Identity, continuity, persona, preferences and durable knowledge that survive any engine change.
2. **Meaning.** Semantic and reference resolution (RAR), narrowing and clarification (ARN), and consequence-aware binding. No harness binds references authoritatively or knows when a guess is dangerous.
3. **Authority.** Permissions, grants, effect classes, single-use argument-bound approvals, fail-closed boundaries, and per-harness authority postures. Harness approval systems cover only what each harness itself classifies.
4. **Truth.** Provenance, evidence, result versions, and **independent outcome verification**. Every harness reports its own success. None verifies the end state independently.
5. **Economy.** The Edge ladder (deterministic → Edge → Capable → harness), shared model residency, and configure-once intelligence brokering. Harnesses send everything to one large model.
6. **Stewardship.** Engine discovery, pinning, qualification, upgrade approval, rollback and replacement, so the user never manages a second product.
7. **Domain understanding**, packaged as domain packs.

## What URI consumes

- Agentic execution: qualified harnesses behind a URI provider port, preferring open, local-endpoint-capable, Windows-native candidates.
- Browser, desktop and Office automation: MCP servers and harness-native tools, each qualified.
- Models: local servers and cloud providers behind URI's router.
- Protocols: ACP to drive agents, MCP to offer and consume tools, OpenTelemetry GenAI conventions for traces. A2A and AG-UI are deferred until needed.

## Product line

```
URI Core   — domain-neutral control plane (relationship, meaning, authority, truth, economy, stewardship)
  └─ URI Office (first domain pack)
       documents · spreadsheets · presentations · PDFs · email · files · browser & portal workflows
       · scripts · verification of completed office work
  └─ future packs (not designed now): Content/Creator · Personal · Health/Diet · ...
```

A domain pack declares:
- capability exposure
- vocabulary
- rules
- workflow hints
- verifiers
- default policies
- harness profile templates

It never modifies Core authority. Future packs will be possible if one discipline starts now: **no new Office-specific logic enters `uri_core/core/`**.

## How it should feel (URI Office)

- **Bounded requests** ("find last week's circular", "draft the noting") answer immediately through deterministic and Edge paths. No heavyweight engine starts.
- **Open-ended requests** ("make this script work with this spreadsheet") produce a visible plan. URI then starts a qualified engine that the user can watch. Consequential steps pause for URI approval. URI verifies the result and shows the evidence. It says "verified", or it says exactly what it could not verify.
- **The user never configures Hermes, Codex or any other engine.** URI asks only about things that matter: cost, privacy, permissions, and consequential upgrades.

## Constraints this vision accepts (from evidence)

- Fully local agentic execution on a 16 GB GPU is **unproven**. Harness runs may need a cloud Capable Brain, with user awareness, until experiments show otherwise.
- Authority over harness actions must be **earned per harness**. Until it is proven, external effects flow only through URI's broker.
- The ecosystem moves weekly. URI's stability comes from its own boundaries, not from any engine's.
