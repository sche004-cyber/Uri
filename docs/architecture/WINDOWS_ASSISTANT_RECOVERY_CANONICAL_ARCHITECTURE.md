# Windows assistant recovery — architecture disposition

Stage 2 proposal, derived from
`docs/research/WINDOWS_ASSISTANT_RECOVERY_ROOT_CAUSE_AUDIT.md`.
Status: BLOCKED at the runtime frozen-security boundary; not an accepted new
architecture or completed repair.

Reuse the accepted Working System composition: real Flutter main entry point,
manifest opt-in, integrated stdio worker, existing OI answer channel and
PairedCoreGateway, paired Core authority, resident pinned Runtime v1, Office
service and native WebView2. Retain the current model, one inference slot,
structured approval chain, signed settlements and source identity checks.
Qualify this existing composition before choosing further routing changes.

Three approaches were compared from source and preserved live evidence:

| Approach | Disposition |
|---|---|
| Restore intended Working System profile and minimally reconcile its reproducible runtime build | Preferred: reuses accepted answer/context/discovery seams; first requires exact security-blob reconciliation and output provenance proof |
| Repair classic `/ask` proposal transport, fallback and planner | Potential separate profile work, but affects frozen `uri_core/`; not chosen as an unauthorized substitute for the designated release architecture |
| Add a parallel conversational HTTP assistant or remove `prepare_output` safety refusal | Rejected: duplicates existing functionality or fabricates successful execution without an implemented capability |

No profile-switch-only fix is declared sufficient. Conversation, follow-up,
durable memory retrieval, incomplete-intent clarification, confirmation and
approval must all be demonstrated in the actual production main UI. The
answer-only channel may talk; it may not claim a state mutation. Core alone
authorizes and executes. Retrieval must use the correct client's scoped store;
supplied chat history is not a substitute for a durable-memory test.

Edge deployment must expose real qualified inventory and an actual routing
bridge before it can be accepted. Do not rename deterministic OI triage as Edge
model inference. Assist requires a genuine granted capture transport, with
unchanged visible-text proof, secret redaction, target freshness and revocation;
until then its status is unavailable. Substantial integration work must remain
isolated and carry its own qualification matrix.

For Office, compare strict per-operation schemas or another narrowly supported
contract repair against the observed null-name request. Keep deterministic
validation as the authority and retain all file hashes, working-copy safeguards,
partial-write protections and approval binding. Failed model proposals must
remain visible and cannot be replaced by guessed arguments.

The exact protected transition proposal lives outside the source tree in
`proposal/EXACT_RUNTIME_SECURITY_TRANSITIONS.patch` and
`proposal/RUNTIME_SECURITY_TRANSITIONS.json` in the recovery workspace. The
source's active accepted checker is unchanged. A future materialized-tree
verifier must reject unknown/altered blobs, missing provenance, invalid modes,
unapproved paths or mismatched source candidate identity. It must preserve the
original checkpoint and the actual historical e8 HEAD, rather than rewriting
identity or granting path-wide exceptions. No new checker is activated here.
