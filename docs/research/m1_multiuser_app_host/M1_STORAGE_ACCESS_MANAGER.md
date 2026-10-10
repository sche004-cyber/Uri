# M1 extension: Storage and Access Manager (user-controlled folders, drives and workspace permissions)

- Baseline: `54ad7be` (canonical `integration/git-sync-20261008`).
- Part of `M1_ARCHITECTURE_AUDIT_AND_PLAN.md` (§11 there points here).
- Status: **research and planning only.**
- Evidence grades:
  - **CODE-RV**: source re-verified by the author at the baseline.
  - **DOC**: a project record.
  - **EXT**: an external page.
  - **PROPOSED**: does not exist yet.

---

## 0. Acceptance criteria for this extension (set before drafting)

- **SA-1.** Every requirement in the assignment (functional 1-10, the security list, storage behaviour) maps to an
  existing component, a proposed one, or an explicit owner decision.
- **SA-2.** Each item is labelled EXISTING or PROPOSED. EXISTING items cite code.
- **SA-3.** Enforcement is placed in the server-side broker and, where possible, the OS. Never only in the UI or the
  prompt.
- **SA-4.** The design extends existing seams rather than creating a parallel permission system. Where a new record type
  is unavoidable, the reason is stated.
- **SA-5.** The design is consistent with the owner-authorized Phase 1 ownership principle. Any conflict is surfaced as
  an owner decision, not resolved silently.
- **SA-6.** Every slice has tests and is marked cloud-testable or PC-blocked, frozen-touch or not.

---

## 1. What already exists (re-verified)

| Existing component | What it already guarantees | Evidence |
|---|---|---|
| **Per-user `FileStore`** | <ul><li>Stored names are server UUIDs; the client filename is never used as a path.</li><li>`_resolve_within_root` (realpath + root-prefix check) re-confirms containment on every read.</li><li>Extension allow-list; 25 MB cap counted on real bytes.</li><li>Nothing stored is executed.</li><li>Per user: `users/<uuid>/uploads`.</li></ul> | `uri_core/core/file_store.py:1-35, 157-190`; `test_m21_file_store_isolation.py` (RUN pass, see evidence file) |
| **Generated work goes to the per-user `FileStore`**; the client downloads via `GET /files/{id}/content` | <ul><li>Today "completed work" never leaves URI's own per-user store.</li><li>There is no user-chosen output folder.</li></ul> | `uri_core/tools/generate_document.py:22,99-101`; `convert_document.py:36,53-54,125,209` |
| **No Line A tool takes a raw filesystem path** | <ul><li>Tools read files only by `file_id`, `session_id`, or fixed directories.</li><li>So default-deny is structurally true today, but only because nothing can reach user folders at all.</li></ul> | grep of `uri_core/tools`, `uri_core/capabilities` for path kwargs: none found; `read_attached_file.py:39-41` |
| **Per-run harness workspace + verified copy-out** | <ul><li>Each run gets a fresh `workspace/<run_id>`.</li><li>URI verifies the output itself (a regular, non-symlink, non-empty file).</li><li>The output is copied out only after verification.</li><li>The harness never writes outside its scratch directory by design (Claude via `--allowedTools` path scoping; Codex via `--sandbox workspace-write`).</li></ul> | `uri_core/client_runtime/turn_runner.py:225-262`; `uri_supervisor/postconditions.py:100-104`; `uri_supervisor_bridge/bridge.py:347-352`; `uri_harness_adapters/__init__.py:27-50` |
| **Fail-closed per-user permission binding** for new external capabilities | <ul><li>A missing record means deny.</li><li>It deliberately does not reuse `CapabilityGrantsStore`, whose default is the full registry.</li></ul> | `uri_core/external/permission_binding.py:1-21` |
| **Capability grants ∩ mode ∩ registry**; admin-only grant edits | <ul><li>Capability-level authorization.</li><li>There is **no resource (folder) axis**.</li></ul> | `uri_core/core/capability_resolver.py`; `route_classification.py:69-76` |
| **Approval gate**: single-use, expiring, session- and argument-fingerprint-bound, per user | <ul><li>Consequential actions need approval of the exact arguments.</li></ul> | `uri_core/core/approval_store.py`; `test_server_approval_endpoints.py` |
| **A2UI**: digest-bound surfaces, action registry with named authorities, inputs (CheckBox, ChoicePicker, TextField, DateTimeInput), URLs refused | <ul><li>A safe channel for permission cards and settings.</li><li>It cannot open a native folder picker.</li><li>It has no component for a file list or table.</li></ul> | `uri_a2ui/catalog.py:35-47`; `uri_a2ui/actions.py:11-29`; `uri_a2ui/validate.py:19` |
| **Flutter client file picker** (single file, injected `FilePickerFn`) | <ul><li>Uploads one file.</li><li>No folder picker yet. The `file_picker` package is already a dependency.</li></ul> | `uri_ui/lib/services/platform_file_picker.dart:22`; `file_picker_service.dart:28` |
| **Owner-authorized ownership principle (Phase 1)** | <ul><li>"Each client owns its private database, workspace, configuration, native accounts and harness processes" (:7).</li><li>Workspace access for local runners "belong[s] to client" (:32).</li><li>Uploads and file evidence: client-owned, with "no absolute path on server" (:96).</li><li>The tool execution location comes from a trusted registry: an "execution-location descriptor + scoped ticket" (:94).</li><li>Layout `<client-root>/<id>/workspace/` (:128).</li></ul> | `docs/evidence/phase0_runtime_inventory_20261005/SERVER_CLIENT_OWNERSHIP.md` (DOC; "high-level ownership is authorized by the User's Phase 1 instruction", :138) |
| Google Drive per-user token; scopes `drive.readonly`, `drive.file` | <ul><li>Per-user cloud access exists for single-action tools.</li><li>`drive.readonly` is a broad (restricted-class) scope.</li></ul> | `uri_core/services/gmail_service.py:54` SCOPES; `drive_service.py` |
| Hash-chained append-only event log (scheduler); append-only tables (supervisor ledger) | <ul><li>A tamper-evident audit pattern exists in the scheduler.</li><li>The supervisor ledger rejects updates and deletes but is not chained.</li></ul> | `uri_scheduler/store.py:9,60`; `uri_supervisor/ledger.py`; `tests/phase2a/test_ledger.py` |

**What is missing:**
- user-chosen folders, drives or output locations;
- per-verb folder permissions;
- named workspaces;
- temporary per-task access;
- a storage approval flow;
- a file-access audit log;
- a native folder picker;
- delivery to client folders;
- reparse-point, UNC and device-path guards outside the single-file output check.

**Observations, low severity:**
- `linked_document_service.py:167-207` extracts zip members with `Path(name).name`, which is traversal-safe. It reads
  each member fully with no decompressed-size bound. This is a zip-bomb exposure to fix when the broker absorbs that
  service.
- `scheduler/engine.py:892` and `bridge.py:352` copy outputs to owner-only destinations without a broker.

---

## 2. Ownership conflict that needs an owner decision (D-9)

The Phase 1 rule says client content and workspaces belong to the client. M1 asks for server folders and server-side
harnesses and apps acting on user files. Both are compatible **if every storage root carries a location** and work is
done where the data lives:

| Root location | Who performs I/O | Server sees |
|---|---|---|
| `CLIENT` (a folder on the user's device) | The client (Flutter + client worker) | An opaque `root_id` + display label + **content only for the files the user approved for a task**. Never the device path. |
| `SERVER_PRIVATE` (`users/<uuid>/storage/…` on the server) | The server broker | Full, but ACL-confined to that user |
| `SERVER_SHARED` (an admin-published server folder or drive, e.g. `D:\Office`) | The server broker | Full; access per user grant |
| `CLOUD` (Drive and later others) | The server broker with **that user's own** token | Only what the provider scope allows |

This reuses the Phase 1 "execution-location descriptor" seam (:94). **D-9:** the owner confirms that
`SERVER_PRIVATE` and `SERVER_SHARED` are acceptable exceptions to "client owns content" for M1, given that Line A
already hosts per-user stores on the server. Alternatively, M1 is limited to `CLIENT` + `CLOUD`.

---

## 3. Storage and folder-permission architecture (PROPOSED)

```
 requester (user turn | harness run | hosted app | scheduler job | Office flow)
        │ never holds raw paths; asks with (root_id, relative path or file handle, verb)
        ▼
 StorageBroker (one per server; in-process library + loopback API for app host and scheduler)
   1. authenticate principal (gateway-validated user) + requester identity (app id, harness id, task id)
   2. resolve grant: StorageGrantStore[user] ∩ capability grant ∩ workspace scope ∩ temporary task grant
   3. path-safety check (§6) and location dispatch (CLIENT → client channel; SERVER/CLOUD → local or provider I/O)
   4. verbs that create/edit/delete → approval gate (existing), digest-bound to (root, path, verb, content hash)
   5. edit-on-copy + versioned backup; delete → URI trash
   6. append audit record (hash-chained, content-free)
        │
        ▼
 OS enforcement: per-user Windows account + NTFS ACL on that user's server roots (S7 dependency);
 harnesses and apps get only a per-run scratch directory, never a user root
```

**Data model (PROPOSED). Why it is a new record type rather than an extension of `CapabilityGrantsStore`:**
- Capability grants answer "may this user use tool X". They default to the full registry.
- Storage needs a *resource × verb × duration* axis and fail-closed defaults.
- So `StorageGrantStore` follows the fail-closed pattern of `external/permission_binding.py`.
- It is **consulted from the same decision point**, the resolver/approval gate. It is not a separate gatekeeper. This
  avoids a competing framework: one decision path, two inputs.

| Record | Fields |
|---|---|
| `StorageRoot` | <ul><li>`root_id` (UUID)</li><li>`owner_user_id`</li><li>`location` (CLIENT, SERVER_PRIVATE, SERVER_SHARED, CLOUD)</li><li>`label`</li><li>locator: device path held **client-side only**; server canonical path; or cloud folder id</li><li>`kind`: folder or whole_drive (elevated)</li><li>`device_id` for CLIENT</li><li>`published_by_admin` for SERVER_SHARED</li><li>`network_path_allowed` (default false)</li></ul> |
| `StorageGrant` | <ul><li>`user_id`, `root_id`</li><li>verbs ⊆ {read, create, edit, delete}</li><li>`requester_scope`: user, app id, or harness id</li><li>`workspace_id`</li><li>`expires_at`, or `task_id` for temporary grants</li><li>`granted_via` (onboarding, settings, approval id)</li><li>`elevated` (whole drive)</li></ul> |
| `Workspace` | <ul><li>`workspace_id`, `user_id`, `name` (Office, Personal, Projects)</li><li>`grant_ids`</li><li>`default_output`: root_id + subfolder</li></ul> <br>A workspace **only narrows**: a turn in workspace W can use only W's grants. It is not a mode and never widens authority. This follows the `AGENTS.md:92-93` rule that UX state never authorizes. |
| `DeliveryRecord` | <ul><li>`output_id` (FileStore id), `sha256`</li><li>target root and path</li><li>state: PRODUCED → DELIVERING → DELIVERED / PENDING_DELIVERY / REFUSED</li><li>`attempts`, `last_error`</li></ul> |
| `AccessRequest` | <ul><li>`request_id`</li><li>requester (user, app, harness, task)</li><li>root (or "new location")</li><li>verbs, duration, reason</li><li>A2UI surface digest</li><li>decision</li></ul> |
| `AccessEvent` (audit) | <ul><li>time, user, requester kind and id</li><li>root_id, relative path hash and display name</li><li>verb, decision, approval id</li><li>content sha256 (no content)</li><li>`prev_hash`</li></ul> |

**Shared service?** Yes. The same broker serves all of these:
- Line A tools: new `storage_read` / `storage_write` capabilities, alongside the unchanged FileStore tools.
- Harnesses: copy-in of approved files to the run workspace; copy-out through the broker.
- Hosted apps: S8 broker service `files.*`, token-scoped to the manifest.
- The scheduler: replace the direct `copyfile` at `engine.py:892`.
- A future URI Office: replace donor M39 write-back with broker `edit` + version backup.

This is feasible because every one of these already ends in "URI copies a verified output to a destination". The
broker becomes that single copy step.

---

## 4. Onboarding and A2UI settings interface (PROPOSED)

A2UI cannot open native pickers, and it should never carry device paths. The split is:

| UI element | Rendered by | Notes |
|---|---|---|
| "Choose a folder or drive" | **Native client picker**: `file_picker` `getDirectoryPath()` on Windows (package already a dependency) | <ul><li>For CLIENT roots the path stays on the device.</li><li>The client registers a `root_id` + label with the server.</li><li>SERVER_SHARED roots are chosen from an admin-published list, not by browsing the server disk.</li></ul> |
| Onboarding step "Where should URI save your work?" + "Which folders may URI read?" | A2UI surface `storage.onboarding` (Card, Text, ChoicePicker for workspace, CheckBoxes for verbs, Button → native picker request) | Produced by the broker; actions registered with authority `storage` |
| Workspace settings: list of workspaces → roots → verbs, default output, expiry; Revoke button per grant; "Revoke all for this app or harness" | A2UI surface `storage.settings` | Needs a new **List row / Table** component (`uri:a2ui/catalog/v2`), also needed later by Office |
| Access request card: "*Codex (task 'Quarterly report') on behalf of Asha* wants **edit** in *Office › Reports* for **this task only**" with Allow once / Allow for workspace / Deny | A2UI surface `storage.access_request` | <ul><li>Digest-bound; the existing approval gate consumes the decision.</li><li>Always names user + app or harness + task (requirement 8).</li></ul> |
| Whole-drive or network-path request | Same card with an "elevated" banner + typed confirmation | Admin publication required first for SERVER_SHARED drives |
| Pending deliveries: "3 files waiting: *Office › Reports* unavailable" with Retry / Choose another folder / Download | A2UI surface `storage.deliveries` | Retries go through the broker only |

New A2UI actions, all with `authority: "storage"` and `confirms: true` where consequential:
- `storage.grant.decide`
- `storage.grant.revoke`
- `storage.root.register_client`
- `storage.workspace.save`
- `storage.delivery.retry`
- `storage.delivery.retarget`

---

## 5. Multi-user isolation design

1. **Ownership.** Every `StorageRoot`, `StorageGrant`, `Workspace`, `DeliveryRecord` and audit chain is stored under
   `users/<uuid>/storage/` (via `user_scoped_path`, UUID-only). They are never in an install-wide file. This avoids
   repeating the shared `capability_grants.json` pattern.
2. **Shared server folders.**
   - SERVER_SHARED roots are *published* by the admin: an ADMIN route behind the gateway.
   - Each user's grant on them is separate, and requested and approved per user.
   - Publication grants nothing by itself.
   - The admin never receives another user's grants or files through the broker. Admin OS access is out of scope and
     is disclosed.
3. **No path oracle.**
   - Errors for roots a user does not own are identical to "not found".
   - `root_id`s are UUIDs, so they cannot be enumerated.
4. **Credentials.** Cloud tokens and any SMB credentials are per user, encrypted (S3-T6 pattern), and never returned
   to any client. The broker uses them server-side only.
5. **OS layer (needs S7).** Each URI user's server roots carry an NTFS ACL for that user's dedicated low-privilege
   Windows account plus the URI service account. Harness and app processes run as the user's account (S7/S8), so the
   OS refuses cross-user reads even if a harness ignores its tool scoping. Until S7 exists, isolation is broker-only
   and that limitation is disclosed.

---

## 6. Filesystem and cloud permission enforcement

**Path safety (broker, every operation).** The proposed rules are listed below. Item 1 already exists in
`FileStore._resolve_within_root`, and item 3 for single files in `postconditions.py:100-104`.

1. Resolve `root + relative` with `os.path.realpath`. Require `os.path.commonpath([root, candidate]) == root`, compared
   after `normcase` (Windows is case-insensitive). The existing check uses a string prefix plus `os.sep`; commonpath is
   stricter.
2. Reject inputs containing:
   - absolute components, `..` after normalization, or drive letters in a relative path;
   - `:` other than the drive (NTFS alternate data streams);
   - trailing dots or spaces;
   - reserved device names (`CON`, `NUL`, `COM1`…);
   - `\\?\`, `\\.\` or UNC prefixes unless `network_path_allowed`;
   - 8.3 short-name aliases. Accept only after `realpath` re-expansion.
3. Reject reparse points in **every** component: symlinks, junctions, mount points
   (`os.lstat().st_file_attributes & FILE_ATTRIBUTE_REPARSE_POINT` on Windows; `is_symlink`/`is_junction` on 3.12+).
4. **TOCTOU.**
   - Windows: open by handle with `FILE_FLAG_OPEN_REPARSE_POINT`, then confirm with `GetFinalPathNameByHandleW` that the
     opened object is still inside the root before any read or write.
   - POSIX (cloud tests): use `openat` with `O_NOFOLLOW` per component.
5. Network and removable drives:
   - `GetDriveTypeW` → `DRIVE_REMOTE` is refused unless the root is an approved network root.
   - Whole-drive roots are `elevated`.
6. Size, type and count caps reuse the FileStore extension allow-list and byte caps per verb.

**Verb mapping and confirmation:**
- `read`: no prompt inside a granted root.
- `create`: a new file only. Collisions get a new name and never overwrite.
- `edit`: **copy-on-edit by default.** Edits produce a new version beside or into the output root. Overwriting the
  original needs an `edit_original` grant plus per-operation approval. The previous bytes are kept in
  `users/<uuid>/storage/versions/` with a retention period.
- `delete`: always per-operation approval. The file moves to URI trash with retention, never a hard delete in M1.
- Sensitive extensions (credential-shaped names via `security_guards.looks_like_credential_key`, `.pfx`, `.kdbx`,
  `.ssh`) are always confirmed and never sent to cloud models without explicit approval. This reuses
  `uri_core/core/security_guards.py`.

**Harnesses and apps (same permissions):**
- They never receive a user root.
- The broker copies in the approved files (read grant) to the existing per-run workspace.
- After the existing verification, the broker copies out (create/edit grant + approval) to the target root.
- Network flags (`capsule.network`) stay off unless granted.
- This means the harness permission system needs no change for M1. Only the copy-in and copy-out steps are added.

**Cloud (Drive):**
- Each user's own token, through the per-user `GmailService/DriveService(user_id)` path (fixed in S3).
- Folder grants map to Drive folder ids. The broker enforces verbs before calling the API.
- Recommendation: move from `drive.readonly` (broad, restricted-class) toward `drive.file` plus explicit per-file
  selection.
  - Google's Picker is a web component. A desktop Flutter equivalent needs research (R-S1, unverified). This is EXT
    secondary knowledge.
  - Scope changes require new consent from each user.

---

## 7. Client-local versus server-side file access

Server agents **cannot** see device files. Two models were compared:

| Model | How it works | Reuse | Fit for M1 |
|---|---|---|---|
| **A. Scoped transfer (recommended for M1)** | <ul><li>The client keeps the CLIENT root path and enforces its verbs locally.</li><li>For a task, the user approves specific files. The client uploads them over the tailnet with TLS + bearer into the user's server FileStore with a task-scoped lifetime.</li><li>Outputs come back via `GET /files/{id}/content`. The client writes them into the chosen local folder after a local re-check of grant and path.</li></ul> | Existing `POST /files`, `GET /files/{id}/content`, per-user FileStore, `attached_file_ids` validation (M34) | <ul><li>Works with Line A today.</li><li>New work: a client folder picker, a local grant store, a delivery writer, and a chunked/resumable upload above the 25 MB cap.</li></ul> |
| **B. Client-side execution** | The client worker runs the file operation or harness locally, per the Phase 1 design. The server sends only bounded instructions. | Line B client worker, `turn_runner` | <ul><li>The correct long-term model.</li><li>Blocked for remote use by the frozen loopback rule and D-1.</li></ul> |
| Rejected: SMB shares from devices to the server, sync tools (Syncthing), or mounting device drives on the server | — | — | They expose device filesystems to a multi-user server, need credentials on the server, and are poor for path containment |

**Delivery when the client is offline:**
- The output stays in the user's private server FileStore as PENDING_DELIVERY.
- The client fetches it on its next connection.
- It is never written anywhere else.

---

## 8. Approval, revocation and recovery workflows

**Request more access.** A requester calls the broker with a missing grant. The flow:
1. The broker returns `ACCESS_REQUIRED` with a request id. The operation is not executed.
2. The A2UI `storage.access_request` card names the user, app or harness, task, root, verbs and duration.
3. The user decides. A whole-drive or network request also needs admin publication plus typed confirmation.
4. The decision is digest-bound and consumed once (existing approval-store semantics).
5. The grant is created with its duration (`task`, `workspace`, or `until revoked`).
6. The operation is retried by the requester. URI does not auto-retry.

**Temporary per-task access:**
- The grant carries `task_id`.
- It is revoked automatically on task end, cancel, failure, or server restart. This copies the bridge's
  revoke-on-restart rule.

**Revoke:**
- One tap per grant, per workspace, per app or harness, or "revoke everything".
- The broker checks the store on **every** operation; no authority is cached.
- In-flight runs that hold copied-in files are cancelled through the existing supervisor `request_cancel`. Their
  outputs are quarantined as PENDING and not delivered.
- OS ACL entries (S7) are removed in the same transaction. A failed removal blocks the revoke from reporting success.

**Output delivery and recovery:**
1. PRODUCED (FileStore, private).
2. DELIVERING: re-check the grant + path safety + free space.
3. On success: DELIVERED + audit record.
4. On failure (root offline, revoked, disk full, client offline): PENDING_DELIVERY. The output stays in the private
   store, the A2UI deliveries card shows it, and retry happens on user action or root-available events only, under
   **re-validated** grants.
5. There is **never** a fallback to another root, and never to another user.

**Edit recovery:**
- Version backups before any original overwrite.
- Trash for deletes.
- "Restore" through the broker with an audit record.

**Audit:**
- A per-user hash-chained `AccessEvent` log, content-free, using the scheduler `event` table pattern (`uri_scheduler/store.py:9,60`).
- The user can view their own log. The admin sees only counts and anomalies, never paths of other users' private
  roots.

---

## 9. Required implementation slices and tests

These are numbered as continuations of the main plan.

### S10. Broker core (path safety, grants, workspaces, audit)

- NEW non-frozen package `uri_storage/`. **Cloud-testable** (POSIX path rules; Windows rules unit-tested with the
  `ntpath` module and simulated attributes).
- Tests:
  - traversal corpus (`..`, mixed separators, encoded, ADS, device names, UNC, `\\?\`, short names);
  - symlink and junction escape: symlinked root, symlinked component, symlink swapped after check (TOCTOU race test
    with `O_NOFOLLOW`);
  - default deny with no record;
  - verb separation (read grant cannot create/edit/delete);
  - workspace narrowing;
  - task-grant expiry on task end and restart;
  - cross-user root access gives the not-found shape;
  - audit chain verification detects tampering;
  - content never appears in the audit (pattern of `test_usage_meter_no_content_stored.py`).

### S11. Decision-point integration

- **FROZEN-TOUCH**: `approval_gate.py`, `dispatcher.py`, `server.py` route classification. Needs authorization
  (extends D-2).
- Adds new `storage_*` capabilities and broker consultation in the existing gate.
- Tests:
  - every `storage_*` call without a grant is refused before tool code runs;
  - approval digest binds (root, path, verb, sha256), and a changed byte invalidates it;
  - route-classification count updated; `test_m22_3_route_authorization.py` still passes.

### S12. Delivery manager

- Non-frozen, **cloud-testable**.
- Tests:
  - output always lands in the requesting user's selected root;
  - root offline or revoked → PENDING_DELIVERY in the private store, with no write elsewhere;
  - retry re-validates the grant (revoke between attempts → refused);
  - never another user's root (property test over 3 users).

### S13. A2UI storage surfaces + `catalog/v2` (List row / Table)

- **Python side cloud-testable** (`uri_a2ui` validators). Flutter rendering is **PC-blocked**.
- Tests:
  - surfaces validate;
  - every action is registered with `authority: storage`;
  - no device paths appear in any surface, for CLIENT roots;
  - Dart and Python shared contract cases extended.

### S14. Client folder picker, local grant store, scoped transfer

- Flutter; **PC-blocked**.
- Tests:
  - `getDirectoryPath` result never sent to the server;
  - local verb enforcement;
  - resumable upload with hash check;
  - delivery writer refuses a symlinked or reparse target;
  - offline → pending, then delivered on reconnect.

### S15. OS enforcement

- NTFS ACL per user root, harness and app scratch dirs under the user's account.
- Depends on S7; **PC-blocked**, Windows.
- Tests:
  - user B's process gets ACCESS_DENIED on user A's root;
  - revoke removes the ACE;
  - junction planted inside a root is refused by the broker and by the OS.

### S16. Harness, app, scheduler and Office adoption

- **Partly frozen** (bridge copy-out); cloud-testable with fake harnesses on POSIX; Job/ACL parts PC-blocked.
- Tests:
  - copy-in includes only granted files;
  - copy-out passes through broker verbs and approval;
  - the scheduler's direct `copyfile` is replaced and its tests still pass.

### S17. Drive folder grants and scope reduction

- **Frozen-touch** (drive service); live consent **PC-blocked**.
- Tests (fake Drive): Drive verbs enforced before API calls; per-user token only.
- Research item: `drive.file` + picker on desktop (R-S1).

**Order:** S10 → S12 → S11 (authorization) → S13 → S14 → S16 → S17 → S15.

- **Smallest useful storage M1:** S10 + S12 + S11 + S13 (Python side). Users then get server-private and
  admin-published folders with per-verb grants, default output and pending delivery. This adds about 1,000-1,400
  lines plus tests: Medium-Large, about 2-3 sessions.
- **Client folders (S14)** follow.

---

## 10. Existing vs proposed: summary

| Requirement | Existing today | Proposed |
|---|---|---|
| 1 Folder/drive picker | Single-file picker only | Native folder picker (S14) + A2UI onboarding/settings (S13) |
| 2 Client, server, drive, cloud locations | Per-user FileStore; Drive per-user (single-action) | `StorageRoot` locations (S10), client transfer (S14), Drive folders (S17) |
| 3 Separate verbs | Capability-level grants only | `StorageGrant` verbs (S10) via the existing gate (S11) |
| 4 Default output folder | Outputs stay in FileStore | `Workspace.default_output` + delivery manager (S12) |
| 5 Named workspaces | Modes exist but are UX-only and never authority | `Workspace` grant sets that only narrow (S10) |
| 6 Temporary per-task access | Approvals are single-use, per action | Task-scoped grants auto-revoked (S10) |
| 7 Easy revoke | Device revoke and admin grant edit only | Per-grant, app or harness, all (S13); no cached authority (S10) |
| 8 Show requester | Approval cards show the action | Access card names user + app or harness + task (S13) |
| 9 Request more access | Approval gate for actions | `ACCESS_REQUIRED` → card → digest-bound grant (S10/S11/S13) |
| 10 Multi-user isolation | Per-user stores (RUN pass) | Per-user storage records + ACLs (S10/S15) |
| Default deny | Structurally true (no tool reaches folders) | Kept explicitly fail-closed when folders are added (S10) |
| Broker enforcement, not UI | — | Broker + existing gate (S10/S11) |
| Harnesses and apps under the same permissions | Per-run workspace + verified copy-out | Broker copy-in and copy-out (S16) |
| OS sandbox | Job Objects (lifetime only); same Windows user | Per-user accounts + ACLs (S7/S15) |
| Traversal and symlink protection | FileStore containment; single-file symlink refusal | Full component-wise rules + handle re-check (S10) |
| Whole drive elevated | — | `elevated` grants + admin publication + typed confirmation (S10/S13) |
| Copy-on-edit | Harness scratch workspace pattern | Broker edit = new version; original overwrite approval-only (S10) |
| Destructive confirmation | Approval gate | Delete always approved; trash (S10/S11) |
| Audit | Hash-chain pattern (scheduler `event` table) | Per-user `AccessEvent` chain (S10) |
| Credentials never exposed | Provider keys never read back | Same for storage credentials; server-side use only (S10, S3-T6) |

---

## 11. Self-review of this extension (protocol steps 3-6)

| # | Flaw found in the draft | Repair |
|---|---|---|
| SS-1 | The draft placed device paths in A2UI settings surfaces, which conflicts with the Phase 1 rule "no absolute path on server" (:96). | CLIENT root paths now stay on the device. The server holds `root_id` + label only. S13 has a test for this. |
| SS-2 | The draft proposed extending `CapabilityGrantsStore` with folder entries. Its default is the full registry, which is wrong for storage. | It now uses a fail-closed record modelled on `external/permission_binding.py`, consulted from the same gate so that no second decision point exists (SA-4). |
| SS-3 | The draft claimed URI "already enforces default-deny for folders". | Reworded: default-deny is true only structurally, because no tool reaches folders. That is not an enforced policy. |
| SS-4 | The draft gave OS-level isolation as a property of M1. | It depends on S7 (per-user Windows accounts) and is PC-blocked. Broker-only isolation until then is disclosed (§5.5). |
| SS-5 | The draft ignored the Phase 1 ownership principle. | Surfaced as owner decision D-9 (§2). |
| SS-6 | The draft labelled the Drive Picker approach as workable on desktop. | Marked as research item R-S1, unverified. |

**Unverified items and their effect:**
- R-S1 (desktop Drive picker): affects only S17.
- Windows API behaviour for `GetFinalPathNameByHandleW` and junction detection on the owner's Python version: affects
  S10's Windows path. Verify on the PC.
- File-picker folder support on the installed `file_picker` version: S14, PC-blocked.

None of these change the architecture verdict.
