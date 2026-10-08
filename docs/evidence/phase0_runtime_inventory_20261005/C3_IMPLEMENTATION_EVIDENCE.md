# C3 implementation evidence

PROVISIONAL — AWAITING INDEPENDENT REVIEW. Base `e8e3b65259c45fc823addc3ef8969425a265bd1b`; no commit or push. This implements the frozen C3 worker/private-persistence scope. Desktop UI parity remains C6 work.

Source overlay: `C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\c3-provisional-source.zip`; SHA-256 `7b2a7a563ae7a58bb7273eee98fbd19a3f21f0dec75c65a3e900b066b6fc4c2f`. Contains 39 changed/untracked source files before final handoff documents; ignored runtime state, client secrets and databases are excluded. Earlier C1/C2 overlays remain preserved.

The combined C1–C3 run passed 58 tests (22 C1, 17 C2, 19 C3), followed by an additional passing PowerShell binary transport test. The latter repairs a Windows PowerShell 5.1 binary-pipeline defect using raw redirected process streams. Core regression validation passed 303 tests plus 29 subtests. XML evidence is under `work/c1/`; the regression runner uses synthetic homes/state and the original test files. `git diff --check` passed.

Live validation used a fresh isolated paired server and two independent client workers sharing one principal. Both proved pinned identities and acquired sessions. A consented local mutation persisted in client A, identical replay returned its receipt, and client B remained empty. The server created no private stores; no model or UI started. Owned test processes were cleaned using identity proofs and worker pipes. This does not qualify the C5 canonical reasoning loop.

The worker validates strict framed requests, source/interpreter/dependency/state/server pins, duplicate-worker mutex, snapshot/mutation bindings, consent, versions and projection hashes. Existing private stores execute locally. DPAPI protects client secrets; ACLs protect fresh installations. Journal tests cover refusal, replay, rollback, interrupted PREPARED recovery, backup integrity and external-write conflicts. Recovery restores owned private state and never replays external execution. No native harness executes through this C3 worker yet.

Limits: headless development launcher only; no UI binary until C6; recoverable single-writer multi-store persistence rather than arbitrary concurrent-reader atomicity; method coverage inventory does not establish live qualification of every mutator. Fixture filesystem guards are not a malicious native-process sandbox. Frozen baseline and its C2 amendments require independent review.
