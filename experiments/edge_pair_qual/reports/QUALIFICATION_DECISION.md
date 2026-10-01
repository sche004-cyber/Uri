# EPQ-1 qualification decision record

| Field | Value |
|---|---|
| Decision | **NOT QUALIFIED**: Needle 3, `granite4:350m-h`, and their tested pairing, for the EPQ-1 workload at the tested interface |
| Decided by | Chetan (project owner), 2026-10-01 08:13 UTC, in the project thread "Edge Brain performance qualification" |
| Evidence | this package, at commit `26537cd` (holdout run once after the harness freeze `c17f593`) |
| Independent audit | **PENDING**. Codex is paused, and the audit handoff (report G) has not been executed. These results are **not independently audited** and must not be described as audited until the Codex review is complete |
| Live path | Neither model nor the pairing is promoted into any live or production execution path |
| Frozen components | M37 (`uri_v1/edge`) is unchanged; any change needs separate authorization plus the required independent audit |

Owner's direction recorded with the decision (paraphrased; the thread holds the exact text):
1. Keep the full evidence package, the failed cases and the decisions.
2. Treat the semantic-correctness failures as an architectural finding: investigate the boundary between RAR/ARN context resolution, specialist proposals and execution permission.
3. Establish whether existing deterministic grounding and ambiguity checks can prevent the incorrect actions before adding model-based verification.
4. A technically valid tool call is not necessarily a correct interpretation of the request.
5. Keep the Edge architecture flexible. A specialist gets a role only where comparative qualification shows an end-to-end advantage, for narrow, measurable capabilities.
6. Do not let Edge research delay Harness-first application integration. A working URI application for testing is the immediate priority.

This is not a decision to abandon the Edge Brain architecture. Follow-up research: `reports/H_INTEGRATION_BOUNDARY_FINDINGS.md`.
