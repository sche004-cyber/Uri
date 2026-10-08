# Approval result repair candidate — 2026-10-03

The User confirmed clicking Approve for Google Workspace creation. Read-only
inspection of that exact action found approved status and null consumed_at.
The stored argument fingerprint did not match its persisted arguments; rebuilding
only the PrincipalContext data-class representation made the old hash match.
No user identity values, arguments or credentials are included in this record.

Cause: ApprovalStore hashed nested data classes through default=str, while
asdict(ProposedAction) persisted them as maps. Consumption correctly failed closed.
The existing record is stale and invalid; do not rebind, edit or replay it.

Additional production path defects: the Decision Engine omitted this legacy
tool's declared content schema, leaving the observed proposal without kind/title;
the Flutter approval parser treated unsuccessful nested tool statuses as completion,
accepted empty narratives and dropped file links; decide_action omitted its actual
execution outcome from the own-session transcript used by follow-up reasoning.

Bounded repair: canonicalize data-class hashing to the already persisted map,
expose existing content-only inputs, preserve actual approval outcomes/links in
Flutter and the existing transcript. No approval/grant/identity policy change.
Existing mismatches stay invalid. No Google creation was retried by this repair.

## Test-isolation incident

A run of test_m19_office_readiness returned success unexpectedly for its nominal
no-credentials Gmail draft and Drive-upload cases (127 pass, 2 fail). Its old
connection_status._repo_root patch no longer isolates service credential paths.
Those legacy tests therefore reached installed Google services: an unsent draft
and a new report.docx containing fixture bytes may have been created. The test
discarded returned IDs; there is no reliable ID for cleanup. No send path exists
in the draft tool. No existing cloud item was changed/deleted, and no cleanup or
retry is attempted. This run is not qualification evidence.

The fixture now explicitly mocks both write-service methods and document
composition before tool invocation, independently of installed credentials.
All later runs use these mocks. Review this isolation repair independently.
