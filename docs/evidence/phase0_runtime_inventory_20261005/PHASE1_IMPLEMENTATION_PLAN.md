# URI Phase 1 — Preservation and Implementation Preparation

Date: 2026-10-05. Status: preparation package for review. The User authorized Phase 1 preservation, boundary design and an isolated integration worktree. Production consolidation implementation is not authorized by this document.

## Deliverables and reused evidence

The Phase 0 companion reports were reviewed before design. Keep [Runtime inventory](RUNTIME_INVENTORY.md) and [Contamination report](CONTAMINATION_REPORT.md) as dated observations, rather than rewriting history. Update the existing [Ownership matrix](SERVER_CLIENT_OWNERSHIP.md) in place. [Interface plan](SERVER_CLIENT_INTERFACE_PLAN.md) defines canonical architecture; [Launcher plan](LAUNCHER_CONSOLIDATION_PLAN.md) defines process authority; [Preservation manifest](PRESERVATION_MANIFEST.md) records recoverability. The existing [Consolidation roadmap](CONSOLIDATION_PLAN.md) remains the broader sequence and gains a pointer to this current package.

Four-stage lifecycle mapping: Phase 0 provides Stage 1 evidence; ownership/interface/launcher plans provide Stage 2 proposed architecture; this plan provides Stage 3 proposed integration sequence. Stage 4 is not started. After review, the authorized architecture/release roles can link/freeze these artifacts into the repository's canonical governance locations without duplicating their contents. No active-milestone/tracker update or acceptance declaration is made here.

## Source authority and isolated environment

Accepted Core anchor: `e8e3b65259c45fc823addc3ef8969425a265bd1b`. Keep dirty master, integration desktop, V1/harness-console and all registered donors as preserved sources, not automatic merge inputs. Higher commit numbers or branch names do not confer qualification.

An app-managed isolated worktree is prepared from that exact checkpoint; its resulting path/branch and setup evidence are recorded in the preservation manifest. No production code change, model configuration, credential copy, running service, virtual environment installation or server launch is performed there. Default future development port is 8031 if free; future state/client roots must be synthetic and outside legacy `uri_workspace` roots.

Do not invoke existing launchers inside the worktree: their default task name, relative private roots, dependencies and UI preference namespace can affect existing installations. Use the future opt-in manifest launcher only after it is implemented and reviewed. Do not import the app merely as a setup probe; accepted source may initialize legacy/global collaborators.

## First implementation milestone: Runtime Identity and Launcher Authority

Proposal ID C1, matching the Phase 0 roadmap. It is not an assigned M-number or permission to start now.

Outcome: a developer can launch and identify one intended isolated Core server without silently adopting another checkout, touching existing tasks/shortcuts, warming a model, or owning client data. Preserve `/health` and existing route behavior; add explicit identity/status and an opt-in launcher. Client-owned persistence and general client-launch implementation follow later.

### Required files and seams

In the isolated worktree only, after approval:

| File/seam | Change |
|---|---|
| New `uri_core/core/runtime_identity.py` | Immutable identity/manifest validation model, generation and safe public projection; no private-store imports |
| New `uri_core/app/runtime_routes.py` or narrow equivalent in existing app module | `/runtime/identity` and authenticated `/runtime/status` handlers |
| `uri_core/app/server.py` | Add explicit runtime composition dependency and route mounting; no change to accepted decision/authority semantics |
| `uri_core/app/route_classification.py` | Classify both routes; preserve existing route classifications |
| New `scripts/uri_server.ps1` and manifest schema | Bounded exact-ownership start/status, mutex, explicit source/interpreter/state; no install/stop/restart/cutover action |
| Existing `scripts/run_uri_server.py` seam or new opt-in composition wrapper | Accept explicit manifest without changing legacy default launcher behavior; no source-repo credential defaults inherited by new server |
| New focused runtime-identity/launcher tests plus existing route auth/bind suites | Validate wrong identity/listener, generation, concurrency, safe errors and optional-model absence |

Reuse integration exact script/executable/socket checks as reviewed code patterns, not a merge of `run_desktop_server.py`. Do not import its harness-first or model-residency behavior. Never change current installed task settings as an incidental launcher fix.

Observed startup dependency: accepted `server.py:914` registers `_UserScopedStoreInitializer` and `_GraphifyIndexLoader`; `_initialize_user_scoped_stores` resolves an installation identity and performs copy-only legacy migration. Therefore ordinary accepted startup is not already a client-state-free server composition. C1 must trace constructor/lifespan paths before any live launch and bind every legacy compatibility path to a fresh synthetic fixture root, with no legacy source files available to migrate. Empty synthetic identity/store fixtures are a transitional test dependency, not private client databases or the final ownership architecture. Do not claim server/client persistence separation in C1. If explicit path injection cannot contain startup without broader persistence refactoring, stop for a revised slice before starting it; do not improvise a second Core or disable accepted safeguards.

### Dependency-ordered work

1. Confirm preservation evidence and exact accepted checkout before implementation. Read current governing records; inject deferred features/protected paths as explicit negative constraints in task context.
2. Freeze the C1 manifest contract and public/private identity fields from the launcher plan. Source checkpoint and source manifest digest are supplied build/deployment metadata, not a runtime claim that dirty files are accepted.
3. Implement identity construction as a pure component. Generate runtime generation on process start; keep stable server installation ID in the server manifest. Reject malformed paths, invalid host and mismatched source/contract identifiers before serving.
4. Add the two classified routes using existing principal enforcement. Public identity never returns paths, account/config/credential details. Detailed status uses safe readiness codes, not raw exception strings.
5. Implement opt-in start/status launcher. Use explicit interpreter and synthetic state root, exact process/socket provenance and a local control identity proof. Mutex bounds concurrent launches. A foreign listener is never stopped, restarted or adopted.
6. Validate no implicit model generation/warm-up, production config access, real client-private-store creation or native account discovery during new composition startup. Enumerate and contain the observed legacy startup dependencies in disposable synthetic fixtures. If explicit path injection cannot satisfy this locally, report the dependency and obtain a revised slice; do not silently migrate store ownership under C1.
7. Run focused component/route/bind/launcher checks in synthetic directories. Validate a real development server on a free nonproduction port, with controlled stop of **only that milestone-owned test instance** at validation cleanup. No production service is part of the test.
8. Independently review actual production paths and live behavior. Record source/build/configuration identity and any exact pre-existing failures. Release/commit only by the applicable authorized role after acceptance; Codex does not self-declare VERIFIED.

### C1 acceptance matrix

| Condition | Required proof |
|---|---|
| Correct identity | HTTP and local manifest/source/interpreter/state root agree; wrong digest/server/composition rejected |
| No contamination | Existing shortcuts, task XML, source/application hashes and active service identity unchanged |
| No unintended authority | Existing principal/route/approval/bind controls pass; public identity contains no sensitive paths/state |
| One server | Two concurrent opt-in launches yield one owned listener and accurate status |
| Foreign/stale process safety | Wrong healthy URI, occupied port, reused PID and stale bookkeeping all fail without signaling foreign process |
| Honest failure | Missing interpreter/build, bad manifest and startup timeout fail safely; no generic health readiness shortcut |
| Models optional | No Ollama/Brain required for identity/start; zero generation/warm-up calls |
| Private state boundary | No existing legacy/client databases or native harness auth files opened/imported; any compatibility identity/store files exist only in fresh synthetic fixtures; later state-port separation remains unclaimed |
| Live result | Developer observes identity/status of the isolated server; legacy source/entrypoints remain unchanged and existing compatibility regressions pass; live UI parity is a later C6 gate |
| Recovery | Restore/rollback to pre-C1 isolated checkout/manifest; no production paths used |

For this infrastructure slice, meaningful live acceptance is launcher/HTTP/process identity, not a new user-facing AI capability. Existing canonical-loop regression is retained. New features in later slices must satisfy the full discover → propose → validate → approve → execute → feedback → live UI rule.

## Subsequent bounded slices

| Slice | Prerequisites | Concrete result / freeze gate |
|---|---|---|
| C2 — Paired client context + state ports | C1; approved interface schemas; enumerate existing store method needs | Strict client routes and request-scoped adapters; no ambient fallback; two-client isolation over synthetic state |
| C3 — Client worker/private persistence + client launcher | C2; supported Windows worker lifecycle; local state transaction design | Independent client roots/prefs/sessions and local journal/CAS; no production-data migration yet |
| C4 — Client harness/cloud bridge | C2/C3; per-adapter qualification | Native credentials remain client; validated tickets, bounded receipts, truthful quota/recovery; no automatic account/provider substitution |
| C5 — Shared engines/model-optional canonical loop | C2–C4; exact RAR/ARN/Graphify donor qualification | Local/cloud/harness reasoning routes, receipts back to reasoning, private overlays scoped; full no-Brain live turn |
| C6 — UI/voice parity and separately approved copy-first migration | C3–C5; explicit owner map/key lineage; source/build baseline | Existing user-visible flows preserved; historical data copied only into its identified client; originals retained |
| C7 — Default launcher cutover/retirement review | All required behavior independently accepted; explicit deployment authorization | One authoritative installed server and client launch entry; legacy entry points retained until separately verified retirement |

Production owner mapping, credential portability, migration formats and compiled UI provenance are gates for later slices, not choices to invent in C1. Legacy PyQt, scheduler prototypes and dormant experiments remain preserved. No scheduler, new graph engine, new provider family, production RBAC/admin UI, mobile packaging or ARN.2 is bundled in.

## Data and donor qualification procedure

Compare a needed donor module against the accepted checkpoint and its preserved dirty overlay. Link exact artifacts to acceptance source/version. Run the existing component and authority boundary tests, then canonical-loop and live client behavior where applicable. Adopt one qualified behavior at a time; preserve experimental negatives/default-off rules. Never merge an entire donor just to obtain one feature.

Before eventual migration, the User identifies each historical installation's destination client. Work from verified backup copies and a fresh copy-first migration snapshot. Validate database/schema/references and key provenance privately; reports contain counts/digests, not contents. Test recovery in a new root before any live destination is selected. No credential import into a server-global store.

## Rollback and stop conditions

C1 rollback is entirely within its isolated worktree/new synthetic roots; existing desktop/task/data never need restoration because they were never changed. Later rollback preserves newer client versions and unsettled operation receipts; never writes new schemas using old code or replays unknown side effects. Restore only into new verified vault/test roots unless a separately authorized recovery names an exact destination.

Stop and report if an implementation needs to modify production shortcuts/tasks/models/data, bypass gates, use shared client auth, merge unqualified experiments, silently substitute models, or broaden the frozen C1 scope. Temporary model quota unavailability persists WAITING_FOR_MODEL under standing governance rather than substituting another worker. Do not mark preparation as an accepted implementation milestone.

## Review state

Phase 1 stops after preservation/recovery verification and architecture preparation. The first proposed implementation slice is bounded and reviewable. Broader migration remains gated by client owner mapping, native credential recovery limits, store adaptation coverage, exact UI provenance and adapter live qualification. No production capability is declared complete by these plans.
