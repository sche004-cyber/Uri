# M1 app hosting design

- **Status:** proposal.
- **Existing state:** no app registry, lifecycle or broker exists (`M1_REPOSITORY_CAPABILITY_INVENTORY.md` §3).
- **First proof:** one small demonstration app. **URI Office is out of scope** for this milestone.

## 1. Reuse map

| Need | Existing component reused | New and minimal |
|---|---|---|
| Register and discover | External-capability descriptor pattern: closed transport set, developer-authored, pinned (`uri_core/external/contract.py:45`; `descriptors/yt_dlp.py`) | `uri_apphost/registry.py`: `app.json` manifests installed by the owner, with the SHA-256 of the package recorded (as `runtime_v1.verify_artifacts` does). Discovery is `GET /apps`, filtered by each user's app grants, which fail closed like `external/permission_binding.py`. |
| Launch and stop | Supervisor attempts plus named Job Objects with kill-on-close, process-tree kill, admission pools (`uri_supervisor/winproc.py`, `admission.py`) | Use Job **limits**: memory, active processes, CPU rate. The structure fields exist but are unused (`winproc.py:49,267`). This is either a frozen change or a non-frozen wrapper (D-6). |
| Interactive UI | A2UI catalog, validator, surface digest, `A2uiHub`, workspace dock; the scheduler's `a2ui_host.py` is the precedent | `surface_bridge.py`: app → A2UI messages, validated server-side by `uri_a2ui.validate` before relay. No webview, iframe or URLs (`validate.py:19`). |
| Controlled URI intelligence | Gateway fair queue; capability resolver; approval gate | `broker.py`: a per-(app, user) token limited to the manifest's services: `brain.complete`, `storage.*` (through the StorageBroker), `web.read` (through SafeFetcher), `notify` |
| User-specific state | `user_scoped_path` | `users/<uuid>/apps/<app_id>/state/` is the only directory the app process may write |
| Storage and network permissions | StorageBroker; SafeFetcher | The manifest declares requested services. **Network is denied by default.** Any egress goes through the broker's `web.read`, so apps never open sockets themselves. On Windows this is enforced with a per-account firewall rule (PC-blocked, unverified). |
| Resource tracking | Supervisor ledger, usage meter | Record Job accounting (`JOBOBJECT_BASIC_ACCOUNTING_INFORMATION`: CPU time, peak memory) per run in the per-user usage meter |
| Updates and versioning | Pinned-version and hash discipline (yt_dlp descriptor, Runtime v1 pins) | Versions are installed side by side (`apps/<id>/<version>/`). The state schema version is in the manifest, with a declared migration. Rollback means switching the active version pointer; state is backed up before migration. Users see "update available" and the owner approves installation. |

## 2. Manifest (PROPOSED)

```json
{
  "schema": "uri.app.v1",
  "id": "uri.demo.notes",
  "version": "0.1.0",
  "package_sha256": "<hex>",
  "entry": {"argv": ["python", "-I", "app.py"], "transport": "stdio-jsonl"},
  "surfaces": ["notes.main"],
  "actions": {"notes.save": {"confirms": false}, "notes.summarise": {"confirms": false},
              "notes.export": {"confirms": true}},
  "services": ["brain.complete", "storage.create", "storage.read"],
  "limits": {"memory_mb": 256, "processes": 4, "cpu_percent": 25, "wall_s": 3600},
  "network": "none",
  "state_schema": 1
}
```

Rules:
- Every action the app emits must be in `actions` and is registered with the A2UI action registry under the authority
  `app:<id>`.
- `confirms: true` actions go through the approval gate.
- Anything not declared is refused.

## 3. Process model

- **One instance per (user, app).**
- It runs as that user's low-privilege Windows account (the same mechanism as P1-6), inside a named Job Object with
  limits.
- The working directory is its state directory.
- Transport is stdio JSON lines: no listening ports, which removes a network attack surface.
- Lifecycle:

```
  INSTALLED → (user opens) → STARTING → RUNNING ⇄ IDLE → STOPPING → STOPPED
```

- There is an idle timeout. Logout, revoke or uninstall kills the process tree through the job.
- On a server restart, instances are not resumed automatically. The user reopens them; state persists on disk. This
  mirrors the bridge's "never relaunch on restart" rule.

## 4. Demonstration app (P5-4)

`uri.demo.notes` ("Link Notes"):
- a per-user list of notes, using the A2UI `List`, `TextField` and `Button` components;
- "Summarise" calls `brain.complete`;
- "Export" writes a Markdown file to the user's default output through `storage.create`, with approval.

This proves the following in one small app:
- registration;
- launch and stop;
- the A2UI presentation;
- intelligence access;
- per-user state isolation (two users see different notes);
- storage permissions;
- resource limits;
- versioning (ship 0.1.0, then 0.2.0 with a state migration).

## 5. Future URI Office (not implemented)

Office would be an app on this host. It would need A2UI `catalog/v2` components (Table and RichText, which the storage
design also needs) and the StorageBroker's copy-on-edit. The donor M39 `uri_v1/office` code stays on its branches.

## 6. Uncertainty

- Job Object limits and firewall-per-account behaviour are unverified (Windows, PC-blocked).
- How much the A2UI surface bridge costs in latency for interactive apps is unmeasured.
